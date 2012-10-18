from django.contrib import admin

import machiavelli.models as machiavelli

class PlayerAdmin(admin.ModelAdmin):
	list_display = ('user', 'game', 'contender', 'done', 'eliminated', 'conqueror', 'is_excommunicated', 'assassinated', 'defaulted', 'ducats')
	list_filter = ('game', 'done')
	ordering = ['game']

class PlayerInline(admin.TabularInline):
	model = machiavelli.Player
	extra = 0
	ordering = ['user__username']
	can_delete = False
	fields = ('user', 'game', 'contender', 'done', 'eliminated', 'conqueror', 'is_excommunicated', 'assassinated', 'defaulted', 'ducats')
	readonly_fields = ('user', 'game', 'contender', 'done', 'eliminated', 'conqueror', 'is_excommunicated', 'assassinated', 'defaulted', 'ducats')

class RevolutionAdmin(admin.ModelAdmin):
	list_display = ('game', 'government', 'opposition', 'country', 'active', 'overthrow')

class ScoreAdmin(admin.ModelAdmin):
	list_display = ('user', 'game', 'country', 'points', 'cities', 'position')
	list_filter = ('game', 'user', 'country')
	ordering = ['game']

class ScoreInline(admin.TabularInline):
	model = machiavelli.Score
	extra = 0
	ordering = ['user__username']
	can_delete = False
	fields = ('user', 'game', 'country', 'points', 'cities', 'position')
	readonly_fields = ('user', 'game', 'country', 'points', 'cities')

class UnitAdmin(admin.ModelAdmin):
	list_display = ('__unicode__', 'player', 'must_retreat', 'power', 'loyalty', 'placed', 'paid')
	ordering = ['player']
	list_filter = ('player', 'must_retreat')

class SpecialUnitAdmin(admin.ModelAdmin):
	list_display = ('__unicode__', 'cost', 'power', 'loyalty')

class GameAreaAdmin(admin.ModelAdmin):
	list_display = ('game', 'board_area', 'player', 'home_of', 'years', 'standoff', 'famine', 'storm')
	list_per_page = 73
	ordering = ['board_area']
	list_filter = ('game', )

class OrderAdmin(admin.ModelAdmin):
	list_display = ('player', '__unicode__', 'explain', 'confirmed')
	list_editable = ('confirmed', )
	list_filter = ('confirmed',)

class ConfigurationInline(admin.TabularInline):
	model = machiavelli.Configuration
	extra = 1

class GameAdmin(admin.ModelAdmin):
	list_display = ('pk', 'slug', 'slots', 'scenario', 'created_by', 'started', 'finished', 'player_list', 'version')
	inlines = [ ConfigurationInline, ScoreInline,]

	def player_list(self, obj):
		users = []
		for p in obj.player_set.filter(user__isnull=False):
			users.append(p.user.username)
		return ", ".join(users)

	player_list.short_description = 'Player list'

class LiveGameAdmin(admin.ModelAdmin):
	list_display = ('pk', 'slug', 'paused', 'extended_deadline', 'year', 'season', 'phase', 'last_phase_change', 'next_phase_change', 'started', 'version')
	actions = ['redraw_map',
				'check_finished_phase',
				'pause',
				'resume',]
	inlines = [ ConfigurationInline, PlayerInline, ]

	def redraw_map(self, request, queryset):
		for obj in queryset:
			obj.make_map(fow=obj.configuration.fow)
	redraw_map.short_description = "Redraw map"

	def check_finished_phase(self, request, queryset):
		for obj in queryset:
			obj.check_finished_phase()
	check_finished_phase.short_description = "Check finished phase"

	def pause(self, request, queryset):
		queryset.update(paused=True)
	pause.short_description = "Pause the games"

	def resume(self, request, queryset):
		queryset.update(paused=False)
	resume.short_description = "Resume paused games"
	
class RetreatOrderAdmin(admin.ModelAdmin):
	pass

class TurnLogAdmin(admin.ModelAdmin):
	ordering = ['-timestamp']
	list_display = ('game', 'timestamp')
	list_filter = ('game',)

class ExpenseAdmin(admin.ModelAdmin):
	list_display = ('__unicode__', 'player', 'ducats', 'type', 'unit', 'area', 'confirmed')
	list_filter = ('player', 'type',)

class RebellionAdmin(admin.ModelAdmin):
	list_display = ('__unicode__', 'player', 'garrisoned', 'repressed',)
	list_filter = ('player',)

class LoanAdmin(admin.ModelAdmin):
	list_display = ('player', 'debt', 'year', 'season', )

class AssassinAdmin(admin.ModelAdmin):
	pass

class AssassinationAdmin(admin.ModelAdmin):
	pass

class WhisperAdmin(admin.ModelAdmin):
	list_display = ('__unicode__', 'user', 'game', 'order',)

class InvitationAdmin(admin.ModelAdmin):
	pass

class GameCommentAdmin(admin.ModelAdmin):
	list_display = ('__unicode__', 'user', 'game', 'is_public')

admin.site.register(machiavelli.Game, GameAdmin)
admin.site.register(machiavelli.LiveGame, LiveGameAdmin)
admin.site.register(machiavelli.Unit, UnitAdmin)
admin.site.register(machiavelli.GameArea, GameAreaAdmin)
admin.site.register(machiavelli.Player, PlayerAdmin)
admin.site.register(machiavelli.Revolution, RevolutionAdmin)
admin.site.register(machiavelli.Score, ScoreAdmin)
admin.site.register(machiavelli.Order, OrderAdmin)
admin.site.register(machiavelli.RetreatOrder, RetreatOrderAdmin)
admin.site.register(machiavelli.TurnLog, TurnLogAdmin)
admin.site.register(machiavelli.Expense, ExpenseAdmin)
admin.site.register(machiavelli.Rebellion, RebellionAdmin)
admin.site.register(machiavelli.Loan, LoanAdmin)
admin.site.register(machiavelli.Assassin, AssassinAdmin)
admin.site.register(machiavelli.Assassination, AssassinationAdmin)
admin.site.register(machiavelli.Whisper, WhisperAdmin)
admin.site.register(machiavelli.Invitation, InvitationAdmin)
admin.site.register(machiavelli.GameComment, GameCommentAdmin)
admin.site.register(machiavelli.Team)
admin.site.register(machiavelli.TeamMessage)
admin.site.register(machiavelli.GameRoute)
admin.site.register(machiavelli.Diplomat)
admin.site.register(machiavelli.StrategicOrder)
