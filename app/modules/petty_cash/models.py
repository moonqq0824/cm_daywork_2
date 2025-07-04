import enum
from datetime import datetime
from app import db

class TransactionType(enum.Enum):
    INCOME = '收入'
    EXPENDITURE = '支出'

class TaxType(enum.Enum):
    TAXABLE = '應稅'
    ZERO_TAX = '零稅率'
    TAX_EXEMPT = '免稅'

class TaxCalculationMethod(enum.Enum):
    EXCLUSIVE = '稅外加'
    INCLUSIVE = '稅內含'

class ApprovalStatus(enum.Enum):
    DRAFT = '草稿'
    PENDING = '待簽核'
    APPROVED = '已核准'
    REJECTED = '已駁回'

class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.Enum(TransactionType), nullable=False)
    tax_type = db.Column(db.Enum(TaxType), nullable=False, default=TaxType.TAXABLE, server_default=TaxType.TAXABLE.name)
    tax_calculation_method = db.Column(db.Enum(TaxCalculationMethod), nullable=True)
    transaction_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    applicant_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    subtotal = db.Column(db.Numeric(precision=10, scale=2), default=0.00)
    tax = db.Column(db.Numeric(precision=10, scale=2), default=0.00)
    total_amount = db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    
    erp_document_number = db.Column(db.String(100), nullable=True, comment='ERP對應單號')
    application_date = db.Column(db.Date, nullable=False, default=datetime.utcnow, comment='申請日期')
    status = db.Column(db.Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.DRAFT, server_default=ApprovalStatus.DRAFT.name, comment='簽核狀態')
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='簽核主管ID')
    approval_date = db.Column(db.Date, nullable=True, comment='簽核日期')

    items = db.relationship('TransactionItem', backref='transaction', lazy=True, cascade='all, delete-orphan')
    approver = db.relationship('User', backref='approved_transactions', foreign_keys=[approver_id])

    def __repr__(self):
        return f"<Transaction {self.id}: {self.description}>"

class TransactionItem(db.Model):
    __tablename__ = 'transaction_items'
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    unit = db.Column(db.String(20), nullable=True)
    unit_price = db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    line_total = db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)

    def __repr__(self):
        return f"<TransactionItem {self.id}: {self.item_name}>"