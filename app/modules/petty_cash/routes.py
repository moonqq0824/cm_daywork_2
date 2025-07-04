from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from decimal import Decimal, ROUND_HALF_UP
from flask_login import login_required
from app import db
from .models import Transaction, TransactionItem, TransactionType, TaxType, TaxCalculationMethod, ApprovalStatus
from .forms import ExpenditureForm, IncomeForm, MonthEndSettlementForm
from datetime import date, datetime, timedelta
from sqlalchemy import func, extract
import calendar # <--- 加入這個標準函式庫

petty_cash_bp = Blueprint('petty_cash', __name__)

@petty_cash_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    transactions_query = Transaction.query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
    transactions = transactions_query.paginate(page=page, per_page=10)
    
    # 計算總餘額
    total_income = db.session.query(func.sum(Transaction.total_amount)).filter(Transaction.transaction_type == TransactionType.INCOME).scalar() or Decimal('0.0')
    total_expenditure = db.session.query(func.sum(Transaction.total_amount)).filter(Transaction.transaction_type == TransactionType.EXPENDITURE).scalar() or Decimal('0.0')
    balance = total_income + total_expenditure  # 支出為負數，所以用加法

    return render_template('petty_cash_index.html', transactions=transactions, balance=balance, TransactionType=TransactionType)

@petty_cash_bp.route('/transaction/<int:transaction_id>')
@login_required
def transaction_detail(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction:
        flash('找不到該筆交易。', 'danger')
        return redirect(url_for('petty_cash.index'))
    return render_template('transaction_detail.html', transaction=transaction, TransactionType=TransactionType)

@petty_cash_bp.route('/expenditure/add', methods=['GET', 'POST'])
@login_required
def add_expenditure():
    form = ExpenditureForm()
    if request.method == 'GET':
        form.application_date.data = date.today()
        form.transaction_date.data = date.today()

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
                applicant_name=form.applicant_name.data,
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
            
    return render_template('edit_transaction.html', form=form, transaction_id=transaction_id)


@petty_cash_bp.route('/income/add', methods=['GET', 'POST'])
@login_required
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
                applicant_name=form.applicant_name.data,
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

        # 1. 計算指定月份的期末餘額
        # 取得該月最後一天
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)

        # 計算到該月底為止的所有收入和支出
        total_income = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.transaction_type == TransactionType.INCOME,
            Transaction.transaction_date <= end_date
        ).scalar() or Decimal('0.0')

        total_expenditure = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.transaction_type == TransactionType.EXPENDITURE,
            Transaction.transaction_date <= end_date
        ).scalar() or Decimal('0.0')
        
        month_end_balance = total_income + total_expenditure

        # 2. 新增次月一號的期初餘額紀錄
        # 計算次月一號的日期
        if month == 12:
            next_month_date = date(year + 1, 1, 1)
        else:
            next_month_date = date(year, month + 1, 1)

        # 檢查是否已存在該筆結轉紀錄，避免重複執行
        existing_settlement = Transaction.query.filter_by(
            transaction_date=next_month_date,
            description=f'{year}年{month}月 餘額結轉'
        ).first()

        if existing_settlement:
            flash(f'錯誤：{year}年{month}月的結轉紀錄已存在，無法重複執行。', 'danger')
            return redirect(url_for('petty_cash.accounting_operations'))

        if month_end_balance < 0:
            flash(f'警告：{year}年{month}月結餘為負 (${month_end_balance})，無法進行結轉。請檢查帳目。', 'warning')
            return redirect(url_for('petty_cash.accounting_operations'))

        # 建立新的收入交易
        settlement_transaction = Transaction(
            transaction_type=TransactionType.INCOME,
            application_date=date.today(),
            transaction_date=next_month_date,
            applicant_name='系統自動作業',
            description=f'{year}年{month}月 餘額結轉',
            total_amount=month_end_balance,
            subtotal=month_end_balance,
            tax=0,
            tax_type=TaxType.TAX_EXEMPT,
            status=ApprovalStatus.APPROVED # 自動作業直接核准
        )
        db.session.add(settlement_transaction)
        db.session.commit()

        flash(f'成功！{year}年{month}月餘額 ${month_end_balance} 已成功結轉至 {next_month_date.strftime("%Y-%m-%d")}。', 'success')

    else:
        # 如果表單驗證失敗
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'欄位 "{getattr(form, field).label.text}" 發生錯誤: {error}', 'danger')

    return redirect(url_for('petty_cash.accounting_operations'))