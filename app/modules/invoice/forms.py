from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, DecimalField, SubmitField
from wtforms.validators import DataRequired, Optional, Length
from .models import InvoiceType

class InvoiceForm(FlaskForm):
    """發票登錄表單"""
    invoice_type = SelectField(
        '發票類型',
        choices=[(t.name, t.value) for t in InvoiceType],
        validators=[DataRequired()]
    )
    track = StringField('發票字軌', validators=[DataRequired(), Length(max=10)])
    number = StringField('發票號碼', validators=[DataRequired(), Length(max=20)])
    invoice_date = DateField('發票日期', validators=[DataRequired()], format='%Y-%m-%d')
    vendor_name = StringField('廠商名稱', validators=[Optional(), Length(max=100)])
    business_number = StringField('統一編號', validators=[Optional(), Length(max=20)])
    sales_amount = DecimalField('銷售額(未稅)', validators=[DataRequired()])
    tax_amount = DecimalField('稅額', validators=[DataRequired()])
    submit = SubmitField('儲存發票')