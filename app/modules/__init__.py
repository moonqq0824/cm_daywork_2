from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import os

# 1. 將擴充套件的實體化放到最外層
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()

# 告訴 LoginManager 登入頁面在哪裡
login_manager.login_view = 'user.login'
# 自訂登入提示訊息
login_manager.login_message = '請先登入以存取此頁面。'
login_manager.login_message_category = 'info'


def create_app():
    """
    應用程式工廠函式
    """
    # 2. 建立 app 實體
    app = Flask(__name__)
    
    # 3. 載入設定
    # 建議將金鑰等敏感資訊存在環境變數中，而不是寫死在程式碼裡
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_very_secret_key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 4. 初始化擴充套件
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # 5. 在工廠函式內部，延遲載入並註冊藍圖 (這是解決循環依賴的關鍵！)
    from app.modules.user.routes import user_bp
    from app.modules.petty_cash.routes import petty_cash_bp
    # from app.modules.invoice_management.routes import invoice_management_bp # 如果您有這個模組，也一併打開
    
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(petty_cash_bp, url_prefix='/petty_cash')
    # app.register_blueprint(invoice_management_bp, url_prefix='/invoice')

    return app