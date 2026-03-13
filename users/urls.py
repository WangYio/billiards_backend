from django.urls import path
from .views import (
    RegisterView, LoginView, ProfileView, FriendListView,
    SendInvitationView, InvitationListView, HandleInvitationView,
    UserSearchView,WxLoginView
)

urlpatterns = [
    # 注册/登录
    path("wx/login/", WxLoginView.as_view(), name="wx_login"),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    # 个人信息
    path('profile/', ProfileView.as_view(), name='profile'),
    # 好友列表
    path('friends/', FriendListView.as_view(), name='friends'),
    # 邀请相关
    path('invitation/send/', SendInvitationView.as_view(), name='send_invitation'),
    path('invitation/list/', InvitationListView.as_view(), name='invitation_list'),
    path('invitation/handle/<int:pk>/', HandleInvitationView.as_view(), name='handle_invitation'),
    # 用户查询
    path('search/', UserSearchView.as_view(), name='user_search'),
]