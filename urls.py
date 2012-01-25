from django.conf.urls.defaults import *
#from django.views.generic import list_detail
#from django.views.generic.create_update import create_object
from django.views.generic.simple import direct_to_template
from django.views.decorators.cache import cache_page


#urlpatterns = patterns('inon.machiavelli.views',
urlpatterns = patterns('machiavelli.views',
    #url(r'^$', 'game_list', name='game-list'),
	url(r'^$', 'summary', name='summary'),
	url(r'^games/all_finished$', 'finished_games', name="games-all-finished"), 
	url(r'^games/finished$', 'finished_games', {'only_user': True, }, name="games-my-finished"), 
	url(r'^games/other_active$', 'other_active_games', name="games-other-active"), 
	url(r'^games/my_active$', 'my_active_games', name="games-my-active"), 
	url(r'^games/joinable$', 'joinable_games', name="games-joinable"), 
	url(r'^games/pending$', 'pending_games', name="games-pending"), 
	url(r'^scenarios$', 'scenario_list', name='scenario-list'),
	url(r'^scenario/(?P<scenario_id>\d+)', 'show_scenario', name='show-scenario'),
	url(r'^scenario/stats/(?P<scenario_id>\d+)', 'scenario_stats', name='scenario-stats'),
	#url(r'^faq$', cache_page(direct_to_template, 24*60*60), {'template': 'machiavelli/faq.html'}, name='faq'),
	url(r'^ranking$', 'hall_of_fame', name='hall-of-fame'),
	url(r'^ranking/(?P<key>[-\w]+)/(?P<val>[-\w]+)$', 'ranking', name='ranking'),
	url(r'^overthrow/(?P<revolution_id>\d+)', 'overthrow', name='overthrow'),
	url(r'^new_game$', 'create_game', name='new-game'),
	url(r'^game/(?P<slug>[-\w]+)/invite$', 'invite_users', name='invite-users'),
	url(r'^game/(?P<slug>[-\w]+)/join$', 'join_game', name='join-game'),
	url(r'^game/(?P<slug>[-\w]+)/public$', 'make_public', name='make-public'),
	url(r'^game/(?P<slug>[-\w]+)/leave$', 'leave_game', name='leave-game'),
	url(r'^game/(?P<slug>[-\w]+)/log$', 'logs_by_game', name='game-log'),
	url(r'^game/(?P<slug>[-\w]+)/turn$', 'turn_log_list', name='turn-log-list'),
	#url(r'^game/(?P<slug>[-\w]+)/results$', 'game_results', name='game-results'),
	url(r'^game/(?P<slug>[-\w]+)/excommunicate/(?P<player_id>\d+)', 'excommunicate', name='excommunicate'),
	url(r'^game/(?P<slug>[-\w]+)/forgive/(?P<player_id>\d+)', 'forgive_excommunication', name='forgive-excommunication'),
	url(r'^game/(?P<slug>[-\w]+)/lend/(?P<player_id>\d+)', 'give_money', name='lend'),
	url(r'^game/(?P<slug>[-\w]+)/borrow$', 'borrow_money', name='borrow-money'),
	url(r'^game/(?P<slug>[-\w]+)/assassination$', 'assassination', name='assassination'),
	url(r'^game/(?P<slug>[-\w]+)/confirm_orders$', 'confirm_orders', name='confirm-orders'),
	url(r'^game/(?P<slug>[-\w]+)/undo$', 'undo_actions', name='undo-actions'),
	url(r'^game/(?P<slug>[-\w]+)/delete_order/(?P<order_id>\d+)$', 'delete_order', name='delete-order'),
	url(r'^game/(?P<slug>[-\w]+)/expenses$', 'play_game', kwargs={'extra': 'expenses'}, name='expenses'),
	url(r'^game/(?P<slug>[-\w]+)/undo_expense/(?P<expense_id>\d+)$', 'undo_expense', name='undo-expense'),
	url(r'^game/(?P<slug>[-\w]+)/whisper$', 'new_whisper', name='new-whisper'),
	url(r'^game/(?P<slug>[-\w]+)/whisper_list$', 'whisper_list', name='whisper-list'),
	url(r'^game/(?P<slug>[-\w]+)/journal$', 'edit_journal', name='edit-journal'),
	url(r'^game/(?P<slug>[-\w]+)', 'play_game', name='show-game'),
	#url(r'^jsgame/(?P<slug>[-\w]+)', 'js_play_game', name='js-play-game'),
)

