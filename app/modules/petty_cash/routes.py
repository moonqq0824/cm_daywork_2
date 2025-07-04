from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from decimal import Decimal, ROUND_HALF_UP
from flask_login import login_required, current_user
from app import db
from .models import Transaction, TransactionItem, TransactionType, TaxType, TaxCalculationMethod, ApprovalStatus, CashCountSession, CashCountDetail
from .forms import ExpenditureForm, IncomeForm, MonthEndSettlementForm, RejectionForm
from datetime import date, datetime, timedelta
from sqlalchemy import func, extract
from app.modules.user.routes import manager_required
import calendar 

petty_cash_bp = Blueprint('petty_cash', __name__)

@petty_cash_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    transactions_query = Transaction.query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
    transactions = transactions_query.paginate(page=page, per_page=10, error_out=False)
    
    # --- 最新的、與結轉功能完全同步的餘額計算邏輯 ---
    
    # 1. 找到最新的一筆結轉紀錄 (這次是全局尋找，沒有日期限制)
    latest_settlement = Transaction.query.filter(
        Transaction.description.like('%餘額結轉%')
    ).order_by(Transaction.transaction_date.desc()).first()

    # 2. 決定計算的起始點（期初餘額）
    balance = Decimal('0.0')
    start_date = date(1900, 1, 1) # 預設一個很早的日期
    if latest_settlement:
        balance = latest_settlement.total_amount
        start_date = latest_settlement.transaction_date

    # 3. 計算從「起始點」到「今天」為止，所有新發生的收支
    income_since_start = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.transaction_type == TransactionType.INCOME,
        Transaction.transaction_date > start_date,
        ~Transaction.description.like('%餘額結轉%') # 計算時要排除結轉本身的金額
    ).scalar() or Decimal('0.0')

    expenditure_since_start = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.transaction_type == TransactionType.EXPENDITURE,
        Transaction.transaction_date > start_date
    ).scalar() or Decimal('0.0')

    # 4. 得到最終正確的目前餘額
    current_balance = balance + income_since_start + expenditure_since_start

    return render_template(
        'petty_cash_index.html', 
        transactions=transactions, 
        balance=current_balance, # 傳遞修正後的餘額
        TransactionType=TransactionType,
        ApprovalStatus=ApprovalStatus
    )

@petty_cash_bp.route('/transaction/<int:transaction_id>')
@login_required
def transaction_detail(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction:
        flash('找不到該筆交易。', 'danger')
        return redirect(url_for('petty_cash.index'))
    return render_template(
        'transaction_detail.html', 
        transaction=transaction, 
        TransactionType=TransactionType, 
        ApprovalStatus=ApprovalStatus  # <--- 新增這一行
    )

@petty_cash_bp.route('/expenditure/add', methods=['GET', 'POST'])
@login_required
def add_expenditure():
    form = ExpenditureForm()
    if request.method == 'GET':
        form.application_date.data = date.today()
        form.transaction_date.data = date.today()
        form.applicant_name.data = current_user.display_name

    if form.validate_on_submit():
        try:
            # 稅務計算
            tax_type_str = form.tax_type.data
            tax_calc_method_str = form.tax_calculation_method.data
            base_amount = sum(Decimal(item['quantity']) * Decimal(item['unit_price']) for item in form.items.data)
            
            subtotal, tax, total_amount = Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

            if tax_type_str == TaxType.TAXABLE.name:
                tax_rate = Decimal('0.05')
                if tax_calc_method_str == TaxCalculationMethod.EXCLUSIVE.name:
                    subtotal = base_amount
                    tax = (subtotal * tax_rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                    total_amount = subtotal + tax
                elif tax_calc_method_str == TaxCalculationMethod.INCLUSIVE.name:
                    total_amount = base_amount
                    subtotal = (total_amount / (1 + tax_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    tax = total_amount - subtotal
            else:
                subtotal, tax, total_amount = base_amount, Decimal('0.0'), base_amount
            
            new_transaction = Transaction(
                transaction_type=TransactionType.EXPENDITURE,
                application_date=form.application_date.data,
                erp_document_number=form.erp_document_number.data,
                status=ApprovalStatus.DRAFT,
                transaction_date=form.transaction_date.data,
                applicant_id=current_user.id,
                description=form.description.data,
                tax_type=TaxType[tax_type_str],
                tax_calculation_method=TaxCalculationMethod[tax_calc_method_str] if tax_calc_method_str else None,
                subtotal=subtotal, tax=tax, total_amount=-total_amount,
            )
            
            for item_data in form.items.data:
                new_item = TransactionItem(
                    item_name=item_data['item_name'],
                    quantity=Decimal(item_data['quantity']), unit=item_data['unit'],
                    unit_price=Decimal(item_data['unit_price']),
                    line_total=Decimal(item_data['quantity']) * Decimal(item_data['unit_price']),
                    transaction=new_transaction
                )
            
            db.session.add(new_transaction)
            db.session.commit()
            flash('支出紀錄已成功新增！', 'success')
            return redirect(url_for('petty_cash.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增失敗，錯誤：{e}', 'danger')

    return render_template('add_expenditure.html', form=form)

@petty_cash_bp.route('/transaction/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction or transaction.transaction_type != TransactionType.EXPENDITURE:
        flash('找不到該筆支出紀錄。', 'danger')
        return redirect(url_for('petty_cash.index'))
    
    if transaction.status != ApprovalStatus.DRAFT and not current_user.is_manager():
        flash('此申請已送出，無法編輯。', 'warning')
        return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction_id))
    
    form = ExpenditureForm(obj=transaction)

    if form.validate_on_submit():
        try:
            # (稅務計算邏輯與 add 相同)
            tax_type_str = form.tax_type.data
            tax_calc_method_str = form.tax_calculation_method.data
            base_amount = sum(Decimal(item['quantity']) * Decimal(item['unit_price']) for item in form.items.data)
            subtotal, tax, total_amount = Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

            if tax_type_str == TaxType.TAXABLE.name:
                tax_rate = Decimal('0.05')
                if tax_calc_method_str == TaxCalculationMethod.EXCLUSIVE.name:
                    subtotal = base_amount; tax = (subtotal * tax_rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                    total_amount = subtotal + tax
                elif tax_calc_method_str == TaxCalculationMethod.INCLUSIVE.name:
                    total_amount = base_amount; subtotal = (total_amount / (1 + tax_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    tax = total_amount - subtotal
            else:
                subtotal, tax, total_amount = base_amount, Decimal('0.0'), base_amount

            # 更新主表資料
            transaction.application_date = form.application_date.data
            transaction.erp_document_number = form.erp_document_number.data
            transaction.transaction_date = form.transaction_date.data
            transaction.applicant_name = form.applicant_name.data
            transaction.description = form.description.data
            transaction.tax_type = TaxType[form.tax_type.data]
            transaction.tax_calculation_method = TaxCalculationMethod[form.tax_calculation_method.data] if form.tax_calculation_method.data else None
            transaction.subtotal, transaction.tax, transaction.total_amount = subtotal, tax, -total_amount
            
            # 清空舊明細，建立新明細
            transaction.items = []
            db.session.flush()
            for item_data in form.items.data:
                transaction.items.append(TransactionItem(
                    item_name=item_data['item_name'],
                    quantity=Decimal(item_data['quantity']), unit=item_data['unit'],
                    unit_price=Decimal(item_data['unit_price']),
                    line_total=Decimal(item_data['quantity']) * Decimal(item_data['unit_price'])
                ))
            
            db.session.commit()
            flash('支出紀錄已成功更新！', 'success')
            return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction.id))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗，錯誤：{e}', 'danger')

    # GET 請求時，手動設定 Enum 類型的值
    form.tax_type.data = transaction.tax_type.name
    if transaction.tax_calculation_method:
        form.tax_calculation_method.data = transaction.tax_calculation_method.name

    # 手動填充 Enum 類型的值
    form.tax_type.data = transaction.tax_type.name
    if transaction.tax_calculation_method:
        form.tax_calculation_method.data = transaction.tax_calculation_method.name

    # 手動填充申請人姓名
    form.applicant_name.data = transaction.applicant.display_name

    return render_template('edit_transaction.html', form=form, transaction_id=transaction_id)

@petty_cash_bp.route('/income/add', methods=['GET', 'POST'])
@login_required
@manager_required
def add_income():
    form = IncomeForm()
    if request.method == 'GET':
        form.application_date.data = date.today()
        form.transaction_date.data = date.today()

    if form.validate_on_submit():
        try:
            new_income = Transaction(
                transaction_type=TransactionType.INCOME,
                application_date=form.application_date.data,
                transaction_date=form.transaction_date.data,
                applicant_id=current_user.id,
                description=form.description.data,
                total_amount=form.total_amount.data,
                subtotal=form.total_amount.data,
                tax=0, tax_type=TaxType.TAX_EXEMPT,
                status=ApprovalStatus.APPROVED
            )
            db.session.add(new_income)
            db.session.commit()
            flash('收入紀錄已成功新增！', 'success')
            return redirect(url_for('petty_cash.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增收入失敗，錯誤：{e}', 'danger')
            
    return render_template('add_income.html', form=form)

@petty_cash_bp.route('/income/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit_income(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction or transaction.transaction_type != TransactionType.INCOME:
        flash('找不到該筆收入紀錄。', 'danger')
        return redirect(url_for('petty_cash.index'))

    form = IncomeForm(obj=transaction)
    
    if form.validate_on_submit():
        try:
            transaction.application_date = form.application_date.data
            transaction.transaction_date = form.transaction_date.data
            transaction.applicant_name = form.applicant_name.data
            transaction.description = form.description.data
            transaction.total_amount = form.total_amount.data
            transaction.subtotal = form.total_amount.data
            
            db.session.commit()
            flash('收入紀錄已成功更新！', 'success')
            return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction.id))
        except Exception as e:
            db.session.rollback()
            flash(f'更新收入失敗，錯誤：{e}', 'danger')

    return render_template('edit_income.html', form=form, transaction=transaction)

@petty_cash_bp.route('/transaction/<int:transaction_id>/delete', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction:
        flash('找不到該筆交易。', 'danger')
        return redirect(url_for('petty_cash.index'))
    
    if transaction.status != ApprovalStatus.DRAFT and not current_user.is_manager():
        flash('此申請已送出，無法刪除。', 'warning')
        return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction_id))

    try:
        db.session.delete(transaction)
        db.session.commit()
        flash(f'交易 (ID: {transaction_id}) 已成功刪除。', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗，錯誤：{e}', 'danger')
    return redirect(url_for('petty_cash.index'))

@petty_cash_bp.route('/accounting', methods=['GET'])
@login_required
def accounting_operations():
    """顯示會計作業頁面"""
    form = MonthEndSettlementForm()
    # 預設為上一個月份
    today = date.today()
    first_day_of_month = today.replace(day=1)
    last_month_date = first_day_of_month - timedelta(days=1)
    form.year.data = str(last_month_date.year)
    form.month.data = str(last_month_date.month)
    return render_template('accounting_operations.html', form=form)


@petty_cash_bp.route('/accounting/settle', methods=['POST'])
@login_required
def settle_month_end():
    """處理月結作業的邏輯"""
    form = MonthEndSettlementForm()
    if form.validate_on_submit():
        year = int(form.year.data)
        month = int(form.month.data)

        # --- ▼▼▼ 全新的、更穩健的月底餘額計算邏輯 ▼▼▼ ---

        # 1. 定義要計算的目標月份的結束日期
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)

        # 2. 計算從古至今，到該月底為止的所有收入總額
        total_income = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.transaction_type == TransactionType.INCOME,
            Transaction.transaction_date <= end_date
        ).scalar() or Decimal('0.0')

        # 3. 計算從古至今，到該月底為止的所有支出總額
        total_expenditure = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.transaction_type == TransactionType.EXPENDITURE,
            Transaction.transaction_date <= end_date
        ).scalar() or Decimal('0.0')

        # 4. 直接加總，得到最準確的月底餘額
        month_end_balance = total_income + total_expenditure

        # --- ▲▲▲ 計算邏輯結束 ▲▲▲ ---

        # 檢查是否已存在該筆結轉紀錄，避免重複執行 (後續邏輯不變)
        if month == 12:
            next_month_date = date(year + 1, 1, 1)
        else:
            next_month_date = date(year, month + 1, 1)

        existing_settlement = Transaction.query.filter_by(
            transaction_date=next_month_date,
            description=f"[{current_user.display_name}] 執行 {year}年{month}月 結餘結轉",
        ).first()

        if existing_settlement:
            flash(f'錯誤：{year}年{month}月的結轉紀錄已存在，無法重複執行。', 'danger')
            return redirect(url_for('petty_cash.accounting_operations'))

        if month_end_balance < 0:
            flash(f'警告：{year}年{month}月結餘為負 (${month_end_balance})，無法進行結轉。請檢查帳目。', 'warning')
            return redirect(url_for('petty_cash.accounting_operations'))

        settlement_transaction = Transaction(
            transaction_type=TransactionType.INCOME,
            application_date=date.today(),
            transaction_date=next_month_date,
            applicant_id=current_user.id,
            description=f"[{current_user.display_name}] 執行 {year}年{month}月 結餘結轉",
            total_amount=month_end_balance,
            subtotal=month_end_balance,
            tax=0,
            tax_type=TaxType.TAX_EXEMPT,
            status=ApprovalStatus.APPROVED
        )
        db.session.add(settlement_transaction)
        db.session.commit()

        flash(f'成功！{year}年{month}月餘額 ${month_end_balance} 已成功結轉至 {next_month_date.strftime("%Y-%m-%d")}。', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'欄位 "{getattr(form, field).label.text}" 發生錯誤: {error}', 'danger')

    return redirect(url_for('petty_cash.accounting_operations'))

@petty_cash_bp.route('/tools/cash_count')
@login_required
def cash_count_tool():
    """顯示現金盤點工具頁面"""
    # --- ▼▼▼ 使用與首頁 index 完全相同的、最正確的計算邏輯 ▼▼▼ ---
    
    # 1. 找到最新的一筆結轉紀錄
    latest_settlement = Transaction.query.filter(
        Transaction.description.like('%餘額結轉%')
    ).order_by(Transaction.transaction_date.desc()).first()

    # 2. 決定計算的起始點（期初餘額）
    balance = Decimal('0.0')
    start_date = date(1900, 1, 1)
    if latest_settlement:
        balance = latest_settlement.total_amount
        start_date = latest_settlement.transaction_date

    # 3. 計算從起始點到今天為止，所有新發生的收支
    income_since_start = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.transaction_type == TransactionType.INCOME,
        Transaction.transaction_date > start_date,
        ~Transaction.description.like('%餘額結轉%')
    ).scalar() or Decimal('0.0')

    expenditure_since_start = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.transaction_type == TransactionType.EXPENDITURE,
        Transaction.transaction_date > start_date
    ).scalar() or Decimal('0.0')

    # 4. 得到最終正確的目前餘額
    current_balance = balance + income_since_start + expenditure_since_start
    
    return render_template('cash_count_tool.html', system_balance=current_balance)

@petty_cash_bp.route('/tools/cash_count/save', methods=['POST'])
@login_required
def save_cash_count():
    """儲存現金盤點紀錄"""
    try:
        session = CashCountSession(
            counted_total=Decimal(request.form.get('counted_total', 0)),
            system_balance=Decimal(request.form.get('system_balance', 0)),
            difference=Decimal(request.form.get('difference', 0)),
            user_id=current_user.id
        )
        db.session.add(session)
        
        denominations = [1000, 500, 100, 50, 10, 5, 1]
        for denom in denominations:
            # --- ▼▼▼ 這是修正的地方 ▼▼▼ ---
            # request.form.get(...) or 0 能確保在收到空字串''時，會用 0 來代替
            count = int(request.form.get(f'count_{denom}') or 0)
            # --- ▲▲▲ 修正結束 ▲▲▲ ---

            if count > 0:
                detail = CashCountDetail(
                    denomination=denom,
                    quantity=count,
                    subtotal=Decimal(denom * count),
                    session=session
                )
                db.session.add(detail)

        db.session.commit()
        flash('盤點紀錄已成功儲存！', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'儲存盤點紀錄時發生錯誤：{e}', 'danger')

    return redirect(url_for('petty_cash.cash_count_tool'))

@petty_cash_bp.route('/accounting/cash_count_history')
@login_required
def cash_count_history():
    """顯示現金盤點的歷史紀錄列表"""
    page = request.args.get('page', 1, type=int)
    
    # 查詢所有的盤點主表紀錄，並依日期排序
    sessions = CashCountSession.query.order_by(CashCountSession.count_date.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    return render_template('cash_count_history.html', sessions=sessions)

@petty_cash_bp.route('/accounting/cash_count_history/<int:session_id>')
@login_required
def cash_count_session_detail(session_id):
    """顯示單次現金盤點的詳情"""
    # 使用 get_or_404 可以更優雅地處理找不到紀錄的情況
    session = CashCountSession.query.get_or_404(session_id)
    
    # 將盤點明細轉換為字典，方便模板處理
    details_map = {detail.denomination: detail for detail in session.details}
    
    # 定義所有可能的面額，以確保模板中能完整顯示
    all_denominations = [1000, 500, 100, 50, 10, 5, 1]
    
    return render_template(
        'cash_count_session_detail.html', 
        session=session, 
        details_map=details_map,
        all_denominations=all_denominations
    )

@petty_cash_bp.route('/approvals')
@login_required
@manager_required
def approval_dashboard():
    """顯示待簽核儀表板"""
    page = request.args.get('page', 1, type=int)
    pending_transactions = Transaction.query.filter_by(
        status=ApprovalStatus.PENDING
    ).order_by(Transaction.application_date.asc()).paginate(
        page=page, per_page=15, error_out=False
    )
    # ▼▼▼ 在此處新增 ▼▼▼
    rejection_form = RejectionForm()
    
    return render_template(
        'approval_dashboard.html', 
        transactions=pending_transactions,
        rejection_form=rejection_form # <--- 將表單傳遞給樣板
    )

@petty_cash_bp.route('/transaction/<int:transaction_id>/submit', methods=['POST'])
@login_required
def submit_for_approval(transaction_id):
    """將草稿狀態的交易提交以供審核"""
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction:
        flash('找不到該筆交易。', 'danger')
        return redirect(url_for('petty_cash.index'))

    # 權限檢查：只有本人或主管可以提交
    if transaction.applicant_id != current_user.id and not current_user.is_manager():
         flash('您沒有權限提交此申請。', 'danger')
         return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction_id))

    if transaction.status in [ApprovalStatus.DRAFT, ApprovalStatus.REJECTED]:
        try:
            transaction.status = ApprovalStatus.PENDING
            # 當重新提交時，清除舊的簽核資訊，重新開始
            transaction.approver_id = None
            transaction.approval_date = None
            transaction.rejection_reason = None
            db.session.commit()
            flash('支出申請已成功提交，等候主管簽核。', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'提交失敗，錯誤：{e}', 'danger')
    else:
        flash('此交易無法提交，可能已在簽核中或已完成。', 'warning')

    return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction_id))

@petty_cash_bp.route('/transaction/<int:transaction_id>/approve', methods=['POST'])
@login_required
@manager_required
def approve_transaction(transaction_id):
    """同意一筆交易申請"""
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction:
        flash('找不到該筆交易。', 'danger')
        return redirect(url_for('petty_cash.approval_dashboard'))

    if transaction.status == ApprovalStatus.PENDING:
        try:
            transaction.status = ApprovalStatus.APPROVED
            transaction.approver_id = current_user.id
            transaction.approval_date = datetime.utcnow()
            db.session.commit()
            flash(f'交易 ID: {transaction.id} 已核准。', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'處理時發生錯誤：{e}', 'danger')
    else:
        flash('此交易不是待簽核狀態，無法操作。', 'warning')
        
    return redirect(url_for('petty_cash.approval_dashboard'))


@petty_cash_bp.route('/transaction/<int:transaction_id>/reject', methods=['POST'])
@login_required
@manager_required
def reject_transaction(transaction_id):
    """駁回一筆交易申請"""
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction:
        flash('找不到該筆交易。', 'danger')
        return redirect(url_for('petty_cash.approval_dashboard'))
    
    form = RejectionForm()
    if form.validate_on_submit():
        if transaction.status == ApprovalStatus.PENDING:
            try:
                transaction.status = ApprovalStatus.REJECTED
                transaction.approver_id = current_user.id
                transaction.approval_date = datetime.utcnow()
                transaction.rejection_reason = form.rejection_reason.data # <--- 儲存駁回理由
                db.session.commit()
                flash(f'交易 ID: {transaction.id} 已駁回。', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'處理時發生錯誤：{e}', 'danger')
        else:
            flash('此交易不是待簽核狀態，無法操作。', 'warning')
    else:
        flash('駁回時發生錯誤，請填寫駁回理由。', 'danger')
        
    return redirect(url_for('petty_cash.approval_dashboard'))

@petty_cash_bp.route('/accounting/cash_count_history/<int:session_id>/delete', methods=['POST'])
@login_required
@manager_required # 只有主管才能刪除盤點紀錄
def delete_cash_count_session(session_id):
    """刪除一筆現金盤點紀錄"""
    session_to_delete = db.session.get(CashCountSession, session_id)
    if not session_to_delete:
        flash('找不到該筆盤點紀錄。', 'danger')
        return redirect(url_for('petty_cash.cash_count_history'))
    
    try:
        # 因為我們在模型中設定了 cascade='all, delete-orphan'
        # 所以刪除主表的同時，所有關聯的明細也會被一併刪除
        db.session.delete(session_to_delete)
        db.session.commit()
        flash(f'盤點紀錄 (ID: {session_id}) 已成功刪除。', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除時發生錯誤：{e}', 'danger')
        
    return redirect(url_for('petty_cash.cash_count_history'))