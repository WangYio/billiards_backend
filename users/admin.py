from django.contrib import admin
from .models import User, Friendship, Invitation

# 极简注册：一行一个模型，直接可用
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # 列表页显示的字段（按你要求：ID、名称、昵称、密码）
    list_display = ('id', 'username', 'nickname', 'password')
    # 密码字段设为只读（Django存储的是哈希值，不能直接编辑）
    # readonly_fields = ('password', 'id')
    # 可选：让名称/昵称支持搜索，方便查找用户
    search_fields = ('username', 'nickname')

# 直接注册 Invitation 并展示详细字段
@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    # 列表页直接展示所有核心字段（详细信息）
    list_display = ['id', 'inviter', 'invitee', 'status', 'create_time']
    # 支持搜索（快速定位）
    search_fields = ['inviter__username', 'invitee__username', 'id']

# 直接注册 Friendship 并展示详细字段
@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    # 列表页直接展示所有核心字段（详细信息）
    list_display = ['id', 'user1', 'user2', 'create_time']
    # 支持搜索（快速定位）
    search_fields = ['user1__username', 'user2__username', 'id']



# Register your models here.
