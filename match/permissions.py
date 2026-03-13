from rest_framework import permissions
from .models import Match

class IsMatchParticipant(permissions.BasePermission):
    """仅比赛双方（创建人/对手）可操作记分/结束比赛"""
    message = '仅比赛双方可执行此操作'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # 仅记分/结束比赛接口需要校验
        if view.action in ['update_score', 'end_match']:
            match_id = request.data.get('match_id')
            try:
                match = Match.objects.get(id=match_id)
                return request.user in [match.creator, match.opponent]
            except Match.DoesNotExist:
                return False
        return True