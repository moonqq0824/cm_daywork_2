import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'user.login' # 未登入時會被導向的登入頁面
login_manager.login_message = '請先登入以存取此頁面。'
login_manager.login_message_category = 'info'


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # 基礎設定
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 初始化擴充套件
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # 註冊藍圖 (Blueprints)
    from app.modules.user.routes import user_bp
    app.register_blueprint(user_bp)

    from app.modules.petty_cash.routes import petty_cash_bp
    app.register_blueprint(petty_cash_bp)

    return app