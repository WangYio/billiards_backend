from django.db import models
from django.utils import timezone
# 核心：导入你user应用的User模型（非Django自带）

from users.models import User

# 比赛表（对标你的Invitation模型）
class Match(models.Model):
    # 比赛模式枚举（对标Invitation的status字段）
    MATCH_MODE_CHOICES = [
        ('zhongba', '中八'),
        ('zhuifen', '追分'),
    ]
    # 比赛状态枚举
    STATUS_CHOICES = [
        ('pending', '待开始'),
        ('ongoing', '比赛中'),
        ('ended', '比赛结束'),
    ]

    # 核心字段（ID自增默认，无需显式定义）
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_matches', verbose_name='创建人')
    opponent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='opponent_matches', verbose_name='对手')
    rounds = models.IntegerField(null=True, blank=True, verbose_name='局数（无限制则为空）')
    match_mode = models.CharField(max_length=10, choices=MATCH_MODE_CHOICES, default='zhongba', verbose_name='比赛模式')
    is_handicap = models.BooleanField(default=False, verbose_name='是否让球')
    handicap_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handicap_matches', verbose_name='让球者')
    handicapped_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handicapped_matches', verbose_name='被让球者')
    handicap_num = models.IntegerField(null=True, blank=True, verbose_name='让球数')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='比赛状态')
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_matches', verbose_name='胜利者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')

    class Meta:
        verbose_name = '比赛'
        verbose_name_plural = '比赛'
        ordering = ['-created_at']  # 与你的Invitation模型一致

    def __str__(self):
        return f'[{self.id}] {self.creator.username} vs {self.opponent.username}'

# 比赛记分表（关联比赛，对标你的Friendship模型）
class MatchScore(models.Model):
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='match_score', verbose_name='关联比赛')
    player1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player1_scores', verbose_name='选手1（创建人）')
    player2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player2_scores', verbose_name='选手2（对手）')
    player1_score = models.IntegerField(default=0, verbose_name='选手1分数')
    player2_score = models.IntegerField(default=0, verbose_name='选手2分数')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '比赛记分'
        verbose_name_plural = '比赛记分'

    def __str__(self):
        return f'[{self.match.id}] {self.player1.username}({self.player1_score}) - {self.player2.username}({self.player2_score})'

# 记分日志表（记录所有操作）
class ScoreLog(models.Model):
    OPERATION_CHOICES = [
        ('add', '加分'),
        ('subtract', '减分'),
        ('system_end', '系统结束'),
        ('manual_end', '手动结束'),
    ]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='score_logs', verbose_name='关联比赛')
    operator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='operated_logs', verbose_name='操作人')
    operation_type = models.CharField(max_length=10, choices=OPERATION_CHOICES, verbose_name='操作类型')
    operation_log = models.CharField(max_length=200, verbose_name='操作日志')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        verbose_name = '记分日志'
        verbose_name_plural = '记分日志'
        ordering = ['-created_at']  # 按操作时间倒序

    def __str__(self):
        return f'[{self.match.id}] {self.operator.username} - {self.operation_log}'