import enum
from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class UserRole(enum.Enum):
    USER = '一般使用者'
    MANAGER = '主管'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    
    # ▼▼▼ 這是我們的修改重點 ▼▼▼
    account_id = db.Column(db.String(64), index=True, unique=True, nullable=False, comment='登入用帳號 (例如: C0007)')
    display_name = db.Column(db.String(100), nullable=False, comment='顯示用姓名 (例如: 施宏岳)')
    # ▲▲▲ 修改結束 ▲▲▲

    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.USER, server_default=UserRole.USER.name)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_manager(self):
        return self.role == UserRole.MANAGER

    def __repr__(self):
        return f'<User {self.display_name}>'