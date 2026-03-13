from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from .validators import validate_username, validate_nickname, validate_password


# 用户管理器（自定义用户模型必须）
class UserManager(BaseUserManager):
    def create_user(self, username, nickname, password, **extra_fields):
        if not username:
            raise ValueError('必须提供用户名')
        if not nickname:
            raise ValueError('必须提供昵称')
        # 验证字段规则
        validate_username(username)
        validate_nickname(nickname)
        validate_password(password)

        user = self.model(
            username=username,
            nickname=nickname,
            **extra_fields
        )
        user.set_password(password)  # 密码加密存储
        user.save(using=self._db)
        return user

    def create_superuser(self, username, nickname, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, nickname, password, **extra_fields)


# 用户表（替换Django默认用户模型）
class User(AbstractBaseUser, PermissionsMixin):
    id = models.IntegerField(primary_key=True, auto_created=True)  # 自增ID，1-999999
    username = models.CharField(
        max_length=8,
        unique=True,
        validators=[validate_username],
        verbose_name='用户名'
    )
    nickname = models.CharField(
        max_length=8,
        validators=[validate_nickname],
        verbose_name='昵称'
    )
    total_matches = models.IntegerField(default=0, verbose_name='总对局数')
    total_wins = models.IntegerField(default=0, verbose_name='总胜局数')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='修改时间')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # 管理员权限
    openid = models.CharField(max_length=64, blank=True, null=True, unique=True, verbose_name="微信小程序openid")
    code = models.CharField(max_length=64, blank=True, null=True, unique=True, verbose_name="微信小程序code")

    objects = UserManager()

    # 登录字段（替换默认的username，这里保持一致）
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['nickname']

    # ID范围限制（1-999999）
    def save(self, *args, **kwargs):
        if self.id is None:
            # 自增逻辑：获取当前最大ID，默认从1开始
            max_id = User.objects.all().aggregate(models.Max('id'))['id__max'] or 0
            self.id = max_id + 1
        if self.id > 999999:
            raise ValueError('用户ID不能超过999999')
        super().save(*args, **kwargs)

    # 计算胜率（只读属性）
    @property
    def win_rate(self):
        if self.total_matches == 0:
            return '0.0%'
        rate = (self.total_wins / self.total_matches) * 100
        return f'{rate:.1f}%'

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        ordering = ['-create_time']


# 邀请状态枚举
INVITATION_STATUS = (
    ('pending', '待处理'),
    ('accepted', '已同意'),
    ('rejected', '已拒绝'),
)


# 邀请表
class Invitation(models.Model):
    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations', verbose_name='邀请人')
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invitations',
                                verbose_name='被邀请人')
    status = models.CharField(max_length=10, choices=INVITATION_STATUS, default='pending', verbose_name='状态')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        verbose_name = '邀请'
        verbose_name_plural = '邀请'
        unique_together = ('inviter', 'invitee')  # 避免重复邀请


# 好友关系表（核心修改：移除CheckConstraint，强化代码逻辑）
class Friendship(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships1', verbose_name='用户1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships2', verbose_name='用户2')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '好友关系'
        verbose_name_plural = '好友关系'
        # 仅保留唯一约束，删除CheckConstraint（SQLite不支持）
        constraints = [
            models.UniqueConstraint(fields=['user1', 'user2'], name='unique_friendship'),
        ]

    @classmethod
    def create_friendship(cls, user_a, user_b):
        """
        创建好友关系（核心：强制保证user1.id < user2.id，避免重复关系）
        替代数据库层面的CheckConstraint，适配SQLite
        """
        # 第一步：强制排序，确保user1始终是ID更小的用户
        if user_a.id > user_b.id:
            user1, user2 = user_b, user_a
        else:
            user1, user2 = user_a, user_b

        # 第二步：尝试创建，已存在则返回现有记录（避免重复）
        friendship, created = cls.objects.get_or_create(
            user1=user1,
            user2=user2
        )
        return friendship