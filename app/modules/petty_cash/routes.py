from flask import Blueprint, render_template, redirect, url_for, flash, request
from decimal import Decimal, ROUND_HALF_UP
from flask_login import login_required, current_user
from app import db
from .models import Transaction, TransactionItem, TransactionType, TaxType, TaxCalculationMethod, ApprovalStatus, CashCountSession, CashCountDetail, Category
from .forms import ExpenditureForm, IncomeForm, MonthEndSettlementForm, RejectionForm, CategoryForm, ItemForm
from datetime import date, datetime, timedelta
from sqlalchemy import func, extract
from app.modules.user.routes import manager_required
import json
import calendar

petty_cash_bp = Blueprint('petty_cash', __name__)

# --- ▼▼▼ 新增：輔助函式 ▼▼▼ ---

def _calculate_current_balance():
    """計算當前的系統總餘額"""
    latest_settlement = Transaction.query.filter(
        Transaction.description.like('%餘額結轉%')
    ).order_by(Transaction.transaction_date.desc()).first()

    balance = Decimal('0.0')
    start_date = date(1900, 1, 1)
    if latest_settlement:
        balance = latest_settlement.total_amount
        start_date = latest_settlement.transaction_date

    income_since_start = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.transaction_type == TransactionType.INCOME,
        Transaction.transaction_date > start_date,
        ~Transaction.description.like('%餘額結轉%')
    ).scalar() or Decimal('0.0')

    expenditure_since_start = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.transaction_type == TransactionType.EXPENDITURE,
        Transaction.transaction_date > start_date
    ).scalar() or Decimal('0.0')

    return balance + income_since_start + expenditure_since_start

def _calculate_tax_and_total(base_amount, tax_type_str, tax_calc_method_str):
    """根據稅別和計稅方式計算稅後金額"""
    tax_rate = Decimal('0.05')
    subtotal, tax, total_amount = Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

    if tax_type_str == TaxType.TAXABLE.name:
        if tax_calc_method_str == TaxCalculationMethod.EXCLUSIVE.name:
            subtotal = base_amount
            tax = (subtotal * tax_rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            total_amount = subtotal + tax
        elif tax_calc_method_str == TaxCalculationMethod.INCLUSIVE.name:
            total_amount = base_amount
            # 修正：內含稅的未稅額計算應該用 total_amount 來除
            subtotal = (total_amount / (1 + tax_rate)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            tax = total_amount - subtotal
        else: # 如果沒有選擇計稅方式，預設為稅外加
            subtotal = base_amount
            tax = (subtotal * tax_rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            total_amount = subtotal + tax
    else: # 免稅或零稅率
        subtotal = base_amount
        tax = Decimal('0.0')
        total_amount = base_amount
        
    return subtotal, tax, total_amount

# --- ▲▲▲ 輔助函式結束 ▲▲▲ ---


@petty_cash_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    transactions = Transaction.query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).paginate(page=page, per_page=10, error_out=False)
    current_balance = _calculate_current_balance()
    return render_template('petty_cash_index.html', transactions=transactions, balance=current_balance, TransactionType=TransactionType, ApprovalStatus=ApprovalStatus)

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
        ApprovalStatus=ApprovalStatus
    )

@petty_cash_bp.route('/expenditure/add', methods=['GET', 'POST'])
@login_required
def add_expenditure():
    form = ExpenditureForm(request.form)
    
    if request.method == 'POST':
        # 在驗證前，先過濾掉所有空白的明細
        valid_items_data = [item for item in form.items.data if item.get('item_name')]
        while len(form.items.entries) > 0:
            form.items.pop_entry()
        for item_data in valid_items_data:
            form.items.append_entry(item_data)

        if form.validate_on_submit():
            if not valid_items_data:
                flash('請至少新增一筆有效的項目明細。', 'warning')
                return render_template('add_expenditure.html', form=form)
            try:
                base_amount = sum(Decimal(item['quantity'] or 0) * Decimal(item['unit_price'] or 0) for item in valid_items_data)
                subtotal, tax, total_amount = _calculate_tax_and_total(base_amount, form.tax_type.data, form.tax_calculation_method.data)
                
                new_transaction = Transaction(
                    transaction_type=TransactionType.EXPENDITURE,
                    application_date=form.application_date.data,
                    erp_document_number=form.erp_document_number.data,
                    status=ApprovalStatus.DRAFT,
                    transaction_date=form.transaction_date.data,
                    applicant_id=current_user.id,
                    description=form.description.data,
                    category_id=form.category_id.data.id,
                    tax_type=TaxType[form.tax_type.data],
                    tax_calculation_method=TaxCalculationMethod[form.tax_calculation_method.data] if form.tax_calculation_method.data else None,
                    subtotal=subtotal, tax=tax, total_amount=-total_amount,
                )
                
                for item_data in valid_items_data:
                    db.session.add(TransactionItem(
                        item_name=item_data['item_name'],
                        quantity=Decimal(item_data['quantity'] or 0),
                        unit=item_data['unit'],
                        unit_price=Decimal(item_data['unit_price'] or 0),
                        line_total=Decimal(item_data['quantity'] or 0) * Decimal(item_data['unit_price'] or 0),
                        transaction=new_transaction
                    ))
                
                db.session.add(new_transaction)
                db.session.commit()
                flash('支出紀錄已成功新增！', 'success')
                return redirect(url_for('petty_cash.index'))
            except Exception as e:
                db.session.rollback()
                flash(f'新增失敗，發生未知錯誤：{e}', 'danger')
    
    # 如果是第一次載入頁面 (GET request)
    if request.method == 'GET':
        form.application_date.data = date.today()
        form.transaction_date.data = date.today()
        form.applicant_name.data = current_user.display_name

    return render_template('add_expenditure.html', form=form)

@petty_cash_bp.route('/transaction/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction or transaction.transaction_type != TransactionType.EXPENDITURE:
        flash('找不到該筆支出紀錄。', 'danger')
        return redirect(url_for('petty_cash.index'))
    
    is_editable = (transaction.status in [ApprovalStatus.DRAFT, ApprovalStatus.REJECTED] and transaction.applicant_id == current_user.id) or current_user.is_manager()
    if not is_editable:
        flash('此單據狀態無法編輯。', 'warning')
        return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction_id))
    
    form = ExpenditureForm(obj=transaction)

    if form.validate_on_submit():
        try:
            base_amount = sum(Decimal(item['quantity'] or 0) * Decimal(item['unit_price'] or 0) for item in form.items.data)
            subtotal, tax, total_amount = _calculate_tax_and_total(base_amount, form.tax_type.data, form.tax_calculation_method.data)

            # 更新主表資料
            transaction.application_date = form.application_date.data
            transaction.erp_document_number = form.erp_document_number.data
            transaction.transaction_date = form.transaction_date.data
            transaction.description = form.description.data
            # --- ▼▼▼ 修改點 3：更新 Transaction 主檔的 category_id ▼▼▼ ---
            transaction.category_id = form.category_id.data.id
            transaction.tax_type = TaxType[form.tax_type.data]
            transaction.tax_calculation_method = TaxCalculationMethod[form.tax_calculation_method.data] if form.tax_calculation_method.data else None
            transaction.subtotal, transaction.tax, transaction.total_amount = subtotal, tax, -total_amount
            
            # 清空舊明細，建立新明細
            for item in transaction.items:
                db.session.delete(item)
            db.session.flush()

            for item_data in form.items.data:
                new_item = TransactionItem(
                    item_name=item_data['item_name'],
                    quantity=Decimal(item_data['quantity']),
                    unit=item_data['unit'],
                    unit_price=Decimal(item_data['unit_price']),
                    line_total=Decimal(item_data['quantity']) * Decimal(item_data['unit_price']),
                    transaction_id=transaction.id
                )
                db.session.add(new_item)
            
            db.session.commit()
            flash('支出紀錄已成功更新！', 'success')
            return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction.id))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗，錯誤：{e}', 'danger')

    elif request.method == 'GET':
        form.applicant_name.data = transaction.applicant.display_name
        form.tax_type.data = transaction.tax_type.name
        if transaction.tax_calculation_method:
            form.tax_calculation_method.data = transaction.tax_calculation_method.name
        # 載入頁面時，將現有的分類填入表單
        if transaction.category:
            form.category_id.data = transaction.category

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
                status=ApprovalStatus.APPROVED # 收入預設為已核准
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
    
    # 權限檢查：只有草稿狀態的單據可以由本人或主管刪除
    can_delete = transaction.status == ApprovalStatus.DRAFT and (transaction.applicant_id == current_user.id or current_user.is_manager())
    if not can_delete:
        flash('此申請已送出或已核准，無法刪除。', 'warning')
        return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction_id))

    try:
        # 刪除關聯的明細
        for item in transaction.items:
            db.session.delete(item)
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

        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)

        total_income = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.transaction_type == TransactionType.INCOME,
            Transaction.transaction_date <= end_date
        ).scalar() or Decimal('0.0')

        total_expenditure = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.transaction_type == TransactionType.EXPENDITURE,
            Transaction.transaction_date <= end_date
        ).scalar() or Decimal('0.0')

        month_end_balance = total_income + total_expenditure

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
    # --- 優化：直接呼叫輔助函式 ---
    current_balance = _calculate_current_balance()
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
            count_str = request.form.get(f'count_{denom}')
            # 確保輸入是數字且大於0
            if count_str and count_str.isdigit() and int(count_str) > 0:
                count = int(count_str)
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
    sessions = CashCountSession.query.order_by(CashCountSession.count_date.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    return render_template('cash_count_history.html', sessions=sessions)

@petty_cash_bp.route('/accounting/cash_count_history/<int:session_id>')
@login_required
def cash_count_session_detail(session_id):
    """顯示單次現金盤點的詳情"""
    session = CashCountSession.query.get_or_404(session_id)
    details_map = {detail.denomination: detail for detail in session.details}
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
    rejection_form = RejectionForm()
    
    return render_template(
        'approval_dashboard.html', 
        transactions=pending_transactions,
        rejection_form=rejection_form
    )

@petty_cash_bp.route('/transaction/<int:transaction_id>/submit', methods=['POST'])
@login_required
def submit_for_approval(transaction_id):
    """將草稿狀態的交易提交以供審核"""
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction:
        flash('找不到該筆交易。', 'danger')
        return redirect(url_for('petty_cash.index'))

    if transaction.applicant_id != current_user.id and not current_user.is_manager():
         flash('您沒有權限提交此申請。', 'danger')
         return redirect(url_for('petty_cash.transaction_detail', transaction_id=transaction_id))

    if transaction.status in [ApprovalStatus.DRAFT, ApprovalStatus.REJECTED]:
        try:
            transaction.status = ApprovalStatus.PENDING
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
            transaction.approval_date = datetime.utcnow().date() # 儲存日期即可
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
                transaction.approval_date = datetime.utcnow().date() # 儲存日期即可
                transaction.rejection_reason = form.rejection_reason.data
                db.session.commit()
                flash(f'交易 ID: {transaction.id} 已駁回。', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'處理時發生錯誤：{e}', 'danger')
        else:
            flash('此交易不是待簽核狀態，無法操作。', 'warning')
    else:
        # 如果表單驗證失敗，顯示具體的錯誤訊息
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'駁回失敗：{error}', 'danger')
        
    return redirect(url_for('petty_cash.approval_dashboard'))

@petty_cash_bp.route('/accounting/cash_count_history/<int:session_id>/delete', methods=['POST'])
@login_required
@manager_required
def delete_cash_count_session(session_id):
    """刪除一筆現金盤點紀錄"""
    session_to_delete = db.session.get(CashCountSession, session_id)
    if not session_to_delete:
        flash('找不到該筆盤點紀錄。', 'danger')
        return redirect(url_for('petty_cash.cash_count_history'))
    
    try:
        db.session.delete(session_to_delete)
        db.session.commit()
        flash(f'盤點紀錄 (ID: {session_id}) 已成功刪除。', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除時發生錯誤：{e}', 'danger')
        
    return redirect(url_for('petty_cash.cash_count_history'))


@petty_cash_bp.route('/categories')
@login_required
@manager_required
def category_management():
    """顯示費用分類管理頁面"""
    categories = Category.query.order_by(Category.name).all()
    form = CategoryForm()
    return render_template('category_management.html', categories=categories, form=form)

@petty_cash_bp.route('/categories/add', methods=['POST'])
@login_required
@manager_required
def add_category():
    """新增費用分類"""
    form = CategoryForm()
    if form.validate_on_submit():
        existing_category = Category.query.filter_by(name=form.name.data).first()
        if existing_category:
            flash('錯誤：該分類名稱已存在。', 'danger')
        else:
            new_category = Category(name=form.name.data)
            db.session.add(new_category)
            db.session.commit()
            flash('新的費用分類已成功新增！', 'success')
    return redirect(url_for('petty_cash.category_management'))

@petty_cash_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
@login_required
@manager_required
def delete_category(category_id):
    """刪除費用分類"""
    category_to_delete = db.session.get(Category, category_id)
    if category_to_delete:
        if category_to_delete.items:
            flash('錯誤：無法刪除此分類，因為已有支出項目正在使用它。', 'danger')
        else:
            db.session.delete(category_to_delete)
            db.session.commit()
            flash('費用分類已成功刪除。', 'success')
    else:
        flash('找不到該分類。', 'danger')
    return redirect(url_for('petty_cash.category_management'))

# 報表用 #
@petty_cash_bp.route('/reports/expense_by_category', methods=['GET'])
@login_required
@manager_required
def report_expense_by_category():
    """費用分類報表頁面"""
    try:
        year = int(request.args.get('year', date.today().year))
        month = int(request.args.get('month', date.today().month))
    except (ValueError, TypeError):
        year = date.today().year
        month = date.today().month
        flash('日期參數格式錯誤，已顯示當前月份報表。', 'warning')

    # --- ▼▼▼ 修改點 4：修改報表查詢邏輯 ▼▼▼ ---
    # 現在直接從 Transaction 查詢，不再需要經過 TransactionItem
    report_data_query = db.session.query(
        Category.name,
        func.sum(Transaction.total_amount).label('total_spent')
    ).join(Transaction.category).filter(
        Transaction.transaction_type == TransactionType.EXPENDITURE,
        Transaction.status == ApprovalStatus.APPROVED,
        extract('year', Transaction.transaction_date) == year,
        extract('month', Transaction.transaction_date) == month
    ).group_by(Category.name).order_by(
        func.sum(Transaction.total_amount).desc()
    ).all()

    # 報表金額應為正數
    total_expense = -sum(item.total_spent for item in report_data_query)
    
    chart_labels = [item[0] for item in report_data_query]
    chart_values = [float(-item[1]) for item in report_data_query]

    chart_data = {
        'labels': json.dumps(chart_labels, ensure_ascii=False),
        'values': json.dumps(chart_values)
    }

    table_data = []
    if total_expense > 0:
        for category_name, total_spent in report_data_query:
            amount = -total_spent
            percentage = (amount / total_expense * 100)
            table_data.append({
                'category': category_name,
                'total': amount,
                'percentage': f"{percentage:.2f}%"
            })

    return render_template(
        'report_expense_by_category.html',
        year=year,
        month=month,
        total_expense=total_expense,
        table_data=table_data,
        chart_data=chart_data
    )