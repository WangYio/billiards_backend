from django.urls import path
from .views import CreateMatchView, UpdateScoreView, EndMatchView, MatchLogView, MatchDetailView, MatchListView

urlpatterns = [
    # 创建比赛
    path('create/', CreateMatchView.as_view(), name='create_match'),
    # 记分操作（加减分）
    path('score/update/', UpdateScoreView.as_view(), name='update_score'),
    # 手动结束比赛
    path('end/', EndMatchView.as_view(), name='end_match'),
    # 查询比赛日志（pk=比赛ID）
    path('log/<int:pk>/', MatchLogView.as_view(), name='match_log'),
    path("detail/<int:match_id>/", MatchDetailView.as_view(), name="match_detail"),
    path("list/", MatchListView.as_view(), name="match_list"),  # 比赛列表接口
]