from rest_framework import serializers
from .models import Match, MatchScore, ScoreLog
from users.models import User
from users.serializers import UserInfoSerializer
# 比赛序列化器（返回详情）
class MatchSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    opponent_username = serializers.CharField(source='opponent.username', read_only=True)
    winner_username = serializers.CharField(source='winner.username', read_only=True, default='')
    match_mode_text = serializers.CharField(source='get_match_mode_display', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Match
        fields = [
            'id', 'creator', 'creator_username', 'opponent', 'opponent_username',
            'rounds', 'match_mode', 'match_mode_text', 'is_handicap',
            'handicap_user', 'handicapped_user', 'handicap_num',
            'status', 'status_text', 'winner', 'winner_username',
            'created_at', 'ended_at'
        ]
        read_only_fields = ['id', 'created_at', 'ended_at', 'status', 'winner']

# 创建比赛入参校验序列化器
class MatchCreateSerializer(serializers.Serializer):
    opponent_id = serializers.IntegerField(required=True)
    rounds = serializers.IntegerField(required=False, allow_null=True)
    match_mode = serializers.ChoiceField(choices=['zhongba', 'zhuifen'], default='zhongba')
    is_handicap = serializers.BooleanField(default=False)
    handicap_user_id = serializers.IntegerField(required=False, allow_null=True)
    handicapped_user_id = serializers.IntegerField(required=False, allow_null=True)
    handicap_num = serializers.IntegerField(required=False, allow_null=True)

    # 自定义校验（与你的SendInvitationView一致）
    def validate(self, data):
        # 让球模式必填项校验
        if data.get('is_handicap'):
            if not all([data.get('handicap_user_id'), data.get('handicapped_user_id')]):
                raise serializers.ValidationError('让球模式下，让球者、被让球者必须填写')

            if not(data.get('handicap_num')):
                raise serializers.ValidationError('让球模式下，必须填写让球数')
            if data.get('handicap_user_id') == data.get('handicapped_user_id'):
                raise serializers.ValidationError('让球者和被让球者不能为同一人')
        return data

# 记分操作入参序列化器
class ScoreUpdateSerializer(serializers.Serializer):
    match_id = serializers.IntegerField(required=True)
    player_id = serializers.IntegerField(required=True)
    action = serializers.ChoiceField(choices=['add', 'subtract'], default='add')

# 记分日志序列化器
class ScoreLogSerializer(serializers.ModelSerializer):
    operator_username = serializers.CharField(source='operator.username', read_only=True)
    operation_type_text = serializers.CharField(source='get_operation_type_display', read_only=True)

    class Meta:
        model = ScoreLog
        fields = ['id', 'match', 'operator', 'operator_username', 'operation_type', 'operation_type_text', 'operation_log', 'created_at']
        read_only_fields = ['id', 'created_at']

# 比赛记分序列化器
class MatchScoreSerializer(serializers.ModelSerializer):
    player1_username = serializers.CharField(source='player1.username', read_only=True)
    player2_username = serializers.CharField(source='player2.username', read_only=True)

    class Meta:
        model = MatchScore
        fields = ['id', 'match', 'player1', 'player1_username', 'player2', 'player2_username', 'player1_score', 'player2_score', 'updated_at']
        read_only_fields = ['id', 'updated_at']

# 比赛详情序列化
class MatchDetailSerializer(serializers.ModelSerializer):
    score = MatchScoreSerializer(read_only=True)  # 关联比分信息
    class Meta:
        model = Match
        fields = ["id", "creator", "opponent", "score","status"]  # 按需添加字段

class MatchListSerializer(serializers.ModelSerializer):
    """比赛列表序列化器（展示核心信息）"""
    # 参赛双方信息
    creator_info = UserInfoSerializer(source='creator', read_only=True)
    opponent_info = UserInfoSerializer(source='opponent', read_only=True)
    # 胜负状态文本（方便前端展示）
    winner_text = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            'id', 'creator_info', 'opponent_info',
            'created_at', 'winner', 'status','winner_text'
        ]

    def get_winner_text(self, obj):
        """返回胜负状态文本（未结束/XX获胜）"""
        if obj.status == 'ongoing':  # 先判断比赛状态
            return "比赛中"

        if not obj.winner:
            return "平局"
        return f"{obj.winner.nickname} 获胜"

    def to_representation(self, instance):
        ret = super().to_representation(instance)

        # ========== 核心修改：去掉状态判断，实时返回比分 ==========
        # 无论比赛状态如何，都尝试获取比分（有则返回实际值，无则返回默认值）
        try:
            score = instance.match_score  # 一对一关联获取比分记录
            ret['score_detail'] = {
                'player1': score.player1.username,
                'player1_score': score.player1_score,
                'player2': score.player2.username,
                'player2_score': score.player2_score,
                'score_result': f'{score.player1_score}:{score.player2_score}',
                'updated_at': score.updated_at.strftime('%Y-%m-%d %H:%M:%S') if score.updated_at else None
            }
        except MatchScore.DoesNotExist:
            # 无比分记录时返回默认值（保证字段结构统一，前端无需适配）
            ret['score_detail'] = {
                'player1': instance.creator.username,
                'player1_score': 0,
                'player2': instance.opponent.username,
                'player2_score': 0,
                'score_result': '0:0',
                'updated_at': None
            }

        return ret