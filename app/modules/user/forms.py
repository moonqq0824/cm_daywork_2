from flask_wtf import FlaskForm
# 1. 導入我們需要的所有欄位類型 (Fields)
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
# 2. 導入我們需要的所有驗證器 (Validators)
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
# 3. 導入我們需要用到的資料模型 (Models)
from .models import User, UserRole


class LoginForm(FlaskForm):
    """使用者登入表單"""
    account_id = StringField('登入帳號', validators=[DataRequired()])
    password = PasswordField('密碼', validators=[DataRequired()])
    remember = BooleanField('記住我')
    submit = SubmitField('登入')


# --- ▼▼▼ 新增的使用者表單，包含了所有正確的導入 ▼▼▼ ---

class AddUserForm(FlaskForm):
    """由主管新增使用者的表單"""
    account_id = StringField('登入帳號', validators=[DataRequired(), Length(min=4, max=20)])
    display_name = StringField('顯示姓名', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('電子郵件', validators=[DataRequired(), Email()])
    password = PasswordField('密碼', validators=[DataRequired(), Length(min=4)])
    confirm_password = PasswordField('確認密碼', validators=[DataRequired(), EqualTo('password', message='兩次輸入的密碼必須相符！')])
    
    # 讓管理者可以選擇要新增的使用者角色
    role = SelectField('使用者角色', 
                   choices=[(role.name, role.value) for role in UserRole], 
                   validators=[DataRequired()])
    
    submit = SubmitField('建立新使用者')

    # 自訂驗證功能，確保帳號不會重複
    def validate_account_id(self, account_id):
        user = User.query.filter_by(account_id=account_id.data).first()
        if user:
            raise ValidationError('這個登入帳號已經有人使用了，請選擇其他帳號。')

    # 自訂驗證功能，確保 Email 不會重複
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('這個電子郵件已經有人使用了，請選擇其他信箱。')
        
class EditUserForm(FlaskForm):
    """由主管編輯使用者資訊的表單"""
    account_id = StringField('登入帳號', validators=[DataRequired(), Length(min=4, max=20)])
    display_name = StringField('顯示姓名', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('電子郵件', validators=[DataRequired(), Email()])
    role = SelectField('使用者角色', choices=[(role.name, role.value) for role in UserRole], validators=[DataRequired()])
    submit = SubmitField('儲存變更')

    def __init__(self, original_account_id, original_email, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_account_id = original_account_id
        self.original_email = original_email

    def validate_account_id(self, account_id):
        # 只有在使用者修改了帳號時，才需要檢查是否重複
        if account_id.data != self.original_account_id:
            user = User.query.filter_by(account_id=account_id.data).first()
            if user:
                raise ValidationError('這個登入帳號已經有人使用了。')

    def validate_email(self, email):
        # 只有在使用者修改了 Email 時，才需要檢查是否重複
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('這個電子郵件已經有人使用了。')