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
    
    # --- ▼▼▼ 這是我們的修改重點 ▼▼▼ ---
    # 1. 移除 applicant_name = db.Column(db.String(100), nullable=False)
    # 2. 新增 applicant_id，並設定它關聯到 users.id
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='申請人ID')
    # --- ▲▲▲ 修改結束 ▲▲▲ ---

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

    # --- ▼▼▼ 這是我們的修改重點 ▼▼▼ ---
    # 3. 新增 applicant 關聯，讓我們可以透過 transaction.applicant.username 輕鬆取得申請人姓名
    applicant = db.relationship('User', backref='applied_transactions', foreign_keys=[applicant_id])
    # --- ▲▲▲ 修改結束 ▲▲▲ ---

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
    
class CashCountSession(db.Model):
    """盤點工作階段主表"""
    __tablename__ = 'cash_count_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    count_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='盤點日期')
    counted_total = db.Column(db.Numeric(precision=10, scale=2), nullable=False, comment='盤點總額')
    system_balance = db.Column(db.Numeric(precision=10, scale=2), nullable=False, comment='系統帳上餘額')
    difference = db.Column(db.Numeric(precision=10, scale=2), nullable=False, comment='差額')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='操作人員ID')
    
    # 建立與 User 的關聯
    user = db.relationship('User', backref='cash_count_sessions')
    # 建立與盤點明細的關聯
    details = db.relationship('CashCountDetail', backref='session', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<CashCountSession {self.id} on {self.count_date}>'

class CashCountDetail(db.Model):
    """盤點工作階段明細表"""
    __tablename__ = 'cash_count_details'

    id = db.Column(db.Integer, primary_key=True)
    denomination = db.Column(db.Integer, nullable=False, comment='面額 (例如: 1000, 500)')
    quantity = db.Column(db.Integer, nullable=False, comment='張數/個數')
    subtotal = db.Column(db.Numeric(precision=10, scale=2), nullable=False, comment='該面額小計')
    session_id = db.Column(db.Integer, db.ForeignKey('cash_count_sessions.id'), nullable=False)

    def __repr__(self):
        return f'<CashCountDetail {self.denomination} x {self.quantity}>'
