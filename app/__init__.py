from flask import Flask, redirect, url_for # <-- 1. 在這裡新增 redirect 和 url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()

login_manager.login_view = 'user.login'
login_manager.login_message = '請先登入以存取此頁面。'
login_manager.login_message_category = 'info'


def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_very_secret_key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # --- ▼▼▼ 2. 在這裡新增首頁路由 ▼▼▼ ---
    @app.route('/')
    def index():
        # 自動重新導向到零用金模組的主頁
        return redirect(url_for('petty_cash.index'))
    # --- ▲▲▲ 新增結束 ▲▲▲ ---

    # 在工廠函式內部，延遲載入並註冊藍圖
    from app.modules.user.routes import user_bp
    from app.modules.petty_cash.routes import petty_cash_bp
    
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(petty_cash_bp, url_prefix='/petty_cash')

    return app