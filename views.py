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
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.forms.formsets import formset_factory
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
from django.views.generic.base import View, TemplateView
from django.views.generic.list import ListView
from django.views.generic.edit import FormMixin, FormView

## pybb
if 'pybb' in settings.INSTALLED_APPS:
	import pybb.models as pybb
else:
	pybb = None

## machiavelli
import machiavelli.models as machiavelli
import machiavelli.forms as forms
from machiavelli.signals import player_joined, overthrow_attempted
from machiavelli.context_processors import activity, latest_gossip
from machiavelli.listappend import ListAppendView

## condottieri_scenarios
import condottieri_scenarios.models as scenarios

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

SUMMARY_FORUM_THREADS = getattr(settings, 'SUMMARY_FORUM_THREADS', 5)

reverse_lazy = lambda name=None, *args : lazy(reverse, str)(name, args=args)

def get_game_or_404(**kwargs):
	return get_object_or_404(machiavelli.Game, **kwargs)

def get_player_or_404(**kwargs):
	return get_object_or_404(machiavelli.Player, **kwargs)

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
		context['comments'] = machiavelli.GameComment.objects.public(). \
			order_by('-id')[:3]
		if self.request.user.is_authenticated():
			joinable = machiavelli.Game.objects.joinable(self.request.user)
			promoted_game = machiavelli.Game.objects.get_promoted(
				self.request.user)
			"""List of games that require the user's attention"""
			my_players = machiavelli.Player.objects.waited(
				user=self.request.user
			)
			player_list = []
			for p in my_players:
				p.deadline = p.next_phase_change()
				player_list.append(p)
			player_list.sort(
				cmp=lambda x,y: cmp(x.deadline, y.deadline), 
				reverse=False
			)
			context.update({ 'actions': player_list })
			"""Unseen notices"""
			if notification:
				context['new_notices'] = notification.Notice.objects. \
				notices_for(self.request.user, unseen=True, on_site=True)[:20]
		else:
			joinable = machiavelli.Game.objects.joinable()
			promoted_game = machiavelli.Game.objects.get_promoted()
		context['joinable_count'] = joinable.count()
		#if promoted_game is not None:
		try:
			num_comments = promoted_game.gamecomment_set.count()
		except AttributeError:
			pass
		else:
			context.update({
				'promoted_game': promoted_game,
				'num_comments': num_comments
			})
		##TODO: Refactor this in condottieri_scenarios
		week = timedelta(seconds=60*60*24*7)
		new_scenario_date = datetime.now() - 4 * week # one month ago
		recent_scenarios = scenarios.Scenario.objects.filter(published__gt=new_scenario_date).order_by('-published')
		if recent_scenarios.count() > 0:
			context.update({'new_scenario': recent_scenarios[0] })
		"""Latest forum threads"""
		if pybb:
			latest_pybb = pybb.Topic.objects.all().order_by('-updated')
			context.update({
				'latest_pybb': latest_pybb[0:SUMMARY_FORUM_THREADS],
			})
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
			my_players = machiavelli.Player.objects.active(
				user=self.request.user
			).select_related(
				"contender",
				"game__scenario",
				"game__configuration")
		else:
			my_players = machiavelli.Player.objects.none()
		player_list = []
		for p in my_players:
			p.deadline = p.next_phase_change()
			player_list.append(p)
		player_list.sort(
			cmp=lambda x,y: cmp(x.deadline, y.deadline),
			reverse=False
		)
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
			if user_id is None:
				games = machiavelli.LiveGame.objects.all()
			else:
				games = machiavelli.LiveGame.objects.exclude(
					player__user=self.request.user
				)
			cache.set(cache_key, games)
		return games

class AllFinishedGamesList(GameListView):
	template_name_suffix = "_list_finished"

	def get_queryset(self):
		cache_key = "finished_games"
		games = cache.get(cache_key)
		if not games:
			games = machiavelli.Game.objects.finished().order_by('-finished'). \
				annotate(comments_count=Count('gamecomment'))
			cache.set(cache_key, games)
		return games

class MyFinishedGamesList(LoginRequiredMixin, GameListView):
	template_name_suffix = "_list_finished"

	def get_queryset(self):
		cache_key = "finished_games-%s" % self.request.user.id
		games = cache.get(cache_key)
		if not games:
			games = machiavelli.Game.objects.finished(user=self.request.user). \
				order_by('-finished'). \
				annotate(comments_count=Count('gamecomment'))
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
		if self.request.user.is_authenticated():
			return machiavelli.Game.objects.joinable(
				self.request.user
			).annotate(comments_count=Count('gamecomment'))
		else:
			return machiavelli.Game.objects.joinable().annotate(
				comments_count=Count('gamecomment'))
			
	def get_context_data(self, **kwargs):
		context = super(JoinableGamesList, self).get_context_data(**kwargs)
		context["joinable"] = True
		return context

class PendingGamesList(LoginRequiredMixin, GameListView):
	"""Get a paginated list of all the games of the player that have not
	yet started """
	template_name_suffix = '_list_pending'

	def get_queryset(self):
		cache_key = "pending_games-%s" % self.request.user.id
		games = cache.get(cache_key)
		if not games:
			games = machiavelli.Game.objects.pending(self.request.user). \
				annotate(comments_count=Count('gamecomment'))
			cache.set(cache_key, games, 10*60)
		return games

	def get_context_data(self, **kwargs):
		context = super(PendingGamesList, self).get_context_data(**kwargs)
		context["joinable"] = False
		return context

class RevolutionList(LoginRequiredMixin, ListView):
	model = machiavelli.Revolution
	paginate_by = 10
	context_object_name = 'revolution_list'
	
	def render_to_response(self, context, **kwargs):
		return super(RevolutionList, self).render_to_response(
			RequestContext(self.request,
				context,
				processors=[activity, sidebar_ranking,]),
			**kwargs)

	def get_queryset(self):
		return machiavelli.Revolution.objects.open().order_by("-active")

class GameMixin(object):
	game = None
	player = None

	def get_game(self, request, *args, **kwargs):
		if not self.game:
			self.game = get_game_or_404(
				slug=kwargs['slug'],
				started__isnull=False,
				finished__isnull=True)
		return self.game

	def get_player(self, request, *args, **kwargs):
		if not self.player:
			if request.user.is_authenticated():
				try:
					self.player = self.game.player_set.get(
						user=request.user,
						eliminated=False,
						surrendered=False
					)
				except ObjectDoesNotExist:
					self.player = machiavelli.Player.objects.none()
			else:
				self.player = machiavelli.Player.objects.none()

class GamePlayView(LoginRequiredMixin, TemplateView, GameMixin):
	def get_template_names(self):
		if self.game.started is not None \
			and self.game.finished is None \
			and self.game.phase != machiavelli.PHINACTIVE \
			and not (self.game.paused and not request.user.is_staff):
			if not self.player:
				return ['machiavelli/inactive_actions.html',]
		return super(GamePlayView, self).get_template_names()

	def dispatch(self, request, *args, **kwargs):
		self.get_game(request, *args, **kwargs)
		self.get_player(request, *args, **kwargs)
		return super(GamePlayView, self).dispatch(request, *args, **kwargs)
	
	def get(self, request, *args, **kwargs):
		try:
			form_class = self.get_form_class()
		except AttributeError:
			form = None
		else:
			form = self.get_form(form_class)
		return self.render_to_response(self.get_context_data(form=form))
    
	def post(self, request, *args, **kwargs):
		form_class = self.get_form_class()
		form = self.get_form(form_class)
		if form.is_valid():
			return self.form_valid(form)
		else:
			return self.form_invalid(form)

	def get_context_data(self, **kwargs):
		ctx = super(GamePlayView, self).get_context_data(**kwargs)
		ctx.update(get_game_context(self.request, self.game, self.player))
		ctx.update(**kwargs)
		return ctx

class AssassinationView(GamePlayView, FormMixin):
	template_name = 'machiavelli/assassination.html'

	def get_context_data(self, **kwargs):
		ctx = super(AssassinationView, self).get_context_data(**kwargs)
		if self.game.phase != machiavelli.PHORDERS \
			or not self.game.configuration.assassinations \
			or self.player is None:
			raise Http404
		elif self.player.done:
			messages.error(
				self.request,
				_("You cannot buy an assassination in this moment.")
			)
			return redirect(self.game)
		return ctx

	def get_form_class(self):
		return forms.make_assassination_form(self.player)

	def form_valid(self, form):
		ducats = int(form.cleaned_data['ducats'])
		country = form.cleaned_data['target']
		target = machiavelli.Player.objects.get(
			game=self.game,
			contender__country=country
		)
		if ducats > self.player.ducats:
			messages.error(
				self.request,
				_("You don't have enough ducats for the assassination.")
			)
			return redirect(self.game)
		if target.eliminated:
			messages.error(
				self.request,
				_("You cannot kill an eliminated player.")
			)
			return redirect(self.game)
		if target == self.player:
			messages.error(self.request, _("You cannot kill yourself."))
			return redirect(self.game)
		assassins = self.player.assassin_set.filter(target=country)
		if assassins.count() == 0:
			messages.error(
				self.request,
				_("You don't have any assassins to kill this leader.")
			)
			return redirect(self.game)
		else:
			assassin = assassins[0]
			assassination = machiavelli.Assassination(
				killer=self.player,
				target=target,
				ducats=ducats
			)
			assassination.save()
			assassin.delete()
			self.player.ducats = F('ducats') - ducats
			self.player.save()
			messages.success(
				self.request,
				_("The assassination attempt has been saved.")
			)
		return redirect(self.game)

class BorrowMoneyView(GamePlayView, FormMixin):
	template_name = 'machiavelli/borrow_money.html'
	form_class = forms.BorrowForm

	def get_context_data(self, **kwargs):
		ctx = super(BorrowMoneyView, self).get_context_data(**kwargs)
		if self.game.phase != machiavelli.PHORDERS \
			or not self.game.configuration.lenders \
			or self.player is None:
			raise Http404
		elif self.player.done:
			messages.error(
				self.request,
				_("You cannot borrow money in this moment.")
			)
			return redirect(self.game)
		credit_limit = self.player.get_credit()
		if credit_limit <= 0:
			messages.error(
				self.request,
				_("You have already consumed all your credit.")
			)
			return redirect(self.game)
		ctx.update({'credit_limit': credit_limit})
		return ctx

	def form_valid(self, form):
		ducats = form.cleaned_data['ducats']
		term = int(form.cleaned_data['term'])
		if ducats > self.player.get_credit():
			messages.error(
				self.request,
				_("You cannot borrow so much money.")
			)
			return HttpResponseRedirect(self.request.path)
		credit = machiavelli.Credit(
			player = self.player,
			principal = ducats,
			season = self.game.season,
			year = self.game.year + term
		)
		if term == 1:
			credit.debt = int(ceil(ducats * 1.2))
		elif term == 2:
			credit.debt = int(ceil(ducats * 1.5))
		else:
			messages.error(self.request, _("The chosen term is not valid."))
			return HttpResponseRedirect(self.request.path)
		credit.save()
		self.player.ducats = F('ducats') + ducats
		self.player.save()
		messages.success(self.request, _("You have got the loan."))
		return redirect(self.game)

class ConfirmOrdersView(GamePlayView):
	def post(self, request, *args, **kwargs):
		if self.player:
			msg = u"Confirming orders for player %s (%s, %s) in game %s (%s):\n" % (
				self.player.id,
				self.player.static_name,
				self.player.user.username,
				self.game.id,
				self.game.slug
			) 
			sent_orders = self.player.order_set.all()
			for order in sent_orders:
				msg += u"%s => " % order.format()
				if order.is_possible():
					order.confirm()
					msg += u"OK\n"
				else:
					msg += u"Invalid\n"
			## confirm expenses
			self.player.expense_set.all().update(confirmed=True)
			logger.info(msg)
			self.player.end_phase()
			messages.success(request, _("You have successfully confirmed your actions."))
		return redirect(self.game)

class DeleteOrderView(GamePlayView):
	def get(self, request, *args, **kwargs):
		order = get_object_or_404(
			machiavelli.Order,
			id=self.kwargs['order_id'],
			player=self.player,
			confirmed=False
		)
		response_dict = {
			'bad': 'false',
			'order_id': order.id
		}
		try:
			order.delete()
		except:
			response_dict.update({'bad': 'true'})
		if request.is_ajax():
			response_json = simplejson.dumps(response_dict, ensure_ascii=False)
			return HttpResponse(response_json, mimetype='application/javascript')		
		return redirect(self.game)

class EditJournalView(GamePlayView):
	template_name = 'machiavelli/edit_journal.html'

	def get_journal(self, request):
		try:
			journal = machiavelli.Journal.objects.get(user=request.user, game=self.game)
		except ObjectDoesNotExist:
			tip = _("What you write above these symbols\n\n%%\n\nwill be shown in the sidebar")
			journal = machiavelli.Journal(content=tip)
		return journal

	def get(self, request, *args, **kwargs):
		if not self.player:
			raise Http404
		journal = self.get_journal(request)
		form = forms.JournalForm(request.user, self.game, instance=journal)
		return self.render_to_response(self.get_context_data(form=form, journal=journal))
	
	def post(self, request, *args, **kwargs):
		if not self.player:
			raise Http404
		journal = self.get_journal(request)
		form = forms.JournalForm(request.user, self.game, instance=journal, data=request.POST)
		if form.is_valid():
			journal = form.save()
			messages.success(request, _("Your journal has been updated."))
			return redirect(self.game)
		else:
			messages.error(request, _("Your journal could not be saved."))
		return self.render_to_response(self.get_context_data(form=form, journal=journal))

class ErrorReportCreateView(GamePlayView, FormMixin):
	template_name = 'machiavelli/error_report_form.html'
	form_class = forms.ErrorReportForm

	def form_valid(self, form):
		if self.player:
			form.save(self.request.user, self.game)
			messages.success(
				self.request,
				_("Your error report has been saved")
			)
			return redirect(self.game)

class ExcommunicationView(GamePlayView):
	action = ""

	def get(self, request, *args, **kwargs):
		if not self.player:
			raise Http404
		victim = get_player_or_404(
			game = self.game,
			id = self.kwargs['player_id'],
			eliminated=False,
			surrendered=False,
			may_excommunicate=False
		)
		if self.game.phase == 0 \
			or not self.game.configuration.excommunication \
			or not self.player \
			or not self.player.may_excommunicate:
			messages.error(
				self.request,
				_("You cannot excommunicate in this game.")
			)
			return redirect(self.game)
		if self.action == 'punish':
			if not self.player.can_excommunicate():
				messages.error(
					self.request,
					_("You cannot excommunicate in the current season.")
				)
				return redirect(self.game)
			if victim.is_excommunicated:
				messages.error(
					self.request,
					_("This country is already excommunicated.")
				)
				return redirect(self.game)
			victim.set_excommunication(by_pope=True)
			self.player.has_sentenced = True
			self.player.save()
			messages.success(
				self.request,
				_("The country has been excommunicated.")
			)
		elif self.action == 'forgive':
			if not self.player.can_forgive():
				messages.error(
					self.request,
				_("You cannot forgive excommunications in the current season.")
				)
				return redirect(self.game)
			if not victim.is_excommunicated:
				messages.error(
					self.request,
					_("You cannot forgive this country.")
				)
				return redirect(self.game)
			victim.unset_excommunication()
			self.player.has_sentenced = True
			self.player.save()
			messages.success(self.request, _("The country has been forgiven."))
		return redirect(self.game)

class ExpenseCreateView(GamePlayView, FormMixin):
	template_name = 'machiavelli/expenses_actions.html'

	def get_form_class(self):
		return forms.make_expense_form(self.player)

	def get_form(self, form_class):
		return form_class(self.player, **self.get_form_kwargs())

	def form_valid(self, form):
		if self.player:
			expense = form.save()
			self.player.ducats = F('ducats') - expense.ducats
			self.player.save()
			messages.success(self.request, _("Expense successfully saved."))
		return HttpResponseRedirect(self.request.path)

	def get_context_data(self, **kwargs):
		if not self.player:
			raise Http404
		ctx = super(ExpenseCreateView, self).get_context_data(**kwargs)
		ctx.update({'current_expenses': self.player.expense_set.all()})
		return ctx

class ExpenseDeleteView(GamePlayView):
	def get(self, request, *args, **kwargs):
		if self.player:
			expense = get_object_or_404(
				machiavelli.Expense,
				id=self.kwargs['expense_id'],
				player=self.player
			)
			try:
				expense.undo()
			except:
				messages.error(self.request, _("Expense could not be undone."))
			else:
				messages.success(
					self.request,
					_("Expense successfully undone.")
				)
		url = reverse('expenses', kwargs={'slug': self.kwargs['slug']})
		return HttpResponseRedirect(url)

class GiveMoneyView(GamePlayView, FormMixin):
	template_name = 'machiavelli/give_money.html'
	form_class = forms.LendForm

	def get_borrower(self, player_id):
		return get_player_or_404(id=player_id, game=self.game)

	def get_context_data(self, **kwargs):
		if not self.player:
			raise Http404
		ctx = super(GiveMoneyView, self).get_context_data(**kwargs)
		ctx.update({'borrower': self.get_borrower(self.kwargs['player_id']),})
		return ctx

	def form_valid(self, form):
		if self.player:
			borrower = self.get_borrower(self.kwargs['player_id'])
			ducats = form.cleaned_data['ducats']
			if ducats > self.player.ducats:
				messages.error(
					self.request,
					_("You cannot give more money than you have")
				)
				return HttpResponseRedirect(self.request.path)
			self.player.ducats = F('ducats') - ducats
			borrower.ducats = F('ducats') + ducats
			self.player.save()
			borrower.save()
			messages.success(
				self.request,
				_("The money has been successfully sent.")
			)
			if notification:
				extra_context = {
					'game': self.game,
					'ducats': ducats,
					'country': self.player.contender.country,
					'STATIC_URL': settings.STATIC_URL
				}
				if self.game.fast:
					notification.send_now(
						[borrower.user,],
						"received_ducats", 
						extra_context
					)
				else:
					notification.send(
						[borrower.user,],
						"received_ducats",
						extra_context
				)
		return redirect(self.game)

class PlayReinforcements(GamePlayView):
	template_name = 'machiavelli/reinforcements_actions.html'

	def get_units_to_place(self):
		return self.player.units_to_place()

	def get_reinforce_formset_class(self):
		ReinforceForm = forms.make_reinforce_form(self.player)
		return formset_factory(
			ReinforceForm,
			formset=forms.BaseReinforceFormSet,
			extra=self.get_units_to_place()
		)

	def get_disband_form_class(self):
		return forms.make_disband_form(self.player)

	def get(self, request, *args, **kwargs):
		if self.player:
			units_to_place = self.get_units_to_place()
			if units_to_place > 0:
				reinforce_formset_class = self.get_reinforce_formset_class()
				reinforce_form = reinforce_formset_class()
				return self.render_to_response(
					self.get_context_data(reinforce_form=reinforce_form)
				)
			elif units_to_place < 0:
				form_class = self.get_disband_form_class()
				disband_form = form_class()
				return self.render_to_response(
					self.get_context_data(disband_form=disband_form)
				)
		return self.render_to_response(self.get_context_data())

	def post(self, request, *args, **kwargs):
		if not self.player or self.player.done:
			raise Http404
		units_to_place = self.get_units_to_place()
		if units_to_place > 0:
			reinforce_formset_class = self.get_reinforce_formset_class()
			reinforce_form = reinforce_formset_class(request.POST)
			if reinforce_form.is_valid():
				for f in reinforce_form.forms:
					new_unit = machiavelli.Unit(
						type=f.cleaned_data['type'],
						area=f.cleaned_data['area'],
						player=self.player,
						placed=False
					)
					new_unit.save()
				self.player.end_phase()
				messages.success(request, _("You have successfully made your reinforcements."))
				return HttpResponseRedirect(request.path)
			else:
				messages.error(request, _("There was an error in your reinforcements."))
				return redirect(self.game)
		elif units_to_place < 0:
			form_class = self.get_disband_form_class()
			disband_form = form_class(request.POST)
			if disband_form.is_valid():
				if len(disband_form.cleaned_data['units']) == -units_to_place:
					for u in disband_form.cleaned_data['units']:
						u.paid = False
						u.save()
					self.player.end_phase()
					messages.success(
						request,
						_("You have successfully made your reinforcements.")
					)
					return HttpResponseRedirect(request.path)
				else:
					messages.error(
						request,
						_("You must disband exactly %s units.") % -units_to_place
					)
					return redirect(self.game)
			else:
				messages.error(request, _("There was an error in your reinforcements."))
				return redirect(self.game)
		else:
			raise Http404

	def get_context_data(self, **kwargs):
		ctx = super(PlayReinforcements, self).get_context_data(**kwargs)
		if not self.player:
			return ctx
		units_to_place = self.get_units_to_place()
		if self.player.done:
			ctx.update({
				'to_place': self.player.unit_set.filter(placed=False),
				'to_disband': self.player.unit_set.filter(placed=True, paid=False),
				'to_keep': self.player.unit_set.filter(placed=True, paid=True),
			})
			if units_to_place == 0:
				ctx.update({'undoable': False})
		else:
			ctx.update({
				'cities_qty': self.player.number_of_cities,
				'cur_units': self.player.unit_set.all().count(),
			})
			if units_to_place > 0:
				## place units
				ctx.update({'units_to_place': units_to_place})
			elif units_to_place < 0:
				## remove units
				ctx.update({'units_to_disband': -units_to_place})
		return ctx

class PlayFinanceReinforcements(GamePlayView):
	def get_template_names(self):
		if not self.player:
			return ['machiavelli/inactive_actions.html',]
		if self.player.done:
			return ['machiavelli/reinforcements_actions.html',]
		else:
			return ['machiavelli/finance_reinforcements_%s.html' % self.player.step,]

	def get_max_units(self):
		can_buy = self.player.ducats / 3
		can_place = self.player.get_areas_for_new_units(finances=True).count()
		return min(can_buy, can_place)

	def get_unit_payment_form_class(self):
		return forms.make_unit_payment_form(self.player)

	def get_reinforce_formset_class(self):
		max_units = self.get_max_units()
		if max_units > 0:
			ReinforceForm = forms.make_reinforce_form(
				self.player,
				finances=True,
				special_units=self.game.configuration.special_units
			)
			return formset_factory(
				ReinforceForm,
				formset=forms.BaseReinforceFormSet,
				extra=max_units
			)
		else:
			return None

	def get(self, request, *args, **kwargs):
		if self.player:
			if self.player.step == 0:
				form_class = self.get_unit_payment_form_class()
				form = form_class()
				return self.render_to_response(self.get_context_data(form=form))
			elif self.player.step == 1:
				formset_class = self.get_reinforce_formset_class()
				if formset_class:
					formset = formset_class()
					return self.render_to_response(self.get_context_data(formset=formset))
		return self.render_to_response(self.get_context_data())

	def post(self, request, *args, **kwargs):
		if not self.player or self.player.done:
			raise Http404
		if self.player.step == 0:
			form_class = self.get_unit_payment_form_class()
			form = form_class(request.POST)
			if form.is_valid():
				cost = 0
				for u in form.cleaned_data['units']:
					cost += u.cost
				if cost <= self.player.ducats:
					for u in form.cleaned_data['units']:
						u.paid = True
						u.save()
					self.player.ducats = self.player.ducats - cost
					self.player.step = 1
					self.player.save()
					messages.success(request, _("You have successfully paid your units."))
					return HttpResponseRedirect(request.path)
				else:
					messages.error(
						request,
						_("You don't have enough money to pay so many units.")
					)
			else:
				return self.render_to_response(self.get_context_data(form=form))
		elif self.player.step == 1:
			formset_class = self.get_reinforce_formset_class()
			if formset_class:
				formset = formset_class(request.POST)
				if formset.is_valid():
					total_cost = 0
					new_units = []
					for f in formset.forms:
						if 'area' in f.cleaned_data:
							new_unit = machiavelli.Unit(
								type=f.cleaned_data['type'],
								area=f.cleaned_data['area'],
								player=self.player,
								placed=False
							)
							if 'unit_class' in f.cleaned_data:
								if not f.cleaned_data['unit_class'] is None:
									unit_class = f.cleaned_data['unit_class']
									## it's a special unit
									new_unit.cost = unit_class.cost
									new_unit.power = unit_class.power
									new_unit.loyalty = unit_class.loyalty
							new_units.append(new_unit)
							total_cost += new_unit.cost
					if total_cost > self.player.ducats:
						messages.error(
							request,
							_("You don't have enough ducats to buy these units.")
						)
					else:
						for u in new_units:
							u.save()
						self.player.ducats = self.player.ducats - total_cost
						self.player.save()
						messages.success(
							request,
							_("You have successfully made your reinforcements.")
						)
						self.player.end_phase()
					return HttpResponseRedirect(request.path)
				else:
					return self.render_to_response(self.get_context_data(formset=formset))
			else:
				self.player.end_phase()
		return redirect(self.game)

	def get_context_data(self, **kwargs):
		ctx = super(PlayFinanceReinforcements, self).get_context_data(**kwargs)
		if not self.player:
			return ctx
		if self.player.done:
			ctx.update({
				'to_place': self.player.unit_set.filter(placed=False),
				'to_disband': self.player.unit_set.filter(placed=True, paid=False),
				'to_keep': self.player.unit_set.filter(placed=True, paid=True),
			})
		else:
			if self.game.configuration.lenders:
				ctx.update({
					'credits': self.player.credit_set.filter(repaid=False) \
						.order_by('year', 'season'),
				})
			if self.game.configuration.special_units:
				ctx.update({'special_units': True})
			if self.player.step == 1:
				ctx.update({'max_units': self.get_max_units(),})
		return ctx

class PlayOrders(GamePlayView):
	template_name = 'machiavelli/orders_actions.html'
	
	def get_form_class(self):
		return forms.make_order_form(self.player)

	def get_context_data(self, **kwargs):
		ctx = super(PlayOrders, self).get_context_data(**kwargs)
		if not self.player:
			return ctx
		ctx.update({'sent_orders': self.player.order_set.all()})
		if self.game.configuration.finances:
			ctx.update({'current_expenses': self.player.expense_set.all()})
		if self.game.configuration.assassinations:
			ctx.update({'assassinations': self.player.assassination_attempts.all()})
		if self.game.configuration.lenders:
			ctx.update({
				'credits': self.player.credit_set.filter(repaid=False). \
					order_by('year', 'season'),
				'credit_limit': self.player.get_credit(),
			})
		return ctx

	def get(self, request, *args, **kwargs):
		if self.player:
			if not self.player.done:
				form_class = self.get_form_class()
				order_form = form_class(self.player)
				return self.render_to_response(self.get_context_data(order_form=order_form))
		return self.render_to_response(self.get_context_data())

	def post(self, request, *args, **kwargs):
		if not self.player or self.player.done:
			raise Http404
		if not self.player.done:
			form_class = self.get_form_class()
			order_form = form_class(self.player, data=request.POST)
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
					new_order = order_form.save()
					response_dict.update({
						'pk': new_order.pk ,
						'new_order': new_order.explain()
					})
				response_json = simplejson.dumps(response_dict, ensure_ascii=False)
				return HttpResponse(response_json, mimetype='application/javascript')
			## not ajax
			else:
				if order_form.is_valid():
					new_order = order_form.save()
				return HttpResponseRedirect(request.path)
		raise Http404

class PlayStrategic(GamePlayView, FormMixin):
	template_name = 'machiavelli/strategic_actions.html'
	
	def get_formset_class(self):
		StrategicOrderForm = forms.strategic_order_form_factory(self.player)
		return formset_factory(
			StrategicOrderForm,
			formset=forms.BaseStrategicOrderFormSet,
			extra=2
		)

	def get(self, request, *args, **kwargs):
		if self.player and not self.player.done:
			formset_class = self.get_formset_class()
			formset = formset_class()
			return self.render_to_response(self.get_context_data(formset=formset))
		return self.render_to_response(self.get_context_data())
	
	def post(self, request, *args, **kwargs):
		if not self.player or self.player.done:
			raise Http404
		formset_class = self.get_formset_class()
		formset = formset_class(request.POST)
		if formset.is_valid():
			for form in formset.forms:
				if 'unit' in form.cleaned_data:
					form.save()
			self.player.end_phase()
			messages.success(request, _("You have successfully sent your strategic movements."))
			return HttpResponseRedirect(request.path)
		return self.render_to_response(self.get_context_data(formset=formset))
	
	def get_context_data(self, **kwargs):
		ctx = super(PlayStrategic, self).get_context_data(**kwargs)
		if not self.player:
			return ctx
		ctx.update({
			'orders': machiavelli.StrategicOrder.objects.filter(unit__player=self.player),
		})
		if self.player.strategic_units().count() <= 0:
			ctx.update({'undoable': False})
		return ctx

class PlayRetreats(GamePlayView, FormMixin):
	template_name = 'machiavelli/retreats_actions.html'

	def get_units(self):
		return self.player.unit_set.exclude(must_retreat__exact='')

	def get_context_data(self, **kwargs):
		ctx = super(PlayRetreats, self).get_context_data(**kwargs)
		if not self.player:
			return ctx
		return ctx
		
	def get(self, request, *args, **kwargs):
		if self.player and not self.player.done:
			retreat_forms = []
			units = self.get_units()
			for u in units:
				RetreatForm = forms.make_retreat_form(u)
				retreat_forms.append(RetreatForm(prefix=u.id))
			if len(retreat_forms) > 0:
				return self.render_to_response(
					self.get_context_data(retreat_forms=retreat_forms)
				)
		return self.render_to_response(self.get_context_data())

	def post(self, request, *args, **kwargs):
		if not self.player or self.player.done:
			raise Http404
		retreat_forms = []
		units = self.get_units()
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
		self.player.end_phase()
		messages.success(request, _("You have successfully retreated your units."))
		return HttpResponseRedirect(request.path)

class PlayInactiveGame(GamePlayView, FormMixin):
	template_name = 'machiavelli/game_inactive.html'
	form_class = forms.GameCommentForm
	
	def render_to_response(self, context, **kwargs):
		return super(PlayInactiveGame, self).render_to_response(
			RequestContext(
				self.request,
				context,
				processors=[activity, sidebar_ranking,]
			),
			**kwargs
		)

	def get_game(self, request, *args, **kwargs):
		if not self.game:
			self.game = get_game_or_404(slug=kwargs['slug'])
		return self.game

	def get_context_data(self, **kwargs):
		ctx = {'game': self.game}
		started = self.game.started is not None
		finished = self.game.finished is not None
		if self.request.user.is_authenticated():
			joinable = self.game in machiavelli.Game.objects.joinable(
				self.request.user
			)
		else:
			joinable = self.game in machiavelli.Game.objects.joinable()
		## if the game is finished, get the scores
		if finished:
			cache_key = "game-scores-%s" % self.game.id
			scores = cache.get(cache_key)
			if not scores:
				scores = self.game.score_set.filter(user__isnull=False).order_by('-points')
				cache.set(cache_key, scores)
			ctx.update({'players': scores,})
			## get the logs, if they still exist
			log = self.game.baseevent_set.all()
			if log.count() > 0:
				ctx.update({'show_log': True})
			## show the overthrows history
			overthrows = self.game.revolution_set.filter(overthrow=True)
			if overthrows.count() > 0:
				ctx.update({'overthrows': overthrows})
		## comments section
		ctx.update({
			'started': started,
			'finished': finished,
			'joinable': joinable,
			'comments': self.game.gamecomment_set.public()
		})
		ctx.update(**kwargs)
		return ctx
	
	def post(self, request, *args, **kwargs):
		form_class = self.get_form_class()
		form = form_class(request.POST)
		if form.is_valid():
			form.save(user=request.user, game=self.game)
			return redirect(self.game)
		else:
			return self.form_invalid(form)

class GameRouter(View):
	"""Return a View that depends on the current status of the game."""
	## staticmethod avoids adding 'self' to the arguments
	inactive_view = staticmethod(PlayInactiveGame.as_view())
	reinforcements_view = staticmethod(PlayReinforcements.as_view())
	finance_reinforcements_view = staticmethod(PlayFinanceReinforcements.as_view())
	orders_view = staticmethod(PlayOrders.as_view())
	strategic_view = staticmethod(PlayStrategic.as_view())
	retreats_view = staticmethod(PlayRetreats.as_view())

	def dispatch(self, request, *args, **kwargs):
		game = get_game_or_404(slug=kwargs['slug'])
		#try:
		#	player = game.player_set.get(user=request.user)
		#except ObjectDoesNotExist:
		#	player = machiavelli.Player.objects.none()
		if game.started is None \
			or game.finished is not None \
			or game.phase == machiavelli.PHINACTIVE \
			or (game.paused and not request.user.is_staff):
			return self.inactive_view(request, *args, **kwargs)
		if game.phase == machiavelli.PHREINFORCE:
			if game.configuration.finances:
				return self.finance_reinforcements_view(request, *args, **kwargs)
			else:
				return self.reinforcements_view(request, *args, **kwargs)
		if game.phase == machiavelli.PHORDERS:
			return self.orders_view(request, *args, **kwargs)
		if game.phase == machiavelli.PHSTRATEGIC:
			return self.strategic_view(request, *args, **kwargs)
		if game.phase == machiavelli.PHRETREATS:
			return self.retreats_view(request, *args, **kwargs)

class ReturnMoneyView(GamePlayView):
	template_name = 'machiavelli/return_money.html'

	def get_credit_or_404(self):
		return get_object_or_404(
			machiavelli.Credit,
			id=self.kwargs['credit_id'],
			player=self.player,
			repaid=False
		)

	def get_context_data(self, **kwargs):
		if not self.player:
			raise Http404
		ctx = super(ReturnMoneyView, self).get_context_data(**kwargs)
		ctx.update({'credit': self.get_credit_or_404()})
		return ctx

	def post(self, request, *args, **kwargs):
		if not self.player:
			raise Http404
		credit = self.get_credit_or_404()
		if self.player.ducats >= credit.debt:
			self.player.ducats = F('ducats') - credit.debt
			self.player.save()
			credit.repaid=True
			credit.save()
			messages.success(self.request, _("You have repaid the loan."))
		else:
			messages.error(
				self.request,
				_("You don't have enough money to repay the loan.")
			)
		return redirect(self.game)

class SurrenderView(GamePlayView):
	template_name = 'machiavelli/surrender.html'

	def post(self, request, *args, **kwargs):
		if self.player:
			self.player.surrender()
			messages.success(
				self.request,
				_("You have surrendered in this game.")
			)
			return redirect(self.game)

class UndoActionsView(GamePlayView):
	def post(self, request, *args, **kwargs):
		if not self.player:
			raise Http404
		if not self.player.done or self.player.in_last_seconds():
			messages.error(request, _("You cannot undo actions in this moment."))
		else:
			self.player.done = False
			if self.game.phase == machiavelli.PHREINFORCE:
				if self.game.configuration.finances:
					## first, delete new, not placed units
					units = self.player.unit_set.filter(placed=False)
					if units.count() > 0:
						costs = units.aggregate(Sum('cost'))
						ducats = costs['cost__sum']
					else:
						ducats = 0
					units.delete()
					## then mark all units as not paid, refund the money
					units = self.player.unit_set.filter(paid=True)
					if units.count() > 0:
						costs = units.aggregate(Sum('cost'))
						ducats += costs['cost__sum']
						units.update(paid=False)
					self.player.ducats += ducats
				else:
					## first, delete new, not placed units
					self.player.unit_set.filter(placed=False).delete()
					## then, mark all units as paid
					self.player.unit_set.update(paid=True)
			elif self.game.phase == machiavelli.PHORDERS:
				self.player.order_set.update(confirmed=False)
				self.player.expense_set.update(confirmed=False)
				messages.success(
					request,
					_("Your actions are now unconfirmed. You'll have to confirm then again.")
				)
			elif self.game.phase == machiavelli.PHRETREATS:
				machiavelli.RetreatOrder.objects.filter(unit__player=self.player).delete()
				messages.success(request, _("Your retreat orders have been undone."))
			elif self.game.phase == machiavelli.PHSTRATEGIC:
				machiavelli.StrategicOrder.objects.filter(unit__player=self.player).delete()
				messages.success(request, _("Your strategic movements have been undone."))
			if self.game.check_bonus_time():
				self.request.user.get_profile().adjust_karma( -1 )
			self.player.save()
		return redirect(self.game)

class WhisperCreateView(GamePlayView, FormMixin):
	form_class = forms.WhisperForm

	def form_valid(self, form):
		if self.player:
			form.save(self.request.user, self.game)
		return redirect(self.game)
	
	def form_invalid(self, form):
		messages.error(
			self.request,
			_("Maximum whisper length is 140 characters.")
		)
		return redirect(self.game)

def get_log_qs(game, player):
	if player and game.configuration.fow:
		cache_key = "player-%s_log" % player.id
	else:
		cache_key = "game-%s_log" % game.id
	log = cache.get(cache_key)
	if not log:
		##TODO: move this to a condottieri_events manager
		log = game.baseevent_set.exclude(season__exact=game.season, phase__exact=game.phase,
			year__exact=game.year)
		if game.configuration.fow:
			## show all control events and all country events
			q = Q(controlevent__area__isnull=False) | \
			Q(countryevent__country__isnull=False) | \
			Q(uncoverevent__country__isnull=False) | \
			Q(disasterevent__area__isnull=False)
			if player:
				visible = player.visible_areas()
				## add events visible by the player
				q = q | \
					Q(orderevent__origin__in=visible) | \
					Q(conversionevent__area__in=visible) | \
					Q(disbandevent__area__in=visible) | \
					Q(expenseevent__area__in=visible) | \
					Q(movementevent__destination__in=visible) | \
					Q(newunitevent__area__in=visible) | \
					Q(retreatevent__destination__in=visible) | \
					Q(standoffevent__area__in=visible) | \
					Q(unitevent__area__in=visible)
			log = log.filter(q)
		cache.set(cache_key, log)
	return log

def get_game_context(request, game, player):
	"""This function returns a common context for all the game views"""
	context = {
		'user': request.user,
		'game': game,
		'player': player,
		'player_list': game.player_set.by_cities(),
		'teams': game.team_set.all(),
		'map': game.get_map_url(player),
	}
	if player:
		if game.configuration.lenders:
			credits = machiavelli.Credit.objects.filter(player=player, repaid=False). \
				order_by('year', 'season')
			credit_limit = player.get_credit()
			context.update({
				'credits': credits,
				'credit_limit': credit_limit
			})
		try:
			journal = machiavelli.Journal.objects.get(
				user=request.user,
				game=game
			)
		except ObjectDoesNotExist:
			journal = machiavelli.Journal()
		context.update({
			'done': player.done,
			'surrendered': player.surrendered,
			'can_excommunicate': player.can_excommunicate(),
			'can_forgive': player.can_forgive(),
			'excerpt': journal.excerpt,
			'time_exceeded': player.time_exceeded(),
		})
	log = get_log_qs(game, player)
	if len(log) > 0:
		last_year = log[0].year
		last_season = log[0].season
		last_phase = log[0].phase
		context.update({
			'log': log.filter(
				year=last_year,
				season=last_season,
				phase=last_phase)
		})
	else:
		context.update({'log': log})
	rules = game.configuration.get_enabled_rules()
	if len(rules) > 0:
		context.update({'rules': rules})
	if game.configuration.gossip:
		whispers = game.whisper_set.all()[:10]
		context.update({'whispers': whispers})
		if player:
			context.update({'whisper_form': forms.WhisperForm(),})
	if game.scenario.setting.configuration.religious_war:
		context.update({'show_religions': True})
	return context

class GameAreaListView(ListView):
	context_object_name = 'area_list'
	template_name = 'machiavelli/gamearea_list'

	def get_queryset(self):
		return machiavelli.GameArea.objects.filter(
			game__slug=self.kwargs['slug']
		)
	
	def get_context_data(self, **kwargs):
		context = super(GameAreaListView, self).get_context_data(**kwargs)
		game = get_game_or_404(slug=self.kwargs['slug'])
		player = machiavelli.Player.objects.none()
		if self.request.user.is_authenticated():
			try:
				player = game.player_set.get(user=self.request.user)
			except ObjectDoesNotExist:
				pass
		context.update(get_game_context(self.request, game, player))
		return context

class TeamMessageListView(LoginRequiredMixin, ListAppendView):
	model = machiavelli.TeamMessage
	paginate_by = 10
	context_object_name = 'message_list'
	template_name = 'machiavelli/team_messages.html'
	form_class = forms.TeamMessageForm

	def get_success_url(self):
		return reverse('team_messages', kwargs={'slug': self.kwargs['slug']})

	def get_queryset(self):
		self.game = get_game_or_404(slug=self.kwargs['slug'])
		if not self.game.is_team_game:
			raise Http404
		player = get_player_or_404(user=self.request.user, game=self.game)
		return machiavelli.TeamMessage.objects.filter(player__team=player.team)

	def get_context_data(self, **kwargs):
		context = super(TeamMessageListView, self).get_context_data(**kwargs)
		game = self.game
		try:
			player = machiavelli.Player.objects.get(game=game, user=self.request.user)
		except ObjectDoesNotExist:
			player = machiavelli.Player.objects.none()
		context.update(get_game_context(self.request, game, player))
		return context

	def form_valid(self, form):
		game = get_game_or_404(slug=self.kwargs['slug'])
		player = get_player_or_404(user=self.request.user, game=game)
		self.object = form.save(player)
		return redirect(self.get_success_url())
		#return super(TeamMessageListView, self).form_valid(form)

#@never_cache
#@login_required
def logs_by_game(request, slug=''):
	game = get_game_or_404(slug=slug)
	try:
		player = machiavelli.Player.objects.get(game=game, user=request.user)
	except:
		player = machiavelli.Player.objects.none()
	context = get_game_context(request, game, player)
	#log_list = game.baseevent_set.exclude(year__exact=game.year,
	#									season__exact=game.season,
	#									phase__exact=game.phase)
	log_list = get_log_qs(game, player)
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

	context['season_log'] = log

	return render_to_response('machiavelli/log_list.html',
							context,
							context_instance=RequestContext(request))

class CreateGameView(LoginRequiredMixin, TemplateView):
	template_name = 'machiavelli/game_form.html'

	def render_to_response(self, context, **kwargs):
		return super(CreateGameView, self).render_to_response(
			RequestContext(
				self.request,
				context,
				processors=[activity, sidebar_ranking,]
			),
			**kwargs
		)

	def get_context_data(self, **kwargs):
		ctx = super(CreateGameView, self).get_context_data(**kwargs)
		ctx.update({
			'scenarios': scenarios.Scenario.objects.filter(enabled=True),
		})
		ctx.update(kwargs)
		return ctx

	def get_form_class(self):
		return forms.GameForm

	def get(self, request, *args, **kwargs):
		form_class = self.get_form_class()
		game_form = form_class(request.user)
		config_form = forms.ConfigurationForm()
		return self.render_to_response(
			self.get_context_data(
				game_form=game_form,
				config_form=config_form
			)
		)

	def post(self, request, *args, **kwargs):
		form_class = self.get_form_class()
		game_form = form_class(request.user, data=request.POST)
		config_form = forms.ConfigurationForm(request.POST)
		if game_form.is_valid():
			new_game = game_form.save()
			new_player = machiavelli.Player()
			new_player.user = request.user
			new_player.game = new_game
			new_player.save()
			config_form = forms.ConfigurationForm(
				request.POST,
				instance=new_game.configuration
			)
			config = config_form.save(commit=False)
			if new_game.require_home_cities:
				config.variable_home = False
			config.save()
			cache.delete('sidebar_activity')
			player_joined.send(sender=new_player)
			messages.success(request, _("Game successfully created."))
			if new_game.private:
				return redirect('invite-users', slug=new_game.slug)
			else:
				return redirect(new_game)
		return self.render_to_response(
			self.get_context_data(
				game_form=game_form,
				config_form=config_form
			)
		)

class CreateTeamGameView(CreateGameView):
	def get_form_class(self):
		return forms.TeamGameForm

	def get_context_data(self, **kwargs):
		ctx = super(CreateTeamGameView, self).get_context_data(**kwargs)
		ctx.update({'teams': True})
		return ctx

class GameInvitationView(FormView):
	template_name = 'machiavelli/invitation_form.html'
	form_class = forms.InvitationForm

	def dispatch(self, request, *args, **kwargs):
		if not request.user.is_authenticated():
			raise Http404
		self.game = get_game_or_404(
			slug=kwargs['slug'],
			slots__gt=0,
			created_by=request.user
		)
		return super(GameInvitationView, self).dispatch(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		ctx = super(GameInvitationView, self).get_context_data(**kwargs)
		ctx.update({
			'game': self.game,
			'players': self.game.player_set.human(),
			'invitations': self.game.invitation_set.all(),
		})
		return ctx

	def render_to_response(self, context, **kwargs):
		return super(GameInvitationView, self).render_to_response(
			RequestContext(
				self.request,
				context,
				processors=[activity, sidebar_ranking,]
			),
			**kwargs
		)

	def form_valid(self, form):
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
					self.game.player_set.get(user=user)
				except ObjectDoesNotExist:
					## check for existing invitation
					try:
						self.game.invitation_set.get(user=user)
					except ObjectDoesNotExist:
						i = machiavelli.Invitation()
						i.game = self.game
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
			messages.success(self.request, msg)
		if len(fail_list) > 0:
			msg = _("The following users could not be invited: %s") % ", ".join(fail_list)
			messages.error(self.request, msg)
			return redirect(self.game)

class JoinGameView(LoginRequiredMixin, View):
	def get(self, request, *args, **kwargs):
		game = get_game_or_404(slug=kwargs['slug'], slots__gt=0)
		try:
			game.player_set.get(user=request.user)
		except ObjectDoesNotExist:
			pass
		else:
			messages.error(request, _("You had already joined this game."))
			return redirect('summary')
		invitation = None
		## check if the user has defined his languages
		if not request.user.get_profile().has_languages():
			messages.error(
				request,
				_("You must define at least one known language before joining a game.")
			)
			messages.info(
				request,
				_("Define your languages and then, try again.")
			)
			return redirect("profile_languages_edit")
		if game.private:
			## check if user has been invited
			try:
				invitation = game.invitation_set.get(user=request.user)
			except ObjectDoesNotExist:
				messages.error(
					request,
					_("This game is private and you have not been invited.")
				)
				return redirect("games-joinable")
		msg = request.user.get_profile().check_karma_to_join(fast=game.fast)
		if msg != "": #user can't join
			messages.error(request, msg)
			return redirect("summary")
		new_player = machiavelli.Player(user=request.user, game=game)
		new_player.save()
		if invitation:
			invitation.delete()
		game.player_joined()
		player_joined.send(sender=new_player)
		messages.success(request, _("You have successfully joined the game."))
		cache.delete('sidebar_activity')
		return redirect(game)

class LeaveGameView(LoginRequiredMixin, View):
	def get(self, request, *args, **kwargs):
		game = get_game_or_404(slug=kwargs['slug'], slots__gt=0)
		try:
			player = game.player_set.get(user=request.user)
		except ObjectDoesNotExist:
			## the user is not in the game
			messages.error(request, _("You had not joined this game."))
		else:
			player.delete()
			game.slots += 1
			game.save()
			cache.delete('sidebar_activity')
			messages.success(request, _("You have left the game."))
			## if the game has no players, delete the game
			if game.player_set.count() == 0:
				game.delete()
				messages.info(request, _("The game has been deleted."))
		return redirect('summary')

class MakeGamePublic(LoginRequiredMixin, View):
	def get(self, request, *args, **kwargs):
		game = get_game_or_404(
			slug=kwargs['slug'],
			slots__gt=0,
			private=True,
			created_by=request.user
		)
		game.private = False
		game.save()
		game.invitation_set.all().delete()
		messages.success(request, _("The game is now open to all users."))
		return redirect(game)

class OverthrowView(LoginRequiredMixin, View):
	def get(self, request, *args, **kwargs):
		revolution = get_object_or_404(machiavelli.Revolution, pk=kwargs['revolution_id'])
		game = revolution.game
		try:
			## check that overthrowing user is not a player
			game.player_set.get(user=request.user)
		except ObjectDoesNotExist:
			try:
				## check that there is not another revolution with the same player
				game.revolution_set.get(opposition=request.user)
			except ObjectDoesNotExist:
				karma = request.user.get_profile().karma
				if karma < settings.KARMA_TO_JOIN:
					err = _("You need a minimum karma of %s to join a game.") % \
						settings.KARMA_TO_JOIN
					messages.error(request, err)
					return redirect("revolution_list")
				if not revolution.active:
					err = _("This revolution is inactive.")
					messages.error(request, err)
					return redirect("revolution_list")
				revolution.opposition = request.user
				revolution.save()
				if revolution.voluntary:
					revolution.resolve()
					messages.success(request, _("You are now playing this game."))
					return redirect(revolution.game)
				else:
					overthrow_attempted.send(sender=revolution)
					messages.success(request, _("Your overthrow attempt has been saved."))
			else:
				messages.error(
					request,
					_("You are already attempting an overthrow on another player in the same game.")
				)
		else:
			messages.error(request, _("You are already playing this game."))
		return redirect("revolution_list")

class UndoOverthrowView(LoginRequiredMixin, View):
	def get(self, request, *args, **kwargs):
		revolution = get_object_or_404(
			machiavelli.Revolution,
			pk=kwargs['revolution_id'],
			opposition=request.user,
			overthrow=False
		)
		revolution.opposition = None
		revolution.save()
		messages.success(request, _("You have withdrawn from this revolution."))
		return redirect("revolution_list")

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
		self.game = get_game_or_404(slug=self.kwargs['slug'])
		if self.game.configuration.fow:
			return machiavelli.TurnLog.objects.none()
		return self.game.turnlog_set.all()

	def get_context_data(self, **kwargs):
		context = super(TurnLogListView, self).get_context_data(**kwargs)
		try:
			player = machiavelli.Player.objects.get(
				user=self.request.user,
				game=self.game
			)
		except ObjectDoesNotExist:
			player = machiavelli.Player.objects.none()
		base_ctx = get_game_context(self.request, self.game, player)
		context.update(base_ctx)
		return context

@login_required
def taxation(request, slug):
	game = get_game_or_404(slug=slug)
	player = get_player_or_404(user=request.user, game=game, surrendered=False)
	if game.phase != machiavelli.PHORDERS or not game.configuration.taxation or player.done:
		messages.error(request, _("You cannot impose taxes in this moment."))
		return redirect(game)
	context = get_game_context(request, game, player)
	TaxationForm = forms.make_taxation_form(player)
	if request.method == 'POST':
		form = TaxationForm(request.POST)
		if form.is_valid():
			ducats = 0
			areas = form.cleaned_data["areas"]
			for a in areas:
				ducats += a.tax()
			player.ducats += ducats
			player.save()
			messages.success(request, _("Taxation has produced %s ducats for your treasury") % ducats)
			return redirect(game)
	form = TaxationForm()
	context["form"] = form
	return render_to_response('machiavelli/taxation.html',
							context,
							context_instance=RequestContext(request))

class WhisperListView(LoginRequiredMixin, ListAppendView):
	model = machiavelli.Whisper
	paginate_by = 20
	context_object_name = 'whisper_list'
	template_name_suffix = '_list'
	form_class = forms.WhisperForm

	def get_success_url(self):
		return reverse('whisper-list', kwargs={'slug': self.kwargs['slug']})

	def get_queryset(self):
		self.game = get_game_or_404(slug=self.kwargs['slug'])
		return self.game.whisper_set.all()

	def get_context_data(self, **kwargs):
		context = super(WhisperListView, self).get_context_data(**kwargs)
		try:
			player = machiavelli.Player.objects.get(user=self.request.user, game=self.game)
		except ObjectDoesNotExist:
			player = machiavelli.Player.objects.none()
		base_ctx = get_game_context(self.request, self.game, player)
		context.update(base_ctx)
		return context

	def form_valid(self, form):
		game = get_game_or_404(slug=self.kwargs['slug'])
		self.object = form.save(self.request.user, game)
		return HttpResponseRedirect(self.get_success_url())

