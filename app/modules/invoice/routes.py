from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from .models import Invoice, InvoiceType
from .forms import InvoiceForm
from decimal import Decimal

invoice_bp = Blueprint('invoice', __name__, url_prefix='/invoice')

@invoice_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        total = form.sales_amount.data + form.tax_amount.data
        new_invoice = Invoice(
            invoice_type=InvoiceType[form.invoice_type.data],
            track=form.track.data,
            number=form.number.data,
            invoice_date=form.invoice_date.data,
            vendor_name=form.vendor_name.data,
            business_number=form.business_number.data,
            sales_amount=form.sales_amount.data,
            tax_amount=form.tax_amount.data,
            total_amount=total,
            uploader_id=current_user.id
        )
        db.session.add(new_invoice)
        db.session.commit()
        flash('發票已成功登錄！', 'success')
        return redirect(url_for('invoice.report'))
    return render_template('add_invoice.html', form=form)

@invoice_bp.route('/report')
@login_required
def report():
    # 接收查詢參數，例如 ?year=2025&month=5
    year = request.args.get('year', type=int, default=datetime.now().year)
    month = request.args.get('month', type=int, default=datetime.now().month)

    # 查詢指定月份的發票，並按類型和日期排序
    invoices = Invoice.query.filter(
        db.extract('year', Invoice.invoice_date) == year,
        db.extract('month', Invoice.invoice_date) == month
    ).order_by(Invoice.invoice_type, Invoice.invoice_date).all()

    # 將發票按類型分組
    grouped_invoices = {}
    for inv in invoices:
        if inv.invoice_type.value not in grouped_invoices:
            grouped_invoices[inv.invoice_type.value] = []
        grouped_invoices[inv.invoice_type.value].append(inv)
        
    return render_template('invoice_report.html', grouped_invoices=grouped_invoices, year=year, month=month)