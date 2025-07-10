import enum
from app import db, login_manager, bcrypt  # 1. bcrypt 已在這裡，很好！
from flask_login import UserMixin
# from werkzeug.security import generate_password_hash, check_password_hash  # 2. 我們不再需要 werkzeug 了，可以刪除

class UserRole(enum.Enum):
    USER = '一般使用者'
    MANAGER = '主管'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    
    account_id = db.Column(db.String(64), index=True, unique=True, nullable=False, comment='登入用帳號 (例如: C0007)')
    display_name = db.Column(db.String(100), nullable=False, comment='顯示用姓名 (例如: 施宏岳)')

    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    # 3. 將長度設為 60，這是 bcrypt 雜湊值的標準長度
    password_hash = db.Column(db.String(60), nullable=False) 
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.USER, server_default=UserRole.USER.name)

    # --- ▼▼▼ 4. 修改點：將密碼設定函式改用 bcrypt ▼▼▼ ---
    def set_password(self, password):
        """使用 bcrypt 來加密密碼"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    # --- ▼▼▼ 5. 修改點：將密碼檢查函式改用 bcrypt ▼▼▼ ---
    def check_password(self, password):
        """使用 bcrypt 來驗證密碼"""
        return bcrypt.check_password_hash(self.password_hash, password)

    def is_manager(self):
        """檢查使用者角色是否為主管"""
        return self.role == UserRole.MANAGER

    def __repr__(self):
        return f'<User {self.display_name}>'