from rest_framework import serializers
from .models import User, Invitation, Friendship
from match.models import Match
from django.db.models import Q
# 用户注册/登录序列化器
class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[User._meta.get_field('password').validators[0]])

    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'password']
        extra_kwargs = {
            'id': {'read_only': True},
        }

    def create(self, validated_data):
        """创建用户（调用管理器的create_user方法，自动加密密码）"""
        return User.objects.create_user(
            username=validated_data['username'],
            nickname=validated_data['nickname'],
            password=validated_data['password']
        )

# 用户信息序列化器（含胜率）
class UserInfoSerializer(serializers.ModelSerializer):
    win_rate = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'total_matches', 'total_wins', 'win_rate', 'create_time']
        read_only_fields = ['id', 'username', 'total_matches', 'total_wins', 'create_time']

# 邀请序列化器
class InvitationSerializer(serializers.ModelSerializer):
    inviter = UserInfoSerializer(read_only=True)
    invitee = UserInfoSerializer(read_only=True)
    inviter_id = serializers.IntegerField(write_only=True, required=False)
    invitee_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Invitation
        fields = ['id', 'inviter', 'inviter_id', 'invitee', 'invitee_id', 'status', 'create_time']
        read_only_fields = ['id', 'status', 'create_time']

# 好友关系序列化器
class FriendshipSerializer(serializers.ModelSerializer):
    friend = serializers.SerializerMethodField()  # 好友信息（排除当前用户）
    total_matches = serializers.SerializerMethodField()
    win_rate = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ['friend', 'create_time','total_matches', 'win_rate']

    def get_friend(self, obj):
        current_user = self.context['request'].user
        if obj.user1.id == current_user.id:
            return UserInfoSerializer(obj.user2).data
        return UserInfoSerializer(obj.user1).data

    def get_total_matches(self, obj):
        current_user = self.context['request'].user
        # 先和get_friend逻辑一致，拿到好友对象
        if obj.user1.id == current_user.id:
            friend_obj = obj.user2
        else:
            friend_obj = obj.user1

        # 完整Q查询：统计两人互相对战的总比赛数（仅查Match表）
        return Match.objects.filter(
            (Q(creator=current_user) & Q(opponent=friend_obj)) |
            (Q(creator=friend_obj) & Q(opponent=current_user))
        ).count()



    def get_win_rate(self, obj):
        current_user = self.context['request'].user
        # 先拿到好友对象（和get_friend逻辑一致）
        if obj.user1.id == current_user.id:
            friend_obj = obj.user2
        else:
            friend_obj = obj.user1

        # 重新计算【已完成】的总场次（替代原get_total_matches，避免包含未结束比赛）
        total_finished = Match.objects.filter(
            # 筛选两人互相对战的比赛
            (Q(creator=current_user) & Q(opponent=friend_obj)) |
            (Q(creator=friend_obj) & Q(opponent=current_user)),
            # 核心：只统计已结束的比赛（winner非空=有结果）
            winner__isnull=False
        ).count()

        if total_finished == 0:
            return 0.0  # 无有效对局时胜率为0

        # 统计当前用户在【已完成】比赛中的获胜场次
        win_count = Match.objects.filter(
            # 筛选两人互相对战的比赛
            (Q(creator=current_user) & Q(opponent=friend_obj)) |
            (Q(creator=friend_obj) & Q(opponent=current_user)),
            # 筛选胜者是当前用户（天然包含winner非空）
            winner=current_user
        ).count()

        # 计算胜率，保留1位小数
        return round((win_count / total_finished) * 100, 1)

    # def get_win_rate(self, obj):
    #     current_user = self.context['request'].user
    #     # 先拿到好友对象（和get_friend逻辑一致）
    #     if obj.user1.id == current_user.id:
    #         friend_obj = obj.user2
    #     else:
    #         friend_obj = obj.user1
    #
    #     total = self.get_total_matches(obj)
    #     if total == 0:
    #         return 0.0  # 无对局时胜率为0
    #
    #     # 统计当前用户获胜的场次（仅查Match表）
    #     win_count = Match.objects.filter(
    #         # 筛选两人互相对战的比赛
    #         (Q(creator=current_user) & Q(opponent=friend_obj)) |
    #         (Q(creator=friend_obj) & Q(opponent=current_user)),
    #         # 筛选胜者是当前用户
    #         winner=current_user
    #     ).count()
    #
    #     # 计算胜率，保留1位小数
    #     return round((win_count / total) * 100, 1)







# 用户查询序列化器（带状态：已好友/已邀请/可邀请）
class UserSearchSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)  # 动态添加的状态

    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'status']