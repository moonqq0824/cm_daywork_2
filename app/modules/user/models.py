import enum # <--- 1. 新增匯入 enum
from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# ▼▼▼ 2. 新增一個 UserRole 的枚舉(Enum) ▼▼▼
class UserRole(enum.Enum):
    USER = '一般使用者'
    MANAGER = '主管'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    
    # ▼▼▼ 3. 新增 role 欄位 ▼▼▼
    #    我們設定預設值為 'USER'，這樣所有現有的和未來新建的帳號，預設都是一般使用者
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.USER, server_default=UserRole.USER.name)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # ▼▼▼ 4. (可選，但建議) 新增一個方便的權限檢查方法 ▼▼▼
    def is_manager(self):
        return self.role == UserRole.MANAGER

    def __repr__(self):
        return f'<User {self.username}>'