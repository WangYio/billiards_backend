import random
import requests
from django.db import models
from billiards_backend import settings
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import User, Invitation, Friendship
from .serializers import (
    UserRegisterSerializer, UserInfoSerializer, InvitationSerializer,
    FriendshipSerializer, UserSearchSerializer
)


# 1. 用户注册视图（允许匿名）
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]


# 微信小程序登录接口
class WxLoginView(APIView):
    # 无需登录即可访问（登录接口本身）
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        # 1. 获取小程序传的 code
        code = request.data.get("code")
        print(code)
        if not code:
            return Response(
                {"code": 400, "msg": "缺少微信登录code"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. 调用微信官方接口，获取 openid
        wx_config = settings.WX_MINI_PROGRAM

        print(wx_config)
        params = {
            "appid": wx_config["APPID"],
            "secret": wx_config["SECRET"],
            "js_code": code,
            "grant_type": "authorization_code"
        }
        print(params)
        try:
            # 调用微信接口
            res = requests.get(wx_config["JSCODE2SESSION_URL"], params=params)

            res_data = res.json()


            # 处理微信接口错误
            if "errcode" in res_data and res_data["errcode"] != 0:
                return Response(
                    {"code": 500, "msg": f"微信接口错误：{res_data['errmsg']}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            openid = res_data.get("openid")
            print(openid)
            if not openid:
                return Response(
                    {"code": 500, "msg": "获取openid失败"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            return Response(
                {"code": 500, "msg": f"调用微信接口异常：{str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 3. 关联你现有台球系统的用户（核心！复用用户表）
        try:
            # 查找是否已有该openid绑定的用户
            user = User.objects.get(openid=openid)
        except User.DoesNotExist:
            # 新用户：自动创建台球系统账号（复用你现有用户逻辑）
            # 生成默认用户名（避免重复）
            default_username = f"wx_{openid[:8]}"
            # 确保用户名唯一（防止极端情况重复）
            while User.objects.filter(username=default_username).exists():
                default_username = f"wx_{openid[:8]}_{random.randint(100, 999)}"

            # 创建用户（字段和你现有一致）
            user = User.objects.create(
                username=default_username,
                nickname="台球玩家",  # 默认昵称
                openid=openid,
                # 其他字段：复用你现有默认值（如 is_active=True 等）
            )

        # 4. 生成JWT Token（完全复用你现有Web端的逻辑！）
        refresh = RefreshToken.for_user(user)
        token = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),  # 业务接口用这个token
        }

        # 5. 返回数据（和你现有Web端登录接口格式一致，方便小程序适配）
        return Response({
            "code": 200,
            "msg": "登录成功",
            "data": {
                "token": token["access"],  # 给小程序存储的token
                "userInfo": {
                    "id": user.id,
                    "openid":user.openid,
                    "username": user.username,
                    "nickname": user.nickname,
                }
            }
        })


# 2. 用户登录视图（JWT，允许匿名）
class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]


# 3. 个人信息视图（查/改）
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserInfoSerializer

    def get_object(self):
        """返回当前登录用户"""
        return self.request.user

    def update(self, request, *args, **kwargs):
        """仅允许修改昵称"""
        allowed_fields = ['nickname']
        # 过滤仅允许修改的字段
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        if not data:
            return Response({'error': '仅允许修改昵称'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(self.get_object(), data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


# 4. 好友列表视图
class FriendListView(generics.ListAPIView):
    serializer_class = FriendshipSerializer

    def get_queryset(self):
        """获取当前用户的所有好友关系"""
        user = self.request.user
        return Friendship.objects.filter(
            # models.Q(user1=user) | models.Q(user2=user)
            Q(user1=self.request.user) | Q(user2=self.request.user)
        ).order_by('-create_time')

    def get_serializer_context(self):
        # 传递当前用户到序列化器
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


# 5. 发送好友邀请视图
class SendInvitationView(generics.CreateAPIView):
    serializer_class = InvitationSerializer

    def create(self, request, *args, **kwargs):
        inviter = request.user
        invitee_id = request.data.get('invitee_id')

        # 验证被邀请人存在
        try:
            invitee = User.objects.get(id=invitee_id)
        except User.DoesNotExist:
            return Response({'error': '被邀请人不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 验证不能邀请自己
        if inviter.id == invitee.id:
            return Response({'error': '不能邀请自己'}, status=status.HTTP_400_BAD_REQUEST)

        # 验证是否已为好友
        is_friend = Friendship.objects.filter(
            models.Q(user1=inviter, user2=invitee) | models.Q(user1=invitee, user2=inviter)
        ).exists()
        if is_friend:
            return Response({'error': '该用户已为您的好友'}, status=status.HTTP_400_BAD_REQUEST)

# 验证是否已邀请，处理已拒绝
        existing_invite = Invitation.objects.filter(
            inviter=inviter, invitee=invitee
        ).first()

        if existing_invite:
            if existing_invite.status in ['pending', 'accepted']:
                return Response({'error': '已向该用户发送过邀请'}, status=status.HTTP_400_BAD_REQUEST)
            elif existing_invite.status == 'rejected':
                existing_invite.status = 'pending'
                # 语法修正：如果你的Invitation模型没有updated_at字段，删掉'updated_at'即可
                existing_invite.save(update_fields=['status'])  # 仅保留必改字段，避免字段不存在报错
                return Response({'message': '邀请重新发送成功'}, status=status.HTTP_201_CREATED)
            else:
                return Response({'error': '该邀请状态异常，无法重发'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            Invitation.objects.create(inviter=inviter, invitee=invitee)
            return Response({'message': '邀请发送成功'}, status=status.HTTP_201_CREATED)




# 6. 邀请列表视图（按状态筛选）
class InvitationListView(generics.ListAPIView):
    serializer_class = InvitationSerializer

    def get_queryset(self):
        """
        获取邀请列表，支持双重筛选：
        - type: received(默认) 收到的邀请 / sent 发送的邀请
        - status: pending(默认) 待处理 / accepted 已同意 / rejected 已拒绝 / all 所有状态
        """
        user = self.request.user
        # 1. 获取筛选参数
        invite_type = self.request.query_params.get('type', 'received')  # 类型：received/sent
        status_filter = self.request.query_params.get('status', 'pending')

        # 基础查询条件：区分收到的/发送的邀请
        if invite_type == 'sent':
            query_filter = {'inviter': user}  # 发送的邀请
        else:
            query_filter = {'invitee': user}  # 收到的邀请（默认）
        # 状态筛选逻辑（兼容原有逻辑）
        if status_filter == 'all':
            queryset = Invitation.objects.filter(**query_filter).order_by('-create_time')
        else:
            queryset = Invitation.objects.filter(
                **query_filter, status=status_filter
            ).order_by('-create_time')

        return queryset




# 7. 处理邀请视图（同意/拒绝）
class HandleInvitationView(generics.UpdateAPIView):
    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer

    def update(self, request, *args, **kwargs):
        invitation = self.get_object()
        action = request.query_params.get('action')

        # 验证：仅邀请接收人可处理
        if invitation.invitee != request.user:
            return Response({'error': '无权限处理该邀请'}, status=status.HTTP_403_FORBIDDEN)

        # 验证：仅待处理邀请可操作
        if invitation.status != 'pending':
            return Response({'error': '该邀请已处理，无法重复操作'}, status=status.HTTP_400_BAD_REQUEST)

        # 处理同意/拒绝
        if action == 'accept':
            invitation.status = 'accepted'
            # 创建好友关系
            Friendship.create_friendship(invitation.inviter, invitation.invitee)
            msg = '邀请已同意，已添加为好友'
        elif action == 'reject':
            invitation.status = 'rejected'
            msg = '邀请已拒绝'
        else:
            return Response({'error': '无效操作，仅支持accept/reject'}, status=status.HTTP_400_BAD_REQUEST)

        invitation.save()
        return Response({'message': msg}, status=status.HTTP_200_OK)


# 8. 用户查询视图（按ID/名称）
class UserSearchView(generics.ListAPIView):
    serializer_class = UserSearchSerializer

    def get_queryset(self):
        """按ID/名称查询用户，并添加状态（已好友/已邀请/可邀请）"""
        keyword = self.request.query_params.get('keyword', '')
        search_type = self.request.query_params.get('type', 'name')  # id/name
        current_user = self.request.user

        # 构建查询条件
        if search_type == 'id' and keyword.isdigit():
            queryset = User.objects.filter(id=int(keyword))
        else:
            queryset = User.objects.filter(username__icontains=keyword)

        # 排除当前用户
        queryset = queryset.exclude(id=current_user.id)

        # 为每个用户添加状态
        for user in queryset:
            # 检查是否已好友
            is_friend = Friendship.objects.filter(
                models.Q(user1=current_user, user2=user) | models.Q(user1=user, user2=current_user)
            ).exists()
            if is_friend:
                user.status = '已加好友'
                continue

            # 检查是否已发送邀请
            is_invited = Invitation.objects.filter(
                inviter=current_user, invitee=user, status__in=['pending', 'accepted']
            ).exists()
            if is_invited:
                user.status = '已发送邀请'
            else:
                user.status = '可邀请'

        return queryset