from django.contrib import admin

from machiavelli.models import *
from machiavelli.graphics import make_scenario_map

class SetupInline(admin.TabularInline):
	model = Setup
	extra = 5
	ordering = ['country']

class HomeInline(admin.TabularInline):
	model = Home
	extra = 5
	ordering = ['country']

class TreasuryInline(admin.TabularInline):
	model = Treasury
	extra = 1
	ordering = ['country']

class CityIncomeInline(admin.TabularInline):
	model = CityIncome
	extra = 1
	ordering = ['city']

class DisabledAreaInline(admin.TabularInline):
	model = DisabledArea
	extra = 1
	ordering = ['area', ]

class NeutralInline(admin.TabularInline):
	model = Neutral
	extra = 1

class ScenarioAdmin(admin.ModelAdmin):
	list_display = ('name', 'start_year')
	inlines = [HomeInline, SetupInline, TreasuryInline, CityIncomeInline,
				DisabledAreaInline, NeutralInline, ]
	actions = ['make_map',]
	
	def make_map(self, request, queryset):
		for obj in queryset:
			make_scenario_map(obj)
	make_map.short_description = "Make initial map"

class CountryAdmin(admin.ModelAdmin):
	list_display = ('name', 'static_name')

class PlayerAdmin(admin.ModelAdmin):
	list_display = ('user', 'game', 'country', 'done', 'eliminated', 'conqueror', 'is_excommunicated', 'assassinated', 'defaulted', 'ducats')
	list_filter = ('game', 'done')
	ordering = ['game']

class PlayerInline(admin.TabularInline):
	model = Player
	extra = 0
	ordering = ['user__username']
	can_delete = False
	fields = ('user', 'game', 'country', 'done', 'eliminated', 'conqueror', 'is_excommunicated', 'assassinated', 'defaulted', 'ducats')
	readonly_fields = ('user', 'game', 'country', 'done', 'eliminated', 'conqueror', 'is_excommunicated', 'assassinated', 'defaulted', 'ducats')

class RevolutionAdmin(admin.ModelAdmin):
	list_display = ('game', 'government', 'opposition', 'active', 'overthrow')

class ScoreAdmin(admin.ModelAdmin):
	list_display = ('user', 'game', 'country', 'points', 'cities', 'position')
	list_filter = ('game', 'user', 'country')
	ordering = ['game']

class ScoreInline(admin.TabularInline):
	model = Score
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
	list_display = ('game', 'board_area', 'player', 'standoff', 'famine', 'storm')
	list_per_page = 73
	ordering = ['board_area']
	list_filter = ('player', )

class SetupAdmin(admin.ModelAdmin):
	list_display = ('scenario', 'country', 'area', 'unit_type')

class OrderAdmin(admin.ModelAdmin):
	list_display = ('player', '__unicode__', 'explain', 'confirmed')
	list_editable = ('confirmed', )
	list_filter = ('confirmed',)

	#def player_info(self, obj):
	#	return "%(country)s (%(game)s)" % { 'country': obj.unit.player.country,
	#										'game': obj.unit.player.game }
	#player_info.short_description = 'Player'

class ControlTokenInline(admin.TabularInline):
	model = ControlToken
	extra = 1

class GTokenInline(admin.TabularInline):
	model = GToken
	extra = 1

class AFTokenInline(admin.TabularInline):
	model = AFToken
	extra = 1

class AreaAdmin(admin.ModelAdmin):
	list_display = ('name', 'code', 'is_sea', 'is_coast', 'has_city', 'is_fortified', 'has_port', 'control_income', 'garrison_income')
	inlines = [ ControlTokenInline,
		GTokenInline,
		AFTokenInline ]

class ConfigurationInline(admin.TabularInline):
	model = Configuration
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
	list_display = ('pk', 'slug', 'paused', 'extended_deadline', 'year', 'season', 'phase', 'next_phase_change', 'started', 'version')
	actions = ['redraw_map',
				'check_finished_phase',
				'pause',
				'resume',]
	inlines = [ ConfigurationInline, PlayerInline, ]

	def redraw_map(self, request, queryset):
		for obj in queryset:
			obj.make_map()
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

admin.site.register(Scenario, ScenarioAdmin)
admin.site.register(Country, CountryAdmin)
admin.site.register(Game, GameAdmin)
admin.site.register(LiveGame, LiveGameAdmin)
admin.site.register(Unit, UnitAdmin)
admin.site.register(SpecialUnit, SpecialUnitAdmin)
admin.site.register(GameArea, GameAreaAdmin)
admin.site.register(Area, AreaAdmin)
admin.site.register(Setup, SetupAdmin)
admin.site.register(Player, PlayerAdmin)
admin.site.register(Revolution, RevolutionAdmin)
admin.site.register(Score, ScoreAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(RetreatOrder, RetreatOrderAdmin)
admin.site.register(TurnLog, TurnLogAdmin)
admin.site.register(Expense, ExpenseAdmin)
admin.site.register(Rebellion, RebellionAdmin)
admin.site.register(Loan, LoanAdmin)
admin.site.register(Assassin, AssassinAdmin)
admin.site.register(Assassination, AssassinationAdmin)
admin.site.register(Whisper, WhisperAdmin)
admin.site.register(Invitation, InvitationAdmin)
admin.site.register(GameComment, GameCommentAdmin)
