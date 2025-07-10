from flask_wtf import FlaskForm
from wtforms import StringField, DateField, DecimalField, FieldList, FormField, RadioField, SelectField, SubmitField, TextAreaField
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms.validators import DataRequired, Optional, Length
from .models import Category

def category_query():
    """查詢所有費用分類，並依名稱排序"""
    return Category.query.order_by(Category.name).all()

class ItemForm(FlaskForm):
    """支出申請中的單一項目子表單"""
    item_name = StringField('品名', validators=[DataRequired(message="請填寫品名")])
    quantity = DecimalField('數量', validators=[DataRequired(message="請填寫數量")], places=2)
    unit = StringField('單位')
    unit_price = DecimalField('單價', validators=[DataRequired(message="請填寫單價")], places=2)

class ExpenditureForm(FlaskForm):
    """支出申請主表單"""
    application_date = DateField('申請日期', validators=[DataRequired()], format='%Y-%m-%d')
    transaction_date = DateField('交易日期', validators=[DataRequired()], format='%Y-%m-%d')
    erp_document_number = StringField('ERP對應單號', validators=[Optional()])
    applicant_name = StringField('申請人')
    description = StringField('摘要說明', validators=[DataRequired(message="請填寫摘要說明")])
    category_id = QuerySelectField(
        '費用分類',
        query_factory=category_query,
        get_label='name',
        allow_blank=True,
        blank_text='-- 請選擇分類 --',
        validators=[DataRequired(message="請選擇一個費用分類")]
    )
    tax_type = SelectField(
        '稅別',
        choices=[('TAXABLE', '應稅'), ('ZERO_TAX', '零稅率'), ('TAX_EXEMPT', '免稅')],
        validators=[DataRequired()]
    )
    tax_calculation_method = RadioField(
        '計稅方式',
        choices=[('EXCLUSIVE', '稅外加'), ('INCLUSIVE', '稅內含')],
        validators=[Optional()]
    )
    items = FieldList(FormField(ItemForm), min_entries=0, label="明細項目")
    submit = SubmitField('送出申請')

class IncomeForm(FlaskForm):
    """收入登錄表單"""
    application_date = DateField('申請日期', validators=[DataRequired()], format='%Y-%m-%d')
    transaction_date = DateField('入帳日期', validators=[DataRequired()], format='%Y-%m-%d')
    description = StringField('摘要說明', validators=[DataRequired(message="請填寫摘要說明")])
    total_amount = DecimalField('收入金額', validators=[DataRequired(message="請填寫收入金額")], places=2)
    submit = SubmitField('登錄收入')

class MonthEndSettlementForm(FlaskForm):
    """月結作業表單"""
    year = StringField('年份', validators=[DataRequired()])
    month = StringField('月份', validators=[DataRequired()])
    submit = SubmitField('執行月結')

class RejectionForm(FlaskForm):
    """駁回理由表單"""
    rejection_reason = TextAreaField('駁回理由', validators=[DataRequired(message="請填寫駁回理由")])
    submit = SubmitField('確認駁回')

class CategoryForm(FlaskForm):
    """費用分類表單"""
    name = StringField('分類名稱', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('新增分類')