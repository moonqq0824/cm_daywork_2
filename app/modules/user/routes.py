from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from .models import User
from .forms import LoginForm

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('petty_cash.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('無效的使用者名稱或密碼', 'danger')
            return redirect(url_for('user.login'))
        
        login_user(user, remember=form.remember_me.data)
        flash('登入成功！', 'success')

        # 登入後導向至零用金主頁
        return redirect(url_for('petty_cash.index'))
        
    return render_template('login.html', form=form)

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功登出。', 'info')
    return redirect(url_for('user.login'))

# 可以在這裡加入註冊、修改密碼等路由...