from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db, bcrypt
from .models import User, UserRole
# 1. 導入我們需要的所有表單
from .forms import LoginForm, AddUserForm, EditUserForm
from functools import wraps

user_bp = Blueprint('user', __name__)

# --- 權限檢查裝飾器 (您的版本很好，我們保留它) ---
def manager_required(f):
    """一個檢查使用者是否為主管的裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 2. 我們可以把 is_manager() 的邏輯統一到 models.py 中，讓程式碼更乾淨
        # (您現有的 is_manager() 已經在 models.py 中了，所以這裡不用改)
        if not current_user.is_manager():
            flash('您沒有權限存取此頁面。', 'danger')
            return redirect(url_for('petty_cash.index')) # 導向到零用金主頁
        return f(*args, **kwargs)
    return decorated_function


# --- 登入與登出 ---
@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('petty_cash.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(account_id=form.account_id.data).first()
        # 3. 修正 login_user 的一個小筆誤 (remember_me -> remember)
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('登入成功！', 'success')
            # 如果使用者是從別的頁面被導過來的，就送他回去；否則去主頁
            return redirect(next_page) if next_page else redirect(url_for('petty_cash.index'))
        else:
            flash('無效的登入帳號或密碼', 'danger')
            return redirect(url_for('user.login'))

    return render_template('login.html', form=form, title='登入')


@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功登出。', 'info')
    return redirect(url_for('user.login'))


# --- 使用者管理功能 ---

@user_bp.route('/list')
@login_required
@manager_required # 4. 所有管理功能都加上權限檢查
def user_list():
    """顯示使用者列表頁面"""
    users = User.query.order_by(User.account_id).all()
    # 5. 記得要把 UserRole 傳給樣板
    return render_template('user_list.html', title='使用者列表', users=users, UserRole=UserRole)


@user_bp.route('/add', methods=['GET', 'POST'])
@login_required
@manager_required
def add_user():
    """處理新增使用者的邏輯"""
    form = AddUserForm()
    if form.validate_on_submit():
        try:
            hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            new_user = User(
                account_id=form.account_id.data,
                display_name=form.display_name.data,
                email=form.email.data,
                password_hash=hashed_password,
                # 6. 修正點：從表單傳回的 "MANAGER" 字串轉換為 UserRole.MANAGER 物件
                role=UserRole[form.role.data] 
            )
            db.session.add(new_user)
            db.session.commit()
            flash(f'已成功建立新使用者：{form.display_name.data}！', 'success')
            return redirect(url_for('user.user_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'建立使用者時發生錯誤：{e}', 'danger')
            
    return render_template('add_user.html', title='新增使用者', form=form)


# 7. 新增的「編輯使用者」路由
@user_bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit_user(user_id):
    """處理編輯使用者資訊的邏輯"""
    user_to_edit = User.query.get_or_404(user_id)
    # 將使用者原始的帳號和信箱傳入表單，用於驗證是否重複
    form = EditUserForm(original_account_id=user_to_edit.account_id, original_email=user_to_edit.email)

    if form.validate_on_submit():
        try:
            # 防止主管不小心修改到自己的權限
            if user_to_edit.id == current_user.id and UserRole[form.role.data] != UserRole.MANAGER:
                flash('無法將自己的角色降級。', 'warning')
                return redirect(url_for('user.user_list'))

            user_to_edit.account_id = form.account_id.data
            user_to_edit.display_name = form.display_name.data
            user_to_edit.email = form.email.data
            user_to_edit.role = UserRole[form.role.data]
            db.session.commit()
            flash('使用者資訊已成功更新！', 'success')
            return redirect(url_for('user.user_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新時發生錯誤：{e}', 'danger')
            
    elif request.method == 'GET':
        # GET 請求時，將使用者現有的資料填入表單
        form.account_id.data = user_to_edit.account_id
        form.display_name.data = user_to_edit.display_name
        form.email.data = user_to_edit.email
        form.role.data = user_to_edit.role.name # 將 UserRole.MANAGER 物件轉為 "MANAGER" 字串給表單

    return render_template('edit_user.html', title='編輯使用者', form=form, user=user_to_edit)