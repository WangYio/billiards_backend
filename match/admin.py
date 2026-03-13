from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Match, MatchScore, ScoreLog

# 记分表内嵌到比赛详情页
class MatchScoreInline(admin.StackedInline):
    model = MatchScore
    can_delete = False
    verbose_name = '比赛记分'

# 日志表内嵌到比赛详情页
class ScoreLogInline(admin.TabularInline):
    model = ScoreLog
    extra = 0
    verbose_name = '记分日志'
    readonly_fields = ['created_at']

# 比赛Admin配置
@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'creator', 'opponent', 'match_mode', 'status', 'rounds', 'winner', 'created_at']
    list_filter = ['match_mode', 'status', 'is_handicap']
    search_fields = ['creator__username', 'opponent__username', 'id']
    readonly_fields = ['created_at', 'ended_at']
    inlines = [MatchScoreInline, ScoreLogInline]

# 记分Admin配置
@admin.register(MatchScore)
class MatchScoreAdmin(admin.ModelAdmin):
    list_display = ['match', 'player1', 'player1_score', 'player2', 'player2_score', 'updated_at']
    search_fields = ['match__id', 'player1__username', 'player2__username']
    readonly_fields = ['updated_at']

# 日志Admin配置
@admin.register(ScoreLog)
class ScoreLogAdmin(admin.ModelAdmin):
    list_display = ['match', 'operator', 'operation_type', 'operation_log', 'created_at']
    list_filter = ['operation_type']
    search_fields = ['match__id', 'operator__username', 'operation_log']
    readonly_fields = ['created_at']