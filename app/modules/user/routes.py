from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from .models import User, UserRole
from .forms import LoginForm
from functools import wraps

user_bp = Blueprint('user', __name__, url_prefix='/user')

def manager_required(f):
    """一個檢查使用者是否為主管的裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_manager():
            flash('您沒有權限存取此頁面。', 'danger')
            return redirect(url_for('petty_cash.index'))
        return f(*args, **kwargs)
    return decorated_function

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('petty_cash.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # ▼▼▼ 修改查詢邏輯 ▼▼▼
        user = User.query.filter_by(account_id=form.account_id.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('無效的登入帳號或密碼', 'danger')
            return redirect(url_for('user.login'))
        # ▲▲▲ 修改結束 ▲▲▲

        login_user(user, remember=form.remember_me.data)
        flash('登入成功！', 'success')
        return redirect(url_for('petty_cash.index'))

    return render_template('login.html', form=form)

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功登出。', 'info')
    return redirect(url_for('user.login'))

# 可以在這裡加入註冊、修改密碼等路由...

@user_bp.route('/manage')
@login_required
@manager_required # <--- 加上我們自訂的權限檢查
def user_management():
    """顯示使用者管理頁面"""
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=15, error_out=False)
    return render_template('user_management.html', users=users)

@user_bp.route('/manage/set_role/<int:user_id>', methods=['POST'])
@login_required
@manager_required
def set_user_role(user_id):
    """設定使用者的角色"""
    user_to_change = db.session.get(User, user_id)
    if not user_to_change:
        flash('找不到該使用者。', 'danger')
        return redirect(url_for('user.user_management'))

    # 防止使用者變更自己的角色
    if user_to_change.id == current_user.id:
        flash('無法變更自己的角色。', 'warning')
        return redirect(url_for('user.user_management'))

    new_role_str = request.form.get('role')
    if new_role_str in UserRole.__members__:
        user_to_change.role = UserRole[new_role_str]
        db.session.commit()
        flash(f'已成功將使用者 {user_to_change.username} 的角色變更為 {user_to_change.role.value}。', 'success')
    else:
        flash('無效的角色設定。', 'danger')
    
    return redirect(url_for('user.user_management'))