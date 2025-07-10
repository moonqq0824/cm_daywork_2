import enum
from app import db
from datetime import datetime

class InvoiceType(enum.Enum):
    """發票類型"""
    CASH_REGISTER = '三聯式收銀機'
    DUPLICATE = '二聯式'
    TRIPLICATE = '三聯式'
    ELECTRONIC = '電子發票'
    OTHER = '其他'

class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    invoice_type = db.Column(db.Enum(InvoiceType), nullable=False, default=InvoiceType.CASH_REGISTER, comment='發票類型')
    track = db.Column(db.String(10), nullable=False, comment='發票字軌 (例如: MU)')
    number = db.Column(db.String(20), nullable=False, unique=True, comment='發票號碼')
    invoice_date = db.Column(db.Date, nullable=False, comment='發票日期')
    vendor_name = db.Column(db.String(100), nullable=True, comment='廠商名稱')
    business_number = db.Column(db.String(20), nullable=True, comment='統一編號')
    sales_amount = db.Column(db.Numeric(precision=10, scale=2), nullable=False, comment='銷售額 (未稅)')
    tax_amount = db.Column(db.Numeric(precision=10, scale=2), nullable=False, comment='稅額')
    total_amount = db.Column(db.Numeric(precision=10, scale=2), nullable=False, comment='總金額')

    # 關聯到上傳者
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='登錄人員ID')
    uploader = db.relationship('User', backref='uploaded_invoices')

    # 可選：關聯到零用金交易
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True, comment='對應的零用金交易ID')
    transaction = db.relationship('Transaction', backref='invoices')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Invoice {self.track}-{self.number}>'