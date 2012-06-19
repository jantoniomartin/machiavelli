## Copyright (c) 2010 by Jose Antonio Martin <jantonio.martin AT gmail DOT com>
## This program is free software: you can redistribute it and/or modify it
## under the terms of the GNU Affero General Public License as published by the
## Free Software Foundation, either version 3 of the License, or (at your option
## any later version.
##
## This program is distributed in the hope that it will be useful, but WITHOUT
## ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
## FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License
## for more details.
##
## You should have received a copy of the GNU Affero General Public License
## along with this program. If not, see <http://www.gnu.org/licenses/agpl.txt>.
##
## This license is also included in the file COPYING
##
## AUTHOR: Jose Antonio Martin <jantonio.martin AT gmail DOT com>

""" Django views definitions for machiavelli application. """

## stdlib
from math import ceil
from datetime import datetime, timedelta

## django
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned, ValidationError
from django.forms.formsets import formset_factory
from django.forms.models import modelformset_factory
from django.db.models import Q, F, Sum, Count
from django.core.cache import cache
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.decorators import method_decorator
from django.utils.functional import lazy
from django.utils import simplejson
from django.contrib import messages

## generic views
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

## machiavelli
import machiavelli.models as machiavelli
import machiavelli.forms as forms
from machiavelli.signals import player_joined
from machiavelli.context_processors import activity, latest_gossip
from machiavelli.listappend import ListAppendView

## condottieri_scenarios
import condottieri_scenarios.models as scenarios

## condottieri_common
from condottieri_common.models import Server

## condottieri_profiles
from condottieri_profiles.models import CondottieriProfile
from condottieri_profiles.context_processors import sidebar_ranking

## condottieri_events
import condottieri_events.paginator as events_paginator

import logging
logger = logging.getLogger(__name__)

if "notification" in settings.INSTALLED_APPS:
	from notification import models as notification
else:
	notification = None

reverse_lazy = lambda name=None, *args : lazy(reverse, str)(name, args=args)

class LoginRequiredMixin(object):
	""" Mixin to check that the user has authenticated.
	(Always the first mixin in class)
	"""
	@method_decorator(login_required)
	def dispatch(self, *args, **kwargs):
		return super(LoginRequiredMixin, self).dispatch(*args, **kwargs)

class GameListView(ListView):
	model = machiavelli.Game
	paginate_by = 10
	context_object_name = 'game_list'
	
	def render_to_response(self, context, **kwargs):
		return super(GameListView, self).render_to_response(
			RequestContext(self.request,
				context,
				processors=[activity, sidebar_ranking,]),
			**kwargs)

class SummaryView(TemplateView):
	template_name = 'machiavelli/summary.html'

	def get_context_data(self, **kwargs):
		context = super(SummaryView, self).get_context_data(**kwargs)
		context['comments'] = machiavelli.GameComment.objects.public().order_by('-id')[:3]
		joinable = machiavelli.Game.objects.filter(slots__gt=0, private=False)
		week = timedelta(0, 7*24*60*60)
		threshold = datetime.now() - week
		promoted = joinable.filter(created__gt=threshold)
		promoted_game = None
		if self.request.user.is_authenticated():
			joinable = joinable.exclude(player__user=self.request.user)
			promoted = promoted.exclude(player__user=self.request.user)
			my_games_ids = machiavelli.Game.objects.filter(player__user=self.request.user).values('id')
			my_rev_ids = machiavelli.Revolution.objects.filter(opposition=self.request.user).values('game__id')
			revolutions = machiavelli.Revolution.objects.exclude(game__id__in=my_games_ids).exclude(game__id__in=my_rev_ids).filter(active__isnull=False, opposition__isnull=True)
			context.update( {'revolutions': revolutions})
			my_players = machiavelli.Player.objects.filter(user=self.request.user, game__started__isnull=False, done=False)
			player_list = []
			for p in my_players:
				p.deadline = p.next_phase_change()
				player_list.append(p)
			player_list.sort(cmp=lambda x,y: cmp(x.deadline, y.deadline), reverse=False)
			context.update({ 'actions': player_list })
			## show unseen notices
			if notification:
				context['new_notices'] = notification.Notice.objects.notices_for(self.request.user, unseen=True, on_site=True)[:20]
		context['joinable_count'] = joinable.count()
		if promoted.count() > 0:
			promoted_game = promoted.order_by('slots').select_related('scenario', 'configuration', 'player__user')[0]
		if promoted_game is not None:
			num_comments = promoted_game.gamecomment_set.count()
			context.update( {'promoted_game': promoted_game,
						'num_comments': num_comments} )
		new_scenario_date = datetime.now() - 4 * week # one month ago
		recent_scenarios = scenarios.Scenario.objects.filter(published__gt=new_scenario_date).order_by('-published')
		if recent_scenarios.count() > 0:
			context.update({'new_scenario': recent_scenarios[0] })
		return context
		
	def render_to_response(self, context, **kwargs):
		return super(SummaryView, self).render_to_response(
			RequestContext(self.request,
				context,
				processors=[activity, latest_gossip, sidebar_ranking,]),
			**kwargs)

class MyActiveGamesList(GameListView):
	template_name = 'machiavelli/game_list_my_active.html'
	model = machiavelli.Player
	context_object_name = 'player_list'

	def get_queryset(self):
		if self.request.user.is_authenticated():
			my_players = machiavelli.Player.objects.filter(user=self.request.user, game__slots=0).select_related("contender", "game__scenario", "game__configuration")
		else:
			my_players = machiavelli.Player.objects.none()
		player_list = []
		for p in my_players:
			p.deadline = p.next_phase_change()
			player_list.append(p)
		player_list.sort(cmp=lambda x,y: cmp(x.deadline, y.deadline), reverse=False)
		return player_list

class OtherActiveGamesList(GameListView):
	template_name = 'machiavelli/game_list_active.html'

	def get_queryset(self):
		if self.request.user.is_authenticated():
			user_id = self.request.user.id
		else:
			user_id = None
		cache_key = "other_active_games-%s" % user_id
		games = cache.get(cache_key)
		if not games:
			if not user_id is None:
				games = machiavelli.LiveGame.objects.exclude(player__user=self.request.user)
			else:
				games = machiavelli.LiveGame.objects.all()
			cache.set(cache_key, games)
		return games

class AllFinishedGamesList(GameListView):
	template_name_suffix = "_list_finished"

	def get_queryset(self):
		cache_key = "finished_games"
		games = cache.get(cache_key)
		if not games:
			games = machiavelli.Game.objects.finished().annotate(comments_count=Count('gamecomment'))
			cache.set(cache_key, games)
		return games

class MyFinishedGamesList(GameListView):
	template_name_suffix = "_list_finished"

	def get_queryset(self):
		cache_key = "finished_games-%s" % self.request.user.id
		games = cache.get(cache_key)
		if not games:
			games = machiavelli.Game.objects.finished().filter(score__user=self.request.user).annotate(comments_count=Count('gamecomment'))
			cache.set(cache_key, games)
		return games
	
	def get_context_data(self, **kwargs):
		context = super(MyFinishedGamesList, self).get_context_data(**kwargs)
		context["only_user"] = True
		return context

class JoinableGamesList(GameListView):
	""" Gets a paginated list of all the games that the user can join """
	template_name_suffix = '_list_pending'

	def get_queryset(self):
		return machiavelli.Game.objects.joinable_by_user(self.request.user).annotate(comments_count=Count('gamecomment'))

	def get_context_data(self, **kwargs):
		context = super(JoinableGamesList, self).get_context_data(**kwargs)
		context["joinable"] = True
		return context

class PendingGamesList(LoginRequiredMixin, GameListView):
	""" Gets a paginated list of all the games of the player that have not yet started """
	template_name_suffix = '_list_pending'

	def get_queryset(self):
		cache_key = "pending_games-%s" % self.request.user.id
		games = cache.get(cache_key)
		if not games:
			games = machiavelli.Game.objects.pending_for_user(self.request.user).annotate(comments_count=Count('gamecomment'))
			cache.set(cache_key, games, 10*60)
		return games

	def get_context_data(self, **kwargs):
		context = super(PendingGamesList, self).get_context_data(**kwargs)
		context["joinable"] = False
		return context

class GameBaseView(DetailView):
	context_object_name = 'game'
	model = machiavelli.Game

	def get_player(self):
		game = self.get_object()
		try:
			player = machiavelli.Player.objects.get(game=game, user=self.request.user)
		except ObjectDoesNotExist:
			player = machiavelli.Player.objects.none()

	def get_context_data(self, **kwargs):
		context = super(GameBaseView, self).get_context_data(**kwargs)
		game = self.get_object()
		player = self.get_player()
		context.update({
			'map': game.map_url,
			'player': player,
			'player_list': game.player_list_ordered_by_cities(),
			'show_users': game.visible,
		})
		if game.slots > 0:
			context['player_list'] = game.player_set.filter(user__isnull=False)
		log = game.baseevent_set.all()
		if player:
			context['done'] = player.done
			if game.configuration.finances:
				context['ducats'] = player.ducats
			context['can_excommunicate'] = player.can_excommunicate()
			context['can_forgive'] = player.can_forgive()
			try:
				journal = machiavelli.Journal.objects.get(user=self.request.user, game=game)
			except ObjectDoesNotExist:
				journal = machiavelli.Journal()
			context.update({'excerpt': journal.excerpt})
			if game.slots == 0:
				context['time_exceeded'] = player.time_exceeded()
			if player.done and not player.in_last_seconds() and not player.eliminated:
				context.update({'undoable': True,})
		log = log.exclude(season__exact=game.season,
							phase__exact=game.phase)
		if len(log) > 0:
			last_year = log[0].year
			last_season = log[0].season
			last_phase = log[0].phase
			context['log'] = log.filter(year__exact=last_year,
								season__exact=last_season,
								phase__exact=last_phase)
		else:
			context['log'] = log # this will always be an empty queryset
		rules = game.configuration.get_enabled_rules()
		if len(rules) > 0:
			context['rules'] = rules
	
		if game.configuration.gossip:
			whispers = game.whisper_set.all()[:10]
			context.update({'whispers': whispers, })
			if player:
				context.update({'whisper_form': forms.WhisperForm(),})
		
		return context

def base_context(request, game, player):
	context = {
		'user': request.user,
		'game': game,
		'map' : game.get_map_url(),
		'player': player,
		'player_list': game.player_list_ordered_by_cities(),
		'show_users': game.visible,
		}
	if game.slots > 0:
		context['player_list'] = game.player_set.filter(user__isnull=False)
	log = game.baseevent_set.all()
	if player:
		context['done'] = player.done
		if game.configuration.finances:
			context['ducats'] = player.ducats
		context['can_excommunicate'] = player.can_excommunicate()
		context['can_forgive'] = player.can_forgive()
		try:
			journal = machiavelli.Journal.objects.get(user=request.user, game=game)
		except ObjectDoesNotExist:
			journal = machiavelli.Journal()
		context.update({'excerpt': journal.excerpt})
		if game.slots == 0:
			context['time_exceeded'] = player.time_exceeded()
		if player.done and not player.in_last_seconds() and not player.eliminated:
			context.update({'undoable': True,})
	log = log.exclude(season__exact=game.season,
							phase__exact=game.phase)
	if len(log) > 0:
		last_year = log[0].year
		last_season = log[0].season
		last_phase = log[0].phase
		context['log'] = log.filter(year__exact=last_year,
								season__exact=last_season,
								phase__exact=last_phase)
	else:
		context['log'] = log # this will always be an empty queryset
	#context['log'] = log[:10]
	rules = game.configuration.get_enabled_rules()
	if len(rules) > 0:
		context['rules'] = rules
	
	if game.configuration.gossip:
		whispers = game.whisper_set.all()[:10]
		context.update({'whispers': whispers, })
		if player:
			context.update({'whisper_form': forms.WhisperForm(),})
		
	return context

#@never_cache
#def js_play_game(request, slug=''):
#	game = get_object_or_404(Game, slug=slug)
#	try:
#		player = Player.objects.get(game=game, user=request.user)
#	except:
#		player = Player.objects.none()
#	units = Unit.objects.filter(player__game=game)
#	player_list = game.player_list_ordered_by_cities()
#	context = {
#		'game': game,
#		'player': player,
#		'map': 'base-map.png',
#		'units': units,
#		'player_list': player_list,
#	}
#	return render_to_response('machiavelli/js_game.html',
#						context,
#						context_instance=RequestContext(request))
#

@login_required
def undo_actions(request, slug=''):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	player = get_object_or_404(machiavelli.Player, game=game, user=request.user)
	profile = request.user.get_profile()
	if request.method == 'POST' and player.done and not player.in_last_seconds():
		player.done = False
		if game.phase == machiavelli.PHREINFORCE:
			if game.configuration.finances:
				## first, delete new, not placed units
				units = machiavelli.Unit.objects.filter(player=player, placed=False)
				if units.count() > 0:
					costs = units.aggregate(Sum('cost'))
					ducats = costs['cost__sum']
				else:
					ducats = 0
				units.delete()
				## then mark all units as not paid, refund the money
				units = machiavelli.Unit.objects.filter(player=player, paid=True)
				if units.count() > 0:
					costs = units.aggregate(Sum('cost'))
					ducats += costs['cost__sum']
					units.update(paid=False)
				player.ducats += ducats
			else:
				## first, delete new, not placed units
				machiavelli.Unit.objects.filter(player=player, placed=False).delete()
				## then, mark all units as paid
				machiavelli.Unit.objects.filter(player=player).update(paid=True)
		elif game.phase == machiavelli.PHORDERS:
			player.order_set.update(confirmed=False)
			player.expense_set.update(confirmed=False)
			messages.success(request, _("Your actions are now unconfirmed. You'll have to confirm then again."))
		elif game.phase == machiavelli.PHRETREATS:
			machiavelli.RetreatOrder.objects.filter(unit__player=player).delete()
			messages.success(request, _("Your retreat orders have been undone."))
		if game.check_bonus_time():
			profile.adjust_karma( -1 )
		player.save()

	return redirect('show-game', slug=slug)

def show_inactive_game(request, game):
	context = sidebar_context(request)
	context.update({'game': game})
	started = (game.started is not None)
	finished = (game.finished is not None)
	context.update({'started': started, 'finished': finished})
	##TODO: move this to Game class
	## check if the user can join the game
	if not started:
		if request.user.is_authenticated():
			try:
				machiavelli.Player.objects.get(game=game, user=request.user)
			except ObjectDoesNotExist:
				joinable = True
			else:
				joinable = False
		else:
			joinable = True
	else:
		joinable = False
	context.update({'joinable': joinable})
	## if the game is finished, get the scores
	if finished:
		cache_key = "game-scores-%s" % game.id
		scores = cache.get(cache_key)
		if not scores:
			scores = game.score_set.filter(user__isnull=False).order_by('-points')
			cache.set(cache_key, scores)
		context.update({'map' : game.get_map_url(),
						'players': scores,})
		## get the logs, if they still exist
		log = game.baseevent_set.all()
		if len(log) > 0:
			context.update({'show_log': True})
		## show the overthrows history
		overthrows = machiavelli.Revolution.objects.filter(game=game, overthrow=True)
		if overthrows.count() > 0:
			context.update({'overthrows': overthrows})
	## comments section
	comments = game.gamecomment_set.public()
	context.update({'comments': comments})
	if request.method == 'POST':
		comment_form = forms.GameCommentForm(request.POST)
		if comment_form.is_valid():
			comment_form.save(user=request.user, game=game)
			return redirect(game)
	comment_form = forms.GameCommentForm()
	context.update({'comment_form': comment_form})

	return render_to_response('machiavelli/game_inactive.html',
						context,
						context_instance=RequestContext(request))

class TeamMessageListView(LoginRequiredMixin, ListAppendView):
	model = machiavelli.TeamMessage
	paginate_by = 20
	context_object_name = 'message_list'
	template_name = 'machiavelli/team_messages.html'
	form_class = forms.TeamMessageForm

	def get_success_url(self):
		return reverse('team_messages', kwargs={'slug': self.kwargs['slug']})

	def get_queryset(self):
		self.game = get_object_or_404(machiavelli.Game, slug=self.kwargs['slug'])
		if not self.game.is_team_game:
			raise Http404
		player = get_object_or_404(machiavelli.Player, user=self.request.user, game=self.game)
		return machiavelli.TeamMessage.objects.filter(player__team=player.team)

	def get_context_data(self, **kwargs):
		context = super(TeamMessageListView, self).get_context_data(**kwargs)
		context['game'] = self.game
		return context

	def form_valid(self, form):
		game = get_object_or_404(machiavelli.Game, slug=self.kwargs['slug'])
		player = get_object_or_404(machiavelli.Player, user=self.request.user, game=game)
		self.object = form.save(commit=False)
		self.object.player = player
		self.object.save()
		return super(TeamMessageListView, self).form_valid(form)

@never_cache
#@login_required
def play_game(request, slug='', **kwargs):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	if game.started is None or not game.finished is None or (game.paused and not request.user.is_staff):
		return show_inactive_game(request, game)
	try:
		player = machiavelli.Player.objects.get(game=game, user=request.user)
	except:
		player = machiavelli.Player.objects.none()
	if player:
		if game.phase == machiavelli.PHINACTIVE:
			context = base_context(request, game, player)
			return render_to_response('machiavelli/inactive_actions.html',
							context,
							context_instance=RequestContext(request))
		elif game.phase == machiavelli.PHREINFORCE:
			if game.configuration.finances:
				return play_finance_reinforcements(request, game, player)
			else:
				return play_reinforcements(request, game, player)
		elif game.phase == machiavelli.PHORDERS:
			if 'extra' in kwargs and kwargs['extra'] == 'expenses':
				if game.configuration.finances:
					return play_expenses(request, game, player)
			return play_orders(request, game, player)
		elif game.phase == machiavelli.PHRETREATS:
			return play_retreats(request, game, player)
		else:
			raise Http404
	## no player
	else:
		context = base_context(request, game, player)
		return render_to_response('machiavelli/inactive_actions.html',
							context,
							context_instance=RequestContext(request))

def play_reinforcements(request, game, player):
	context = base_context(request, game, player)
	units_to_place = player.units_to_place()
	if player.done:
		context['to_place'] = player.unit_set.filter(placed=False)
		context['to_disband'] = player.unit_set.filter(placed=True, paid=False)
		context['to_keep'] = player.unit_set.filter(placed=True, paid=True)
		if units_to_place == 0:
			context.update({'undoable': False})
	else:
		context['cities_qty'] = player.number_of_cities
		context['cur_units'] = len(player.unit_set.all())
		if units_to_place > 0:
			## place units
			context['units_to_place'] = units_to_place
			ReinforceForm = forms.make_reinforce_form(player)
			ReinforceFormSet = formset_factory(ReinforceForm,
								formset=forms.BaseReinforceFormSet,
								extra=units_to_place)
			if request.method == 'POST':
				reinforce_form = ReinforceFormSet(request.POST)
				if reinforce_form.is_valid():
					for f in reinforce_form.forms:
						new_unit = machiavelli.Unit(type=f.cleaned_data['type'],
								area=f.cleaned_data['area'],
								player=player,
								placed=False)
						new_unit.save()
					## not sure, but i think i could remove the fol. line
					player = machiavelli.Player.objects.get(id=player.pk) ## see below
					player.end_phase()
					messages.success(request, _("You have successfully made your reinforcements."))
					return HttpResponseRedirect(request.path)
			else:
				reinforce_form = ReinforceFormSet()
			context['reinforce_form'] = reinforce_form
		elif units_to_place < 0:
			## remove units
			DisbandForm = forms.make_disband_form(player)
			#choices = []
			context['units_to_disband'] = -units_to_place
			#for unit in player.unit_set.all():
			#	choices.append((unit.pk, unit))
			if request.method == 'POST':
				disband_form = DisbandForm(request.POST)
				if disband_form.is_valid():
					if len(disband_form.cleaned_data['units']) == -units_to_place:
						for u in disband_form.cleaned_data['units']:
							#u.delete()
							u.paid = False
							u.save()
						#game.map_changed()
						## odd: the player object needs to be reloaded or
						## the it doesn't know the change in game.map_outdated
						## this hack needs to be done in some other places
						player = machiavelli.Player.objects.get(id=player.pk)
						## --
						player.end_phase()
						messages.success(request, _("You have successfully made your reinforcements."))
						return HttpResponseRedirect(request.path)
			else:
				disband_form = DisbandForm()
			context['disband_form'] = disband_form
	return render_to_response('machiavelli/reinforcements_actions.html',
							context,
							context_instance=RequestContext(request))

def play_finance_reinforcements(request, game, player):
	context = base_context(request, game, player)
	if player.done:
		context['to_place'] = player.unit_set.filter(placed=False)
		context['to_disband'] = player.unit_set.filter(placed=True, paid=False)
		context['to_keep'] = player.unit_set.filter(placed=True, paid=True)
		template_name = 'machiavelli/reinforcements_actions.html'
	else:
		step = player.step
		if game.configuration.lenders:
			try:
				loan = player.loan
			except ObjectDoesNotExist:
				pass
			else:
				context.update({'loan': loan})
		if game.configuration.special_units:
			context.update({'special_units': True})
		if step == 0:
			## the player must select the units that he wants to pay and keep
			machiavelli.UnitPaymentForm = forms.make_unit_payment_form(player)
			if request.method == 'POST':
				form = machiavelli.UnitPaymentForm(request.POST)
				if form.is_valid():
					#cost = len(form.cleaned_data['units']) * 3
					cost = 0
					for u in form.cleaned_data['units']:
						cost += u.cost
					if cost <= player.ducats:
						for u in form.cleaned_data['units']:
							u.paid = True
							u.save()
						player.ducats = player.ducats - cost
						step = 1
						player.step = step
						player.save()
						messages.success(request, _("You have successfully paid your units."))
						return HttpResponseRedirect(request.path)
			else:
				form = machiavelli.UnitPaymentForm()
			context['form'] = form
		elif step == 1:
			## the player can create new units if he has money and areas
			can_buy = player.ducats / 3
			can_place = player.get_areas_for_new_units(finances=True).count()
			max_units = min(can_buy, can_place)
			ReinforceForm = forms.make_reinforce_form(player, finances=True,
												special_units=game.configuration.special_units)
			ReinforceFormSet = formset_factory(ReinforceForm,
								formset=forms.BaseReinforceFormSet,
								extra=max_units)
			if request.method == 'POST':
				if max_units > 0:
					try:
						formset = ReinforceFormSet(request.POST)
					except ValidationError:
						formset = None
				else:
					formset = None
					player.end_phase()
					messages.success(request, _("You have successfully made your reinforcements."))
					return HttpResponseRedirect(request.path)
				if formset and formset.is_valid():
					total_cost = 0
					new_units = []
					for f in formset.forms:
						if 'area' in f.cleaned_data:
							new_unit = machiavelli.Unit(type=f.cleaned_data['type'],
									area=f.cleaned_data['area'],
									player=player,
									placed=False)
							if 'unit_class' in f.cleaned_data:
								if not f.cleaned_data['unit_class'] is None:
									unit_class = f.cleaned_data['unit_class']
									## it's a special unit
									new_unit.cost = unit_class.cost
									new_unit.power = unit_class.power
									new_unit.loyalty = unit_class.loyalty
							new_units.append(new_unit)
							total_cost += new_unit.cost
					if total_cost > player.ducats:
						messages.error(request, _("You don't have enough ducats to buy these units."))
					else:
						for u in new_units:
							u.save()
						player.ducats = player.ducats - total_cost
						player.save()
						player.end_phase()
						messages.success(request, _("You have successfully made your reinforcements."))
					return HttpResponseRedirect(request.path)
				else:
					messages.error(request, _("There are one or more errors in the form below."))
			else:
				if max_units > 0:
					formset = ReinforceFormSet()
				else:
					formset = None
			context['formset'] = formset
			context['max_units'] = max_units
		else:
			raise Http404
		template_name = 'machiavelli/finance_reinforcements_%s.html' % step
	return render_to_response(template_name, context,
							context_instance=RequestContext(request))


def play_orders(request, game, player):
	context = base_context(request, game, player)
	#sent_orders = Order.objects.filter(unit__in=player.unit_set.all())
	sent_orders = player.order_set.all()
	context.update({'sent_orders': sent_orders})
	if game.configuration.finances:
		context['current_expenses'] = player.expense_set.all()
	if game.configuration.assassinations:
		context['assassinations'] = player.assassination_attempts.all()
	if game.configuration.lenders:
		try:
			loan = player.loan
		except ObjectDoesNotExist:
			pass
		else:
			context.update({'loan': loan})
	if not player.done:
		OrderForm = forms.make_order_form(player)
		if request.method == 'POST':
			order_form = OrderForm(player, data=request.POST)
			if request.is_ajax():
				## validate the form
				clean = order_form.is_valid()
				response_dict = {'bad': 'false'}
				if not clean:
					response_dict.update({'bad': 'true'})
					d = {}
					for e in order_form.errors.iteritems():
						d.update({e[0] : unicode(e[1])})
					response_dict.update({'errs': d})
				else:
					#new_order = Order(**order_form.cleaned_data)
					#new_order.save()
					new_order = order_form.save()
					response_dict.update({'pk': new_order.pk ,
										'new_order': new_order.explain()})
				response_json = simplejson.dumps(response_dict, ensure_ascii=False)

				return HttpResponse(response_json, mimetype='application/javascript')
			## not ajax
			else:
				if order_form.is_valid():
					#new_order = Order(**order_form.cleaned_data)
					#new_order.save()
					new_order = order_form.save()
					return HttpResponseRedirect(request.path)
		else:
			order_form = OrderForm(player)
		context.update({'order_form': order_form})
	return render_to_response('machiavelli/orders_actions.html',
							context,
							context_instance=RequestContext(request))

@login_required
def delete_order(request, slug='', order_id=''):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	player = get_object_or_404(machiavelli.Player, game=game, user=request.user)
	#order = get_object_or_404(Order, id=order_id, unit__player=player, confirmed=False)
	order = get_object_or_404(machiavelli.Order, id=order_id, player=player, confirmed=False)
	response_dict = {'bad': 'false',
					'order_id': order.id}
	try:
		order.delete()
	except:
		response_dict.update({'bad': 'true'})
	if request.is_ajax():
		response_json = simplejson.dumps(response_dict, ensure_ascii=False)
		return HttpResponse(response_json, mimetype='application/javascript')
		
	return redirect(game)

@login_required
def confirm_orders(request, slug=''):
	""" Confirms orders and expenses in Order Writing phase """
	game = get_object_or_404(machiavelli.Game, slug=slug)
	player = get_object_or_404(machiavelli.Player, game=game, user=request.user, done=False)
	if request.method == 'POST':
		msg = u"Confirming orders for player %s (%s, %s) in game %s (%s):\n" % (player.id,
			player.static_name,
			player.user.username,
			game.id,
			game.slug) 
		sent_orders = player.order_set.all()
		for order in sent_orders:
			msg += u"%s => " % order.format()
			if order.is_possible():
				order.confirm()
				msg += u"OK\n"
			else:
				msg += u"Invalid\n"
		## confirm expenses
		player.expense_set.all().update(confirmed=True)
		if logging:
			logger.info(msg)
		player.end_phase()
		messages.success(request, _("You have successfully confirmed your actions."))
	return redirect(game)		
	
def play_retreats(request, game, player):
	context = base_context(request, game, player)
	units = machiavelli.Unit.objects.filter(player=player).exclude(must_retreat__exact='')
	if units.count() <= 0:
		context.update({'undoable': False })
	if not player.done:
		retreat_forms = []
		if request.method == 'POST':
			data = request.POST
			for u in units:
				unitid_key = "%s-unitid" % u.id
				area_key = "%s-area" % u.id
				unit_data = {unitid_key: data[unitid_key], area_key: data[area_key]}
				RetreatForm = forms.make_retreat_form(u)
				retreat_forms.append(RetreatForm(data, prefix=u.id))
			for f in retreat_forms:
				if f.is_valid():
					unitid = f.cleaned_data['unitid']
					area= f.cleaned_data['area']
					unit = machiavelli.Unit.objects.get(id=unitid)
					if isinstance(area, machiavelli.GameArea):
						retreat = machiavelli.RetreatOrder(unit=unit, area=area)
					else:
						retreat = machiavelli.RetreatOrder(unit=unit)
					retreat.save()
			player.end_phase()
			messages.success(request, _("You have successfully retreated your units."))
			return HttpResponseRedirect(request.path)
		else:
			for u in units:
				RetreatForm = forms.make_retreat_form(u)
				retreat_forms.append(RetreatForm(prefix=u.id))
		if len(retreat_forms) > 0:
			context['retreat_forms'] = retreat_forms
	return render_to_response('machiavelli/retreats_actions.html',
							context,
							context_instance=RequestContext(request))

def play_expenses(request, game, player):
	context = base_context(request, game, player)
	context['current_expenses'] = player.expense_set.all()
	ExpenseForm = forms.make_expense_form(player)
	if request.method == 'POST':
		form = ExpenseForm(player, data=request.POST)
		if form.is_valid():
			expense = form.save()
			player.ducats = F('ducats') - expense.ducats
			player.save()
			messages.success(request, _("Expense successfully saved."))
			return HttpResponseRedirect(request.path)
	else:
		form = ExpenseForm(player)

	context['form'] = form

	return render_to_response('machiavelli/expenses_actions.html',
							context,
							context_instance=RequestContext(request))

@login_required
def undo_expense(request, slug='', expense_id=''):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	player = get_object_or_404(machiavelli.Player, game=game, user=request.user)
	expense = get_object_or_404(machiavelli.Expense, id=expense_id, player=player)
	try:
		expense.undo()
	except:
		messages.error(request, _("Expense could not be undone."))
	else:
		messages.success(request, _("Expense successfully undone."))
		
	return redirect(game)

#@login_required
#def game_results(request, slug=''):
#	game = get_object_or_404(Game, slug=slug)
#	if game.phase != PHINACTIVE:
#		raise Http404
#	cache_key = "game-scores-%s" % game.id
#	scores = cache.get(cache_key)
#	if not scores:
#		scores = game.score_set.filter(user__isnull=False).order_by('-points')
#		cache.set(cache_key, scores)
#	context = {'game': game,
#				'map' : game.get_map_url(),
#				'players': scores,
#				'show_log': False,}
#	log = game.baseevent_set.all()
#	if len(log) > 0:
#		context['show_log'] = True
#	return render_to_response('machiavelli/game_results.html',
#							context,
#							context_instance=RequestContext(request))

@never_cache
#@login_required
def logs_by_game(request, slug=''):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	try:
		player = machiavelli.Player.objects.get(game=game, user=request.user)
	except:
		player = machiavelli.Player.objects.none()
	context = base_context(request, game, player)
	log_list = game.baseevent_set.exclude(year__exact=game.year,
										season__exact=game.season,
										phase__exact=game.phase)
	paginator = events_paginator.SeasonPaginator(log_list)
	try:
		year = int(request.GET.get('year'))
	except TypeError:
		year = None
	try:
		season = int(request.GET.get('season'))
	except TypeError:
		season = None
	try:
		log = paginator.page(year, season)
	except (events_paginator.EmptyPage, events_paginator.InvalidPage):
		raise Http404

	context['log'] = log

	return render_to_response('machiavelli/log_list.html',
							context,
							context_instance=RequestContext(request))

@login_required
def create_game(request, teams=False):
	context = sidebar_context(request)
	context.update( {'user': request.user,})
	if teams:
		form_cls = forms.TeamGameForm
		context['teams'] = True
	else:
		form_cls = forms.GameForm
	if request.method == 'POST':
		game_form = form_cls(request.user, data=request.POST)
		config_form = forms.ConfigurationForm(request.POST)
		if game_form.is_valid():
			new_game = game_form.save(commit=False)
			new_game.slots = new_game.scenario.number_of_players - 1
			new_game.save()
			new_player = machiavelli.Player()
			new_player.user = request.user
			new_player.game = new_game
			new_player.save()
			config_form = forms.ConfigurationForm(request.POST,
												instance=new_game.configuration)
			config_form.save()
			cache.delete('sidebar_activity')
			player_joined.send(sender=new_player)
			messages.success(request, _("Game successfully created."))
			if new_game.private:
				return redirect('invite-users', slug=new_game.slug)
			else:
				return redirect(new_game)
	else:
		game_form = form_cls(request.user)
		config_form = forms.ConfigurationForm()
	context['scenarios'] = scenarios.Scenario.objects.filter(enabled=True)
	context['game_form'] = game_form
	context['config_form'] = config_form
	return render_to_response('machiavelli/game_form.html',
							context,
							context_instance=RequestContext(request))

@login_required
def invite_users(request, slug=''):
	g = get_object_or_404(machiavelli.Game, slug=slug)
	## check that the game is open
	if g.slots == 0:
		raise Http404
	## check that the current user is the creator of the game
	if g.created_by != request.user:
		raise Http404
	context = sidebar_context(request)
	context.update({'game': g,})
	context.update({'players': g.player_set.exclude(user__isnull=True)})
	invitations = machiavelli.Invitation.objects.filter(game=g)
	context.update({'invitations': invitations})
	if request.method == 'POST':
		form = forms.InvitationForm(request.POST)
		if form.is_valid():
			message = form.cleaned_data['message']
			user_list = form.cleaned_data['user_list']
			user_names = user_list.split(',')
			success_list = []
			fail_list = []
			for u in user_names:
				name = u.strip()
				try:
					user = User.objects.get(username=name)
				except ObjectDoesNotExist:
					fail_list.append(name)
					continue
				else:
					## check that the user is not already in the game
					try:
						machiavelli.Player.objects.get(game=g, user=user)
					except ObjectDoesNotExist:
						## check for existing invitation
						try:
							machiavelli.Invitation.objects.get(game=g, user=user)
						except ObjectDoesNotExist:
							i = machiavelli.Invitation()
							i.game = g
							i.user = user
							i.message = message
							i.save()
							success_list.append(name)
						else:
							fail_list.append(name)
					else:
						fail_list.append(name)
			if len(success_list) > 0:
				msg = _("The following users have been invited: %s") % ", ".join(success_list)
				messages.success(request, msg)
			if len(fail_list) > 0:
				msg = _("The following users could not be invited: %s") % ", ".join(fail_list)
				messages.error(request, msg)
	else:
		form = forms.InvitationForm()
	context.update({'form': form})
	return render_to_response('machiavelli/invitation_form.html',
							context,
							context_instance=RequestContext(request))

@login_required
def join_game(request, slug=''):
	g = get_object_or_404(machiavelli.Game, slug=slug)
	invitation = None
	## check if the user has defined his languages
	if not request.user.get_profile().has_languages():
		messages.error(request, _("You must define at least one known language before joining a game."))
		messages.info(request, _("Define your languages and then, try again."))
		return redirect("profile_languages_edit")
	if g.private:
		## check if user has been invited
		try:
			invitation = machiavelli.Invitation.objects.get(game=g, user=request.user)
		except ObjectDoesNotExist:
			messages.error(request, _("This game is private and you have not been invited."))
			return redirect("games-joinable")
	else:
		karma = request.user.get_profile().karma
		if karma < settings.KARMA_TO_JOIN:
			err = _("You need a minimum karma of %s to join a game.") % settings.KARMA_TO_JOIN
			messages.error(request, err)
			return redirect("summary")
		if g.fast and karma < settings.KARMA_TO_FAST:
			err = _("You need a minimum karma of %s to join a fast game.") % settings.KARMA_TO_FAST
			messages.error(request, err)
			return redirect("games-joinable")
	if g.slots > 0:
		try:
			machiavelli.Player.objects.get(user=request.user, game=g)
		except:
			## the user is not in the game
			new_player = machiavelli.Player(user=request.user, game=g)
			new_player.save()
			if invitation:
				invitation.delete()
			g.player_joined()
			player_joined.send(sender=new_player)
			messages.success(request, _("You have successfully joined the game."))
			cache.delete('sidebar_activity')
			return redirect(g)
		else:
			messages.error(request, _("You had already joined this game."))
	return redirect('summary')

@login_required
def leave_game(request, slug=''):
	g = get_object_or_404(machiavelli.Game, slug=slug, slots__gt=0)
	try:
		player = machiavelli.Player.objects.get(user=request.user, game=g)
	except:
		## the user is not in the game
		messages.error(request, _("You had not joined this game."))
	else:
		player.delete()
		g.slots += 1
		g.save()
		cache.delete('sidebar_activity')
		messages.success(request, _("You have left the game."))
		## if the game has no players, delete the game
		if g.player_set.count() == 0:
			g.delete()
			messages.info(request, _("The game has been deleted."))
	return redirect('summary')

@login_required
def make_public(request, slug=''):
	g = get_object_or_404(machiavelli.Game, slug=slug, slots__gt=0,
						private=True, created_by=request.user)
	g.private = False
	g.save()
	g.invitation_set.all().delete()
	messages.success(request, _("The game is now open to all users."))
	return redirect('games-pending')

@login_required
def overthrow(request, revolution_id):
	revolution = get_object_or_404(machiavelli.Revolution, pk=revolution_id)
	g = revolution.game
	try:
		## check that overthrowing user is not a player
		machiavelli.Player.objects.get(user=request.user, game=g)
	except ObjectDoesNotExist:
		try:
			## check that there is not another revolution with the same player
			machiavelli.Revolution.objects.get(game=g, opposition=request.user)
		except ObjectDoesNotExist:
			karma = request.user.get_profile().karma
			if karma < settings.KARMA_TO_JOIN:
				err = _("You need a minimum karma of %s to join a game.") % settings.KARMA_TO_JOIN
				messages.error(request, err)
				return redirect("summary")
			revolution.opposition = request.user
			revolution.save()
			messages.success(request, _("Your overthrow attempt has been saved."))
		else:
			messages.error(request, _("You are already attempting an overthrow on another player in the same game."))
	else:
		messages.error(request, _("You are already playing this game."))
	return redirect("summary")

@login_required
def excommunicate(request, slug, player_id):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	if game.phase == 0 or not game.configuration.excommunication:
		messages.error(request, _("You cannot excommunicate in this game."))
		return redirect(game)
	papacy = get_object_or_404(machiavelli.Player, user=request.user,
								game=game,
								may_excommunicate=True)
	if not papacy.can_excommunicate():
		messages.error(request, _("You cannot excommunicate in the current season."))
		return redirect(game)
	try:
		player = machiavelli.Player.objects.get(game=game, id=player_id, eliminated=False,
									conqueror__isnull=True, may_excommunicate=False)
	except ObjectDoesNotExist:
		messages.error(request, _("You cannot excommunicate this country."))
	else:
		player.set_excommunication(by_pope=True)
		papacy.has_sentenced = True
		papacy.save()
		messages.success(request, _("The country has been excommunicated."))
	return redirect(game)

@login_required
def forgive_excommunication(request, slug, player_id):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	if game.phase == 0 or not game.configuration.excommunication:
		messages.error(request, _("You cannot forgive excommunications in this game."))
		return redirect(game)
	papacy = get_object_or_404(machiavelli.Player, user=request.user,
								game=game,
								may_excommunicate=True)
	if not papacy.can_forgive():
		messages.error(request, _("You cannot forgive excommunications in the current season."))
		return redirect(game)
	try:
		player = machiavelli.Player.objects.get(game=game, id=player_id, eliminated=False,
									conqueror__isnull=True, is_excommunicated=True)
	except ObjectDoesNotExist:
		messages.error(request, _("You cannot forgive this country."))
	else:
		player.unset_excommunication()
		papacy.has_sentenced = True
		papacy.save()
		messages.success(request, _("The country has been forgiven."))
	return redirect(game)

class HallOfFameView(ListView):
	allow_empty = False
	model = CondottieriProfile
	paginate_by = 10
	context_object_name = 'profiles_list'
	template_name = 'machiavelli/hall_of_fame.html'

	def get_queryset(self):
		order = self.request.GET.get('o', 'w')
		return CondottieriProfile.objects.hall_of_fame(order=order)
	
	def render_to_response(self, context, **kwargs):
		return super(HallOfFameView, self).render_to_response(
			RequestContext(self.request,
				context,
				processors=[activity, sidebar_ranking,]),
			**kwargs)
	
	def get_context_data(self, **kwargs):
		context = super(HallOfFameView, self).get_context_data(**kwargs)
		context['order'] = self.request.GET.get('o', 'w')
		return context

def ranking(request, key='', val=''):
	""" Gets the qualification, ordered by scores, for a given parameter. """
	
	scores = machiavelli.Score.objects.all().order_by('-points')
	if key == 'user': # by user
		user = get_object_or_404(User, username=val)
		scores = scores.filter(user=user)
		title = _("Ranking for the user") + ' ' + val
	elif key == 'scenario': # by scenario
		scenario = get_object_or_404(scenarios.Scenario, name=val)
		scores = scores.filter(game__scenario=scenario)
		title = _("Ranking for the scenario") + ' ' + val
	elif key == 'country': # by country
		country = get_object_or_404(scenarios.Country, static_name=val)
		scores = scores.filter(country=country)
		title = _("Ranking for the country") + ' ' + country.name
	else:
		raise Http404

	paginator = Paginator(scores, 10)
	try:
		page = int(request.GET.get('page', '1'))
	except ValueError:
		page = 1
	try:
		qualification = paginator.page(page)
	except (EmptyPage, InvalidPage):
		qualification = paginator.page(paginator.num_pages)
	context = {
		'qualification': qualification,
		'key': key,
		'val': val,
		'title': title,
		}
	return render_to_response('machiavelli/ranking.html',
							context,
							context_instance=RequestContext(request))

class TurnLogListView(LoginRequiredMixin, ListView):
	model = machiavelli.TurnLog
	paginate_by = 1
	context_object_name = 'turnlog_list'
	template_name = 'machiavelli/turn_log_list.html'

	def get_queryset(self):
		self.game = get_object_or_404(machiavelli.Game, slug=self.kwargs['slug'])
		return self.game.turnlog_set.all()

	def get_context_data(self, **kwargs):
		context = super(TurnLogListView, self).get_context_data(**kwargs)
		context['game'] = self.game
		return context

@login_required
def give_money(request, slug, player_id):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	if game.phase == 0 or not game.configuration.finances:
		messages.error(request, _("You cannot give money in this game."))
		return redirect(game)
	borrower = get_object_or_404(machiavelli.Player, id=player_id, game=game)
	lender = get_object_or_404(machiavelli.Player, user=request.user, game=game)
	context = base_context(request, game, lender)

	if request.method == 'POST':
		form = forms.LendForm(request.POST)
		if form.is_valid():
			ducats = form.cleaned_data['ducats']
			if ducats > lender.ducats:
				##TODO Move this to form validation
				messages.error(request, _("You cannot give more money than you have"))
				return redirect(game)
			lender.ducats = F('ducats') - ducats
			borrower.ducats = F('ducats') + ducats
			lender.save()
			borrower.save()
			messages.success(request, _("The money has been successfully sent."))
			if notification:
				extra_context = {'game': lender.game,
								'ducats': ducats,
								'country': lender.contender.country,
								'STATIC_URL': settings.STATIC_URL}
				if lender.game.fast:
					notification.send_now([borrower.user,], "received_ducats", extra_context)
				else:
					notification.send([borrower.user,], "received_ducats", extra_context)
			return redirect(game)
	else:
		form = forms.LendForm()
	context['form'] = form
	context['borrower'] = borrower

	return render_to_response('machiavelli/give_money.html',
							context,
							context_instance=RequestContext(request))

@login_required
def borrow_money(request, slug):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	player = get_object_or_404(machiavelli.Player, user=request.user, game=game)
	if game.phase != machiavelli.PHORDERS or not game.configuration.lenders or player.done:
		messages.error(request, _("You cannot borrow money in this moment."))
		return redirect(game)
	context = base_context(request, game, player)
	credit = player.get_credit()
	try:
		loan = player.loan
	except ObjectDoesNotExist:
		## the player may ask for a loan
		if request.method == 'POST':
			form = forms.BorrowForm(request.POST)
			if form.is_valid():
				ducats = form.cleaned_data['ducats']
				term = int(form.cleaned_data['term'])
				if ducats > credit:
					messages.error(request, _("You cannot borrow so much money."))
					return redirect("borrow-money", slug=slug)
				loan = machiavelli.Loan(player=player, season=game.season)
				if term == 1:
					loan.debt = int(ceil(ducats * 1.2))
				elif term == 2:
					loan.debt = int(ceil(ducats * 1.5))
				else:
					messages.error(request, _("The chosen term is not valid."))
					return redirect("borrow-money", slug=slug)
				loan.year = game.year + term
				loan.save()
				player.ducats = F('ducats') + ducats
				player.save()
				messages.success(request, _("You have got the loan."))
				return redirect(game)
		else:
			form = forms.BorrowForm()
	else:
		## the player must repay a loan
		context.update({'loan': loan})
		if request.method == 'POST':
			if player.ducats >= loan.debt:
				player.ducats = F('ducats') - loan.debt
				player.save()
				loan.delete()
				messages.success(request, _("You have repaid the loan."))
			else:
				messages.error(request, _("You don't have enough money to repay the loan."))
			return redirect(game)
		else:
			form = forms.RepayForm()
	context.update({'credit': credit,
					'form': form,})

	return render_to_response('machiavelli/borrow_money.html',
							context,
							context_instance=RequestContext(request))

@login_required
def assassination(request, slug):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	player = get_object_or_404(machiavelli.Player, user=request.user, game=game)
	if game.phase != machiavelli.PHORDERS or not game.configuration.assassinations or player.done:
		messages.error(request, _("You cannot buy an assassination in this moment."))
		return redirect(game)
	context = base_context(request, game, player)
	AssassinationForm = forms.make_assassination_form(player)
	if request.method == 'POST':
		form = AssassinationForm(request.POST)
		if form.is_valid():
			ducats = int(form.cleaned_data['ducats'])
			country = form.cleaned_data['target']
			target = machiavelli.Player.objects.get(game=game, contender__country=country)
			if ducats > player.ducats:
				messages.error(request, _("You don't have enough ducats for the assassination."))
				return redirect(game)
			if target.eliminated:
				messages.error(request, _("You cannot kill an eliminated player."))
				return redirect(game)
			if target == player:
				messages.error(request, _("You cannot kill yourself."))
				return redirect(game)
			try:
				assassin = machiavelli.Assassin.objects.get(owner=player, target=country)
			except ObjectDoesNotExist:
				messages.error(request, _("You don't have any assassins to kill this leader."))
				return redirect(game)
			except MultipleObjectsReturned:
				assassin = machiavelli.Assassin.objects.filter(owner=player, target=country)[0]
			## everything is ok and we should have an assassin token
			assassination = machiavelli.Assassination(killer=player, target=target, ducats=ducats)
			assassination.save()
			assassin.delete()
			player.ducats = F('ducats') - ducats
			player.save()
			messages.success(request, _("The assassination attempt has been saved."))

			return redirect(game)
	else:
		form = AssassinationForm()
	context.update({'form': form,})
	return render_to_response('machiavelli/assassination.html',
							context,
							context_instance=RequestContext(request))

@login_required
def new_whisper(request, slug):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	try:
		player = machiavelli.Player.objects.get(user=request.user, game=game)
	except ObjectDoesNotExist:
		messages.error(request, _("You cannot write messages in this game"))
		return redirect(game)
	if request.method == 'POST':
		form = forms.WhisperForm(request.POST)
		if form.is_valid():
			whisper = form.save(commit=False)
			whisper.user=request.user
			whisper.game=game
			whisper.save()
	return redirect(game)

class WhisperListView(LoginRequiredMixin, ListAppendView):
	model = machiavelli.Whisper
	paginate_by = 20
	context_object_name = 'whisper_list'
	template_name_suffix = '_list'
	form_class = forms.WhisperForm

	def get_success_url(self):
		return reverse('whisper-list', kwargs={'slug': self.kwargs['slug']})

	def get_queryset(self):
		self.game = get_object_or_404(machiavelli.Game, slug=self.kwargs['slug'])
		return self.game.whisper_set.all()

	def get_context_data(self, **kwargs):
		context = super(WhisperListView, self).get_context_data(**kwargs)
		context['game'] = self.game
		try:
			player = machiavelli.Player.objects.get(user=self.request.user, game=self.game)
		except ObjectDoesNotExist:
			player = machiavelli.Player.objects.none()
		context['player'] = player
		return context

	def form_valid(self, form):
		self.object = form.save(commit=False)
		self.object.user = self.request.user
		self.object.game = get_object_or_404(machiavelli.Game, slug=self.kwargs['slug'])
		self.object.save()
		return super(WhisperListView, self).form_valid(form)

@login_required
def edit_journal(request, slug):
	game = get_object_or_404(machiavelli.Game, slug=slug)
	player = get_object_or_404(machiavelli.Player, game=game, user=request.user)
	context = base_context(request, game, player)
	try:
		journal = machiavelli.Journal.objects.get(user=request.user, game=game)
	except ObjectDoesNotExist:
		tip = _("What you write above these symbols\n\n%%\n\nwill be shown in the sidebar")
		journal = machiavelli.Journal(content=tip)
	if request.method == 'POST':
		form = forms.JournalForm(request.user, game, instance=journal, data=request.POST)
		if form.is_valid():
			journal = form.save()
			messages.success(request, _("Your journal has been updated."))
			return redirect(game)
		else:
			messages.error(request, _("Your journal could not be saved."))
	else:
		form = forms.JournalForm(request.user, game, instance=journal)
	context.update({'journal': journal,
					'form': form,})
	return render_to_response('machiavelli/edit_journal.html',
							context,
							context_instance=RequestContext(request))

