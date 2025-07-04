from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FieldList, FormField, DecimalField, DateField, SelectField, RadioField
from wtforms.validators import DataRequired, NumberRange, Optional
# 這裡只從 models 匯入我們需要用到的 Enum，而不是整個模型
from .models import TaxType, TaxCalculationMethod
from wtforms import SelectField
from datetime import datetime

class TransactionItemForm(FlaskForm):
    """子表單：用於單個明細項目"""
    class Meta:
        csrf = False  # 子表單通常不需要獨立的 CSRF 保護
    item_name = StringField('品名：', validators=[DataRequired()])
    quantity = DecimalField('數量：', validators=[DataRequired(), NumberRange(min=0)])
    unit = StringField('單位：')
    unit_price = DecimalField('單價：', validators=[DataRequired()])


class ExpenditureForm(FlaskForm):
    """主表單：新增一筆支出"""
    application_date = DateField('申請日期：', validators=[DataRequired()], format='%Y-%m-%d')
    erp_document_number = StringField('ERP 單號：', validators=[Optional()])
    transaction_date = DateField('交易日期：', validators=[DataRequired()], format='%Y-%m-%d')
    applicant_name = StringField('申請人：', validators=[DataRequired()])
    description = StringField('摘要：', validators=[DataRequired()])
    
    tax_type = SelectField(
        '稅別：',
        choices=[(t.name, t.value) for t in TaxType],
        validators=[DataRequired()]
    )
    tax_calculation_method = RadioField(
        '計稅方式：',
        choices=[(t.name, t.value) for t in TaxCalculationMethod],
        default=TaxCalculationMethod.EXCLUSIVE.name,
        validators=[Optional()]
    )
    items = FieldList(FormField(TransactionItemForm), min_entries=0)
    submit = SubmitField('新增支出')

class IncomeForm(FlaskForm):
    """新增一筆收入的表單"""
    application_date = DateField('申請日期：', validators=[DataRequired()], format='%Y-%m-%d')
    transaction_date = DateField('交易日期：', validators=[DataRequired()], format='%Y-%m-%d')
    applicant_name = StringField('經手人/來源：', validators=[DataRequired()])
    description = StringField('摘要：', validators=[DataRequired()])
    total_amount = DecimalField('收入金額：', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('新增收入')

class MonthEndSettlementForm(FlaskForm):
    """月結作業表單"""
    current_year = datetime.utcnow().year
    # 建立從今年到過去五年的年份選項
    year = SelectField(
        '年份',
        choices=[(str(y), f'{y}年') for y in range(current_year, current_year - 5, -1)],
        validators=[DataRequired()]
    )
    # 建立月份選項
    month = SelectField(
        '月份',
        choices=[(str(m), f'{m}月') for m in range(1, 13)],
        validators=[DataRequired()]
    )
    submit = SubmitField('執行結轉')