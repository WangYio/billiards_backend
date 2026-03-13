import re
from django.core.exceptions import ValidationError

# 用户名验证：英文+数字，2-8位
def validate_username(value):
    if not re.match(r'^[a-zA-Z0-9]{2,8}$', value):
        raise ValidationError('用户名只能包含英文和数字，长度2-8位')

# 昵称验证：中文/英文/数字，2-8位
def validate_nickname(value):
    if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9]{2,8}$', value):
        raise ValidationError('昵称只能包含中文、英文和数字，长度2-8位')

# 密码验证：英文+数字，6-12位
def validate_password(value):
    if not re.match(r'^[a-zA-Z0-9]{6,12}$', value):
        raise ValidationError('密码只能包含英文和数字，长度6-12位')