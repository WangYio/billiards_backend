from django.db.models import Q
from django.shortcuts import render
from rest_framework.views import APIView
# Create your views here.
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.db import models, transaction
from django.utils import timezone
from .models import Match, MatchScore, ScoreLog
from .serializers import (
    MatchSerializer, MatchCreateSerializer, MatchScoreSerializer,
    ScoreLogSerializer, ScoreUpdateSerializer, MatchDetailSerializer, MatchListSerializer
)
from .permissions import IsMatchParticipant
# 导入你user应用的模型
from users.models import User, Friendship
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# 1. 创建比赛视图（对标你的SendInvitationView）
@method_decorator(csrf_exempt, name='dispatch')
class CreateMatchView(generics.CreateAPIView):
    serializer_class = MatchCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic  # 事务保证数据一致性
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 1. 校验对手存在（与你的被邀请人校验一致）
        try:
            opponent = User.objects.get(id=data['opponent_id'])
        except User.DoesNotExist:
            return Response({'error': '对手不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 2. 校验不能和自己比赛（与你的“不能邀请自己”一致）
        if request.user == opponent:
            return Response({'error': '不能和自己创建比赛'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. 校验对手是好友（与你的“已是好友”校验一致）
        is_friend = Friendship.objects.filter(
            (models.Q(user1=request.user) & models.Q(user2=opponent)) |
            (models.Q(user1=opponent) & models.Q(user2=request.user)),
            # status='accepted'
        ).exists()


        if not is_friend:
            return Response({'error': '对手必须是你的好友'}, status=status.HTTP_400_BAD_REQUEST)

        # 4. 处理让球信息
        handicap_user = User.objects.get(id=data.get('handicap_user_id')) if data.get('handicap_user_id') else None
        handicapped_user = User.objects.get(id=data.get('handicapped_user_id')) if data.get('handicapped_user_id') else None

        # 5. 创建比赛
        match = Match.objects.create(
            creator=request.user,
            opponent=opponent,
            rounds=data.get('rounds'),
            match_mode=data.get('match_mode'),
            is_handicap=data.get('is_handicap'),
            handicap_user=handicap_user,
            handicapped_user=handicapped_user,
            handicap_num=data.get('handicap_num'),
            status='ongoing'  # 创建后直接进入比赛中
        )

        # 6. 初始化记分表
        MatchScore.objects.create(
            match=match,
            player1=request.user,
            player2=opponent,
            player1_score=0,
            player2_score=0
        )

        # 7. 记录创建日志
        ScoreLog.objects.create(
            match=match,
            operator=request.user,
            operation_type='add',
            operation_log=f'创建{match.get_match_mode_display()}比赛，局数：{match.rounds if match.rounds else "无限制"}'
        )

        return Response({
            'message': '比赛创建成功',
            'match': MatchSerializer(match).data
        }, status=status.HTTP_201_CREATED)

# 2. 记分操作视图（加减分）
class UpdateScoreView(generics.GenericAPIView):
    serializer_class = ScoreUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsMatchParticipant]
    action = 'update_score'  # 用于权限校验

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 1. 校验比赛/选手存在
        try:
            match = Match.objects.get(id=data['match_id'])
            player = User.objects.get(id=data['player_id'])
        except (Match.DoesNotExist, User.DoesNotExist):
            return Response({'error': '比赛或选手不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 2. 校验比赛状态
        if match.status != 'ongoing':
            return Response({'error': '比赛已结束，无法操作记分'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. 校验选手属于该比赛
        score = match.match_score
        if player not in [score.player1, score.player2]:
            return Response({'error': '选手不属于该比赛'}, status=status.HTTP_400_BAD_REQUEST)

        # 4. 执行加减分（每次±1）
        change_num = 1 if data['action'] == 'add' else -1
        if player == score.player1:
            new_score = score.player1_score + change_num
            # 中八模式减分不能为负
            if match.match_mode == 'zhongba' and new_score < 0:
                return Response({'error': '中八模式分数不能为负数'}, status=status.HTTP_400_BAD_REQUEST)
            score.player1_score = new_score
        else:
            new_score = score.player2_score + change_num
            if match.match_mode == 'zhongba' and new_score < 0:
                return Response({'error': '中八模式分数不能为负数'}, status=status.HTTP_400_BAD_REQUEST)
            score.player2_score = new_score

        # 5. 保存分数并记录日志
        score.save()
        log_content = f'给{player.username}{"加" if change_num>0 else "减"}1分，当前分数：{new_score}'
        ScoreLog.objects.create(
            match=match,
            operator=request.user,
            operation_type=data['action'],
            operation_log=log_content
        )

        # 6. 检查是否达到局数，自动结束比赛
        auto_end_msg = None
        if match.rounds:
            if score.player1_score >= match.rounds or score.player2_score >= match.rounds:
                winner = score.player1 if score.player1_score >= match.rounds else score.player2
                match.status = 'ended'
                match.ended_at = timezone.now()
                match.winner = winner
                match.save()

                # 记录系统结束日志
                auto_end_msg = f'系统结束比赛：{winner.username}率先达到{match.rounds}局获胜，最终比分{score.player1_score}:{score.player2_score}'
                ScoreLog.objects.create(
                    match=match,
                    operator=request.user,
                    operation_type='system_end',
                    operation_log=auto_end_msg
                )

        # 7. 返回结果
        response_data = {
            'message': auto_end_msg if auto_end_msg else f'{player.username}记分操作成功',
            'score': MatchScoreSerializer(score).data
        }
        return Response(response_data)

# 3. 手动结束比赛视图
class EndMatchView(generics.GenericAPIView):
    serializer_class = ScoreUpdateSerializer  # 复用match_id校验
    permission_classes = [permissions.IsAuthenticated, IsMatchParticipant]
    action = 'end_match'  # 用于权限校验

    def post(self, request, *args, **kwargs):
        # 1. 校验比赛ID
        match_id = request.data.get('match_id')
        if not match_id:
            return Response({'error': '比赛ID不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. 校验比赛存在且未结束
        try:
            match = Match.objects.get(id=match_id)
        except Match.DoesNotExist:
            return Response({'error': '比赛不存在'}, status=status.HTTP_404_NOT_FOUND)
        if match.status == 'ended':
            return Response({'error': '比赛已结束'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. 判定胜利者
        score = match.match_score
        if score.player1_score > score.player2_score:
            winner = score.player1
        elif score.player2_score > score.player1_score:
            winner = score.player2
        else:
            winner = None

        # 4. 更新比赛状态
        match.status = 'ended'
        match.ended_at = timezone.now()
        match.winner = winner
        match.save()

        # 5. 记录手动结束日志
        log_content = f'手动结束比赛，'
        if winner:
            log_content += f'{winner.username}以{score.player1_score}:{score.player2_score}获胜'
        else:
            log_content += f'双方平局，比分{score.player1_score}:{score.player2_score}'
        ScoreLog.objects.create(
            match=match,
            operator=request.user,
            operation_type='manual_end',
            operation_log=log_content
        )

        return Response({
            'message': log_content,
            'match': MatchSerializer(match).data
        })

# 4. 比赛日志查询视图
class MatchLogView(generics.RetrieveAPIView):
    serializer_class = ScoreLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsMatchParticipant]
    queryset = Match.objects.all()
    action = 'match_log'  # 用于权限校验

    def retrieve(self, request, *args, **kwargs):
        match = self.get_object()
        logs = match.score_logs.all()
        return Response({
            'match_id': match.id,
            'logs': ScoreLogSerializer(logs, many=True).data
        })


class MatchDetailView(APIView):
    """比赛详情接口（仅返回核心比分，不碰任何未知字段）"""

    def get(self, request, match_id):
        try:
            # 初始化默认分数（仅保留核心分数字段）
            score_data = {
                "player1_score": 0,
                "player2_score": 0  # 仅保留这两个核心字段，绝不加其他
            }

            status = {
                "status": "pending",  # 状态值（0/1/2）
                "status_text": "未开始" , # 状态文字
                "winner":"None"
            }
            # winner = "null"
            rounds = "null"

            # 查询比分记录（只查match_id匹配的）
            score_record = MatchScore.objects.filter(match_id=match_id).first()
            if score_record:
                # 只读取模型中肯定存在的字段（player1_score/player2_score）
                score_data["player1_score"] = score_record.player1_score
                score_data["player2_score"] = score_record.player2_score



            match_record = Match.objects.filter(id=match_id).first()
            # print(match_record.rounds)
            rounds = match_record.rounds
            if match_record:

                # print(match_record.get_status_display())
                # 只读取Match模型中肯定存在的status字段
                status["status"] = match_record.status
                # 获取状态文字（利用Django的choices枚举，无需手动判断）
                status["statusText"] = match_record.get_status_display()

                if match_record.winner:
                    # 可选：返回用户ID（数字）
                    status["winner"] = match_record.winner.username
                    # status["winner"] = match_record.winner()



                # print(status.winner)
                # winner = match_record.winner


            # 返回极简数据（和前端解析字段严格对齐）
            return Response({
                "match_id": match_id,
                "score": score_data,
                "status": status,
                "rounds":rounds,



            })
        except Exception as e:
            print(f"比分接口报错：{type(e)} - {str(e)}")
            return Response({"message": f"获取比分失败：{str(e)}"}, status=500)


class MatchListView(APIView):
    """比赛列表接口（参赛双方均可查看）"""

    def get(self, request):
        current_user = request.user
        # 核心筛选：当前用户是creator或opponent的所有比赛
        matches = Match.objects.filter(
            Q(creator=current_user) | Q(opponent=current_user)
        ).order_by('-created_at')  # 按创建时间倒序（最新的在前）

        # 序列化返回
        serializer = MatchListSerializer(matches, many=True)
        return Response({
            "count": matches.count(),
            "results": serializer.data
        })

