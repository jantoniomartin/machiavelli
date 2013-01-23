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

""" Class definitions for machiavelli django application

Defines the core classes of the machiavelli game.
"""

## stdlib
import random
import thread
from datetime import datetime, timedelta
import string
import os
import os.path

## django
from django.db import models
from django.db.models import permalink, Q, F, Count, Sum, Avg, Max
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.cache import cache
from django.core.mail import mail_admins
from django.contrib.auth.models import User
import django.forms as forms
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.template.defaultfilters import capfirst, timesince, force_escape

if "notification" in settings.INSTALLED_APPS:
	from notification import models as notification
else:
	notification = None

import logging
logger = logging.getLogger(__name__)

if "condottieri_messages" in settings.INSTALLED_APPS:
	import condottieri_messages as condottieri_messages 
else:
	condottieri_messages = None

## machiavelli
from machiavelli.graphics import make_map
import machiavelli.dice as dice
import machiavelli.disasters as disasters
import machiavelli.exceptions as exceptions
import slugify

## condottieri_scenarios
from condottieri_scenarios.models import Scenario, Contender, Country, Area, CountryRandomIncome, CityRandomIncome, FamineCell, PlagueCell, StormCell, TradeRoute

## condottieri_profiles
from condottieri_profiles.models import CondottieriProfile

## condottieri_events
import machiavelli.signals as signals

UNIT_TYPES = (('A', _('Army')),
              ('F', _('Fleet')),
              ('G', _('Garrison'))
			  )

SEASONS = ((1, _('Spring')),
           (2, _('Summer')),
           (3, _('Fall')),
           )

PHINACTIVE=0
PHREINFORCE=1
PHORDERS=2
PHRETREATS=3
PHSTRATEGIC=4

GAME_PHASES = ((PHINACTIVE, _('Inactive game')),
	  (PHREINFORCE, _('Military adjustments')),
	  (PHORDERS, _('Order writing')),
	  (PHRETREATS, _('Retreats')),
	  (PHSTRATEGIC, _('Strategic movement')),
	  )

ORDER_CODES = (('H', _('Hold')),
			   ('B', _('Besiege')),
			   ('-', _('Advance')),
			   ('=', _('Conversion')),
			   ('C', _('Convoy')),
			   ('S', _('Support'))
				)
ORDER_SUBCODES = (
				('H', _('Hold')),
				('-', _('Advance')),
				('=', _('Conversion'))
)

## time limit in seconds for a game phase
FAST_LIMITS = (15*60, )

TIME_LIMITS = (
			#(5*24*60*60, _('5 days')),
			#(4*24*60*60, _('4 days')),
			(3*24*60*60, _('3 days')),
			(2*24*60*60, _('2 days')),
			(24*60*60, _('1 day')),
			(12*60*60, _('1/2 day')),
			(15*60, _('15 min')),
)

## SCORES
## points assigned to the first, second and third players
SCORES=[30, 10, 5]

TEAM_GOAL=30

KARMA_MINIMUM = settings.KARMA_MINIMUM
KARMA_DEFAULT = settings.KARMA_DEFAULT
KARMA_MAXIMUM = settings.KARMA_MAXIMUM
BONUS_TIME = settings.BONUS_TIME

class Invasion(object):
	""" This class is used in conflicts resolution for conditioned invasions.
	Invasion objects are not persistent (i.e. not stored in the database).
	"""

	def __init__(self, unit, area, conv=''):
		assert isinstance(unit, Unit), u"%s is not a Unit" % unit
		assert isinstance(area, GameArea), u"%s is not a GameArea" % area
		assert conv in ['', 'A', 'F'], u"%s is not a valid conversion" % conv
		self.unit = unit
		self.area = area
		self.conversion = conv

class GameManager(models.Manager):
	def joinable_by_user(self, user):
		if user.is_authenticated():
			return self.filter(slots__gt=0).exclude(player__user=user)
		else:
			return self.filter(slots__gt=0)
	
	def pending_for_user(self, user):
		return self.filter(started__isnull=True, player__user=user)	

	def finished(self):
		return self.filter(finished__isnull=False).order_by('-finished')

def get_default_version():
	try:
		v = int(settings.RULES_VERSION)
	except:
		v = 0
	return v

class Game(models.Model):
	"""
	This is the main class of the machiavelli application. It includes all the
	logic to control the flow of the game, and to resolve conflicts.

	The attributes year, season and field are null when the game is first
	created and will be populated when the game is started, from the scenario
	data.
	"""

	title = models.CharField(max_length=128, unique=True,
		verbose_name=_("title"), help_text=_("max. 128 characters"))
	slug = models.SlugField(_("slug"), max_length=20, unique=True,
		help_text=_("4-20 characters, only letters, numbers, hyphens and underscores"))
	year = models.PositiveIntegerField(_("year"), blank=True, null=True)
	season = models.PositiveIntegerField(_("season"), blank=True, null=True,
		choices=SEASONS)
	phase = models.PositiveIntegerField(_("phase"), blank=True, null=True,
		choices=GAME_PHASES, default=0)
	slots = models.SmallIntegerField(_("slots"), null=False, default=0)
	scenario = models.ForeignKey(Scenario, verbose_name=_("scenario"))
	created_by = models.ForeignKey(User, editable=False,
		verbose_name=_("created by"))
	## whether the player of each country is visible
	visible = models.BooleanField(_("visible"), default=0,
		help_text=_("if checked, it will be known who controls each country"))
	map_outdated = models.BooleanField(_("map outdated"), default=0)
	time_limit = models.PositiveIntegerField(_("time limit"),
		choices=TIME_LIMITS,
		help_text=_("time available to play a turn"))
	## the time and date of the last phase change
	last_phase_change = models.DateTimeField(_("last phase change"),
		blank=True, null=True)
	created = models.DateTimeField(_("creation date"),blank=True, null=True,
		auto_now_add=True)
	started = models.DateTimeField(_("starting date"), blank=True, null=True)
	finished = models.DateTimeField(_("ending date"), blank=True, null=True)
	## if true, the game will start when it has all the players
	autostart = models.BooleanField(_("autostart"), default=True)
	cities_to_win = models.PositiveIntegerField(_("cities to win"), default=15,
		help_text=_("cities that must be controlled to win a game"))
	## if true, the player must keep all his home cities to win
	require_home_cities = models.BooleanField(_("require home cities"),
		default=False)
	## minimum number of conquered cities, apart from home country, to win
	extra_conquered_cities = models.PositiveIntegerField(default=0,
		verbose_name=_("extra conquered cities"))
	fast = models.BooleanField(_("fast"), default=0)
	uses_karma = models.BooleanField(_("uses karma"), default=True)
	paused = models.BooleanField(_("paused"), default=False)
	private = models.BooleanField(_("private"), default=0,
		help_text=_("only invited users can join the game"))
	comment = models.TextField(_("comment"), max_length=255, blank=True,
		null=True, help_text=_("optional comment for joining users"))
	## version of the rules that are used in this game
	## RULES_VERSION must be defined in settings module
	version = models.PositiveIntegerField(_("rules version"),
		default=get_default_version)
	extended_deadline = models.BooleanField(_("extended deadline"),
		default=False)
	""" if teams < 2, there will be no teams """
	teams = models.PositiveIntegerField(_("teams"), default=0)

	objects = GameManager()

	class Meta:
		verbose_name = _("game")
		verbose_name_plural = _("games")

	def save(self, *args, **kwargs):
		if not self.pk:
			if self.time_limit in FAST_LIMITS:
				self.fast = True
				self.uses_karma = False
			if self.teams > 1:
				self.uses_karma = False
			## short games
			## TODO: make this not hardcoded
			if self.cities_to_win == 12:
				self.require_home_cities = True
				self.extra_conquered_cities = 6
		if not self.slug:
			slugify.unique_slugify(self, self.title)
		super(Game, self).save(*args, **kwargs)

	def _get_expired(self):
		""" Returns True if the game is not started and a certain time has passed. """
		if self.started or self.finished:
			return False
		term = timedelta(0, settings.GAME_EXPIRATION)
		expiration = self.created + term
		if datetime.now() > expiration:
			return True
		return False

	expired = property(_get_expired)

	##------------------------
	## representation methods
	##------------------------
	def __unicode__(self):
		return self.title

	def get_absolute_url(self):
		return ('show-game', None, {'slug': self.slug})
	get_absolute_url = models.permalink(get_absolute_url)

	def _is_team_game(self):
		return self.teams > 1

	is_team_game = property(_is_team_game)

	def reset_players_cache(self):
		""" Deletes the player list from the cache """
		key = "game-%s_player-list" % self.pk
		cache.delete(key)
	
	def player_list_ordered_by_cities(self):
		##TODO: condottieri_scenarios should not appear in the SQL query. Fix it.
		key = "game-%s_player-list" % self.pk
		result_list = cache.get(key)
		if 1: #result_list is None:
			from django.db import connection
			cursor = connection.cursor()
			cursor.execute("SELECT machiavelli_player.*, COUNT(machiavelli_gamearea.id) \
			AS cities \
			FROM machiavelli_player \
			LEFT JOIN (machiavelli_gamearea \
			INNER JOIN condottieri_scenarios_area \
			ON machiavelli_gamearea.board_area_id=condottieri_scenarios_area.id \
			AND condottieri_scenarios_area.has_city=1) \
			ON machiavelli_gamearea.player_id=machiavelli_player.id \
			WHERE machiavelli_player.game_id=%s \
			GROUP BY machiavelli_player.id \
			ORDER BY machiavelli_player.team_id, cities DESC, machiavelli_player.id;" % self.id)
			result_list = []
			print result_list
			for row in cursor.fetchall():
				result_list.append(Player.objects.get(id=row[0]))
			cache.set(key, result_list)
		return result_list

	def _get_winners_qs(self):
		""" Returns a queryset of the highest score(s) in the game """
		if self.slots > 0 or self.phase != PHINACTIVE:
			return Score.objects.none()
		scores = self.score_set.all()
		max_dict = scores.aggregate(Max('points'))
		max_points = max_dict['points__max']
		return scores.filter(points=max_points)

	winners_qs = property(_get_winners_qs)
	
	def highest_score(self):
		""" Returns the Score with the highest points value. """

		if self.slots > 0 or self.phase != PHINACTIVE:
			return Score.objects.none()
		scores = self.score_set.all().order_by('-points')
		return scores[0]
	
	def get_average_score(self):
		""" Returns the average score of the current list of players """
		
		result = CondottieriProfile.objects.filter(user__player__game=self).aggregate(average_score=Avg('total_score'))
		return result['average_score']

	def get_average_karma(self):
		""" Returns the average karma of the current list of players """
		
		result = CondottieriProfile.objects.filter(user__player__game=self).aggregate(average_karma=Avg('karma'))
		return result['average_karma']

	def get_all_units(self):
		""" Returns a queryset with all the units in the board. """
		key = "game-%s_all-units" % self.pk
		all_units = cache.get(key)
		if all_units is None:
			all_units = Unit.objects.select_related().filter(player__game=self).order_by('area__board_area__code')
			cache.set(key, all_units)
		return all_units

	def get_all_gameareas(self):
		""" Returns a queryset with all the game areas in the board. """
		key = "game-%s_all-areas" % self.pk
		all_areas = cache.get(key)
		if all_areas is None:
			all_areas = self.gamearea_set.select_related().order_by('board_area__code')
			cache.set(key, all_areas)
		return all_areas

	##------------------------
	## map methods
	##------------------------
	
	def make_map(self, fow=False):
		make_map(self, fow)
		return True

	def map_changed(self):
		if self.map_outdated == False:
			self.map_outdated = True
			self.save()
	
	def map_saved(self):
		if self.map_outdated == True:
			self.map_outdated = False
			self.save()

	def get_map_name(self, player=None):
		if self.finished:
			return "%s_final.jpg" % self.id
		elif not self.configuration.fow:
			return "%s_%s_%s_%s.jpg" % (self.id, self.year, self.season,
				self.phase)
		else: #fow is enabled
			if isinstance(player, Player):
				return "%s_%s_%s_%s.jpg" % (player.secret_key, self.year,
					self.season, self.phase)
			else:
				return "" ## show scenario map

	def get_map_path(self, player=None):
		""" returns the absolute path of the map file """
		name = self.get_map_name(player)
		if name == "":
			return self.scenario.map_path
		else:
			return os.path.join(settings.MEDIA_ROOT, settings.MAPS_ROOT,
				self.slug, name)

	def get_map_url(self, player=None):
		""" returns the relative url of the map file """
		name = self.get_map_name(player)
		if name == "":
			return self.scenario.map_url
		else:
			return os.path.join(settings.MEDIA_URL, settings.MAPS_ROOT,
				self.slug, name)

	def _get_thumbnail_path(self):
		name = self.get_map_name()
		if name == "" or not self.started:
			return self.scenario.thumbnail_path
		else:
			return os.path.join(settings.MEDIA_ROOT, settings.MAPS_ROOT,
				self.slug, "thumb", name)

	thumbnail_path = property(_get_thumbnail_path)

	def _get_thumbnail_url(self):
		name = self.get_map_name()
		if name == "" or not self.started:
			return self.scenario.thumbnail_url
		else:
			return os.path.join(settings.MEDIA_URL, settings.MAPS_ROOT,
				self.slug, "thumb", name)
	
	thumbnail_url = property(_get_thumbnail_url)

	def remove_private_maps(self):
		for p in self.player_set.filter(user__isnull=False):
			path = self.get_map_path(p)
			try:
				os.remove(path)
			except:
				logger.error("Can't delete map %s" % path)

	##------------------------
	## game starting methods
	##------------------------

	def start(self):
		""" Starts the game """
		if not self.started is None:
			## the game is already started
			return
		if logging:
			logger.info("Starting game %s" % self.id)
		if self.private:
			self.invitation_set.all().delete()
		self.slots = 0
		self.year = self.scenario.start_year
		self.season = 1
		self.phase = PHORDERS
		self.create_game_board()
		if self.scenario.setting.configuration.trade_routes:
			self.create_routes()
		self.shuffle_countries()
		self.copy_country_data()
		if self.teams > 1:
			self.make_teams()
		self.home_control_markers()
		self.place_initial_units()
		if self.configuration.finances:
			self.assign_initial_income()
		if self.configuration.assassinations:
			self.create_assassins()
		self.started = datetime.now()
		self.last_phase_change = datetime.now()
		self.notify_players("game_started", {"game": self})
		self.save()
		self.make_map(fow=self.configuration.fow)

	def player_joined(self):
		self.slots -= 1
		self.save()
	
	def shuffle_countries(self):
		""" Assign a Country of the Scenario to each Player, randomly. """
		#countries = self.scenario.setup_set.exclude(country__isnull=True).values_list('country', flat=True).distinct()
		contenders = self.scenario.contender_set.exclude(country__isnull=True)
		#countries = list(countries)
		contenders = list(contenders)
		players = self.player_set.filter(user__isnull=False)
		## TODO: Enable this when condottieri_tournament is adapted to condottieri_scenarios
		#neutral_count = len(countries) - players.count()
		#if neutral_count > 0:
			## there are more countries than players
		#	neutral_ids = self.scenario.neutral_set.values_list('country', flat=True)[:neutral_count]
		#	countries = [item for item in countries if item not in neutral_ids]
		#################################################################
		## a list of tuples will be returned
		assignment = []
		## shuffle the list of countries
		#random.shuffle(countries)
		random.shuffle(contenders)
		for player in self.player_set.filter(user__isnull=False):
			#assignment.append((player, countries.pop()))
			assignment.append((player, contenders.pop()))
		for t in assignment:
			#t[0].country = Country.objects.get(id=t[1])
			t[0].contender = t[1]
			t[0].save()

	def copy_country_data(self):
		""" Copies to the player objects some properties that will never change during the game.
		This way, I hope to save some hits to the database """
		excom = self.configuration.excommunication
		finances = self.configuration.finances

		for p in self.player_set.filter(user__isnull=False):
			#p.static_name = p.country.static_name
			p.static_name = p.contender.country.static_name
			if excom:
				#p.may_excommunicate = p.country.can_excommunicate
				p.may_excommunicate = p.contender.country.can_excommunicate
			if finances:
				#t = self.scenario.treasury_set.get(country=p.country)
				#p.double_income = t.double
				p.double_income = p.contender.treasury.double
			p.save()

	def make_teams(self):
		""" Make self.teams teams and assign each player to a team """
		teams = []
		for i in range(0, self.teams):
			team = Team(game=self)
			team.save()
			teams.append(team)
		players = self.player_set.filter(user__isnull=False)
		players = list(players)
		random.shuffle(players)
		size = len(players) // len(teams)
		i = 0
		t = 0
		while 1:
			try:
				p = players.pop()
			except IndexError:
				return
			if i == size:
				t += 1
				i = 0
			p.team = teams[t]
			p.save()
			i += 1

	def get_disabled_areas(self):
		""" Returns the disabled Areas in the game scenario """
		enabled = self.gamearea_set.values_list('board_area', flat=True)
		#return Area.objects.filter(disabledarea__scenario=self.scenario)
		return Area.objects.filter(setting=self.scenario.setting).exclude(id__in=enabled)

	def create_game_board(self):
		""" Creates the GameAreas for the Game.	"""
		##TODO: Uncomment when condottieri_tournament is adapted to condottieri_scenarios
		disabled_ids = Area.objects.filter(disabledarea__scenario=self.scenario).values_list('id', flat=True)
		#countries = self.scenario.setup_set.exclude(country__isnull=True).values_list('country', flat=True).distinct()
		#player_count = self.player_set.exclude(user__isnull=True).count()
		#neutral_count = countries.count() - player_count
		neutral_ids = []
		#if neutral_count > 0:
		#	neutrals = self.scenario.neutral_set.values_list('country', flat=True)[:neutral_count]
		#	neutrals = list(neutrals)
		#	neutral_ids = self.scenario.home_set.filter(country__id__in=neutrals, is_home=True).values_list('area__id', flat=True)
		for a in Area.objects.filter(setting=self.scenario.setting):
			if not (a.id in disabled_ids or a.id in neutral_ids):
				ga = GameArea(game=self, board_area=a)
				ga.save()

	def create_routes(self):
		""" Creates game trade routes """
		routes = TradeRoute.objects.filter(routestep__area__setting=self.scenario.setting).distinct()
		for r in routes:
			gr = GameRoute(game=self, trade_route=r)
			gr.save()

	def get_autonomous_setups(self):
		return self.scenario.autonomous
	
	def place_initial_garrisons(self):
		""" Creates the Autonomous Player, and places the autonomous garrisons at the
		start of the game.
		"""
		## create the autonomous player
		contender = self.scenario.contender_set.get(country__isnull=True)
		autonomous = Player(game=self, done=True, contender=contender)
		autonomous.save()
		for s in self.get_autonomous_setups():
			try:
				a = GameArea.objects.get(game=self, board_area=s.area)
			except:
				print "Error 1: Area not found!"
			else:	
				if s.unit_type:
					new_unit = Unit(type='G', area=a, player=autonomous)
					new_unit.save()

	def home_control_markers(self):
		for p in self.player_set.filter(user__isnull=False):
			p.home_control_markers()

	def place_initial_units(self):
		for p in self.player_set.filter(user__isnull=False):
			p.place_initial_units()
		self.place_initial_garrisons()

	def assign_initial_income(self):
		for p in self.player_set.filter(user__isnull=False):
			#t = self.scenario.treasury_set.get(country=p.country)
			#p.ducats = t.ducats
			p.ducats = p.contender.treasury.ducats
			p.save()

	def create_assassins(self):
		""" Assign each player an assassination counter for each of the other players """
		for p in self.player_set.filter(user__isnull=False):
			for q in self.player_set.filter(user__isnull=False):
				if q == p:
					continue
				assassin = Assassin()
				assassin.owner = p
				#assassin.target = q.country
				assassin.target = q.contender.country
				assassin.save()

	##--------------------------
	## time controlling methods
	##--------------------------

	def clear_phase_cache(self):
		cache_keys = [
			"game-%s_player_list" % self.pk,
			"game-%s_all-units" % self.pk,
			"game-%s_all-areas" % self.pk,
			"game-%s_log" % self.pk,
		]
		try:
			cache.delete_many(cache_keys)
		except:
			logger.error("Error while deleting cache keys")
		for p in self.player_set.filter(user__isnull=False):
			p.clear_phase_cache()

	def get_highest_karma(self):
		""" Returns the karma of the non-finished player with the highest value.
			
			Returns 0 if all the players have finished.
		"""

		players = CondottieriProfile.objects.filter(user__player__game=self,
								user__player__done=False).order_by('-karma')
		if len(players) > 0:
			return float(players[0].karma)
		return 0


	def next_phase_change(self):
		""" Returns the Time of the next compulsory phase change. """
		if self.phase == PHINACTIVE :
			return False	
		if not self.uses_karma:
			## do not use karma
			time_limit = self.time_limit
		else:
			## get the player with the highest karma, and not done
			highest = self.get_highest_karma()
			if highest > 100:
				if self.phase == PHORDERS:
					k = 1 + (highest - 100) / 200
				else:
					k = 1
			else:
				k = highest / 100
			time_limit = self.time_limit * k
			## if extended_deadline, add the base time limit
			if self.extended_deadline:
				time_limit += self.time_limit
		
		duration = timedelta(0, time_limit)

		return self.last_phase_change + duration
	

	def force_phase_change(self):
		""" When the time limit is reached and one or more of the players are
		not done, if game is not in extended deadline, make extended_deadline
		true. If game is already in extended deadline, force next turn.
		"""
		if not self.extended_deadline:
			self.extended_deadline = True
			self.save()
			## create or update revolutions for lazy players
			for p in self.player_set.all():
				if not p.done:
					p.check_revolution()
		else: #game in extended deadline
			for p in self.player_set.all():
				if not p.done:
					p.end_phase(forced=True)
		
	def time_to_limit(self):
		""" Calculates the time to the next phase change and returns it as a
		timedelta.
		"""
		if not self.phase == PHINACTIVE:
			limit = self.next_phase_change()
			return limit - datetime.now()
	
	def time_is_exceeded(self):
		"""
		Checks if the time limit has been reached. If yes, return True
		"""
		return self.time_to_limit() <= timedelta(0, 0)

	def check_finished_phase(self):
		""" This method is to be called by a management script, called by cron.
		It checks if all the players are done, then process the phase.
		If at least a player is not done, check the time limit
		"""
		players = self.player_set.all()
		msg = u"Checking phase change in game %s\n" % self.pk
		if self.time_is_exceeded():
			msg += u"Time exceeded.\n"
			self.force_phase_change()
		for p in players:
			if not p.done:
				msg += u"At least a player is not done.\n"
				return False
		msg += u"All players done.\n"
		if logging:
			logger.info(msg)
		self.process_turn()
		self.clear_phase_cache()
		## If I don't reload players, p.new_phase overwrite the changes made by
		## self.assign_incomes()
		## TODO: optimize this
		players = self.player_set.all()
		for p in players:
			p.new_phase()

	
	def check_bonus_time(self):
		""" Returns true if, when the function is called, the first BONUS_TIME% of the
		duration has not been reached.
		"""

		duration = timedelta(0, self.time_limit * BONUS_TIME)
		limit = self.last_phase_change + duration
		to_limit = limit - datetime.now()
		if to_limit >= timedelta(0, 0):
			return True
		else:
			return False

	def get_bonus_deadline(self):
		""" Returns the latest time when karma is bonified """
		duration = timedelta(0, self.time_limit * BONUS_TIME)
		return self.last_phase_change + duration
	
	def _next_season(self):
		## take a snapshot of the units layout
		#thread.start_new_thread(save_snapshot, (self,))
		#save_snapshot(self)
		if self.season == 3:
			self.season = 1
			self.year += 1
		else:
			self.season += 1
		## delete all retreats and standoffs
		Unit.objects.filter(player__game=self).update(must_retreat='')
		GameArea.objects.filter(game=self).update(standoff=False)

	def process_turn(self):
		## remove current private maps in games with Fog of War
		if self.configuration.fow:
			self.remove_private_maps()
		##
		end_season = False
		if self.phase == PHINACTIVE:
			return
		elif self.phase == PHREINFORCE:
			self.auto_reinforcements()
			self.adjust_units()
			next_phase = PHORDERS
		elif self.phase == PHORDERS:
			if self.configuration.lenders:
				self.check_loans()
			if self.configuration.finances:
				self.process_expenses()
			if self.configuration.taxation:
				for a in self.gamearea_set.filter(taxed=True):
					if a.famine:
						a.check_assassination_rebellion(mod=a.board_area.control_income - 1)
			if self.configuration.assassinations:
				self.process_assassinations()
			if self.configuration.assassinations or self.configuration.lenders:
				## if a player is assassinated, all his orders become 'H'
				for p in self.player_set.filter(assassinated=True):
					p.cancel_orders()
					for area in p.gamearea_set.exclude(board_area__is_sea=True):
						area.check_assassination_rebellion()
			self.process_orders()
			Order.objects.filter(unit__player__game=self).delete()
			retreats_count = Unit.objects.filter(player__game=self).exclude(must_retreat__exact='').count()
			if retreats_count > 0:
				next_phase = PHRETREATS
			else:
				if self.configuration.strategic:
					next_phase = PHSTRATEGIC
				else:
					end_season = True
		elif self.phase == PHRETREATS:
			self.process_retreats()
			if self.configuration.strategic:
				next_phase = PHSTRATEGIC
			else:
				end_season = True
		elif self.phase == PHSTRATEGIC:
			self.process_strategic_movements()
			end_season = True
		if end_season:
			## delete repressed rebellions
			Rebellion.objects.filter(player__game=self, repressed=True).delete()
			if self.season == 1:
				## delete units in famine areas
				if self.configuration.famine:
					famine_units = Unit.objects.filter(player__game=self, area__famine=True)
					for f in famine_units:
						f.delete()
					## reset famine markers
					self.gamearea_set.all().update(famine=False)
					## check plagues
					self.kill_plague_units()
			elif self.season == 2:
				## if storms are enabled, place storm markers
				self.mark_storm_areas()
			elif self.season == 3:
				## if storms are enabled, delete fleets in storm areas
				if self.configuration.storms:
					storm_units = Unit.objects.filter(player__game=self, area__storm=True)
					for f in storm_units:
						f.delete()
					## reset storm markers
					self.gamearea_set.all().update(storm=False)
				## check if any users are eliminated
				to_eliminate = []
				for p in self.player_set.filter(eliminated=False,
												user__isnull=False):
					if p.check_eliminated():
						to_eliminate.append(p)
				for p in to_eliminate:
					p.eliminate()
				self.update_controls()
				## if conquering is enabled, check conquerings
				if self.configuration.conquering:
					self.check_conquerings()
				winner = self.check_winner()
				if winner:
					if isinstance(winner, Player):
						self.assign_scores()
					elif isinstance(winner, Team):
						self.assign_team_scores()
					self.game_over()
					return
				## if famine enabled, place famine markers
				if self.configuration.famine:
					self.mark_famine_areas()
			## reset taxation
			if self.configuration.taxation:
				taxed = self.gamearea_set.filter(taxed=True)
				taxed.update(famine=True)
				for t in taxed:
					signals.famine_marker_placed.send(sender=t)
				self.gamearea_set.all().update(taxed=False)
			## check which trade routes are safe
			if self.scenario.setting.configuration.trade_routes:
				for r in self.gameroute_set.all():
					r.update_status()
			## if finances are enabled, assign incomes
			## this has been moved after taxation famines
			if self.season == 3 and self.configuration.finances:
				self.assign_incomes()
			## reset assassinations, and the pope can excommunicate again
			self.player_set.all().update(assassinated=False, has_sentenced=False)
			self._next_season()
			if self.season == 1:
				## if there are not finances all units are paid
				if not self.configuration.finances:
					next_phase = PHORDERS
					Unit.objects.filter(player__game=self).update(paid=True)
					for p in self.player_set.all():
						if p.units_to_place() != 0:
							next_phase = PHREINFORCE
							break
				else:
					## if playing with finances, reinforcement phase must be always played
					next_phase = PHREINFORCE
					## autonomous units are automatically paid
					Unit.objects.filter(player__game=self, player__user__isnull=True).update(paid=True) 
			else:
				next_phase = PHORDERS
		self.phase = next_phase
		self.last_phase_change = datetime.now()
		#self.map_changed()
		self.extended_deadline = False
		self.save()
		self.make_map(fow=self.configuration.fow)
		if end_season and self.configuration.fow:
			for dip in Diplomat.objects.filter(player__game=self):
				dip.uncover()
		self.notify_players("new_phase", {"game": self})
   	
	def auto_reinforcements(self):
		## automatic reinforcements for players not done OR surrendered
		for p in self.player_set.exclude(done=True, surrendered=False):
			if self.configuration.finances:
				units = Unit.objects.filter(player=p).order_by('id')
				ducats = p.ducats
				for u in units:
					if ducats >= u.cost:
						u.paid = True
						u.save()
						ducats -= u.cost
				p.ducats = ducats
				p.save()
			else:
				units = Unit.objects.filter(player=p).order_by('-id')
				reinforce = p.units_to_place()
				if reinforce < 0:
					## delete the newest units
					for u in units[:-reinforce]:
						u.paid = False
						u.save()

	def adjust_units(self):
		""" Places new units and disbands the ones that are not paid """
		to_disband = Unit.objects.filter(player__game=self, paid=False)
		for u in to_disband:
			u.delete()
		to_place = Unit.objects.filter(player__game=self, placed=False)
		for u in to_place:
			u.place()
		## mark as unpaid all units
		Unit.objects.filter(player__game=self).update(paid=False)

	##------------------------
	## optional rules methods
	##------------------------
	def check_conquerings(self):
		if not self.configuration.conquering:
			return
		## a player can only be conquered if he is eliminated
		for p in self.player_set.filter(eliminated=True):
			## try fo find a home province that is not controlled by any player
			neutral = GameArea.objects.filter(game=self,
				#board_area__home__contender=p.contender,
				#board_area__home__is_home=True,
				home_of=p,
				player__isnull=True).count()
			if neutral > 0:
				continue
			## get the players that control part of this player's home country
			#controllers = self.player_set.filter(gamearea__board_area__home__contender=p.contender,
			#	gamearea__board_area__home__is_home=True).distinct()
			controllers = self.player_set.filter(gamearea__home_of=p).distinct()
			if len(controllers) == 1:
				## all the areas in home country belong to the same player
				if p != controllers[0] and p.conqueror != controllers[0]:
					## controllers[0] conquers p
					p.set_conqueror(controllers[0])

	def mark_famine_areas(self):
		if not self.configuration.famine:
			return
		#codes = disasters.get_famine()
		year = disasters.get_year()
		row = disasters.get_row(year)
		column = disasters.get_column(year)
		codes = FamineCell.objects.roll(self.scenario.setting, row, column).values_list('area__code', flat=True)
		famine_areas = GameArea.objects.filter(game=self, board_area__code__in=codes)
		for f in famine_areas:
			print f
			f.famine=True
			f.save()
			signals.famine_marker_placed.send(sender=f)
	
	def mark_storm_areas(self):
		if not self.configuration.storms:
			return
		#codes = disasters.get_storms()
		year = disasters.get_year()
		row = disasters.get_row(year)
		column = disasters.get_column(year)
		codes = StormCell.objects.roll(self.scenario.setting, row, column).values_list('area__code', flat=True)
		storm_areas = GameArea.objects.filter(game=self, board_area__code__in=codes)
		for f in storm_areas:
			f.storm=True
			f.save()
			signals.storm_marker_placed.send(sender=f)
	
	def kill_plague_units(self):
		if not self.configuration.plague:
			return
		#codes = disasters.get_plague()
		year = disasters.get_year()
		row = disasters.get_row(year)
		column = disasters.get_column(year)
		codes = PlagueCell.objects.roll(self.scenario.setting, row, column).values_list('area__code', flat=True)
		plague_areas = GameArea.objects.filter(game=self, board_area__code__in=codes)
		for p in plague_areas:
			signals.plague_placed.send(sender=p)
			for u in p.unit_set.all():
				u.delete()

	def assign_incomes(self):
		""" Gets each player's income and add it to the player's treasury """
		## get the column for variable income
		die = dice.roll_1d6()
		if logging:
			msg = "Varible income: Got a %s in game %s" % (die, self)
			logger.info(msg)
		## get a list of the ids of the major cities that generate income
		majors = self.scenario.major_cities
		majors_ids = majors.values_list('city', flat=True)
		##
		players = self.player_set.filter(user__isnull=False, eliminated=False)
		for p in players:
			i = p.get_income(die, majors_ids)
			if i > 0:
				p.add_ducats(i)

	def check_loans(self):
		""" Check if any loans have exceeded their terms. If so, apply the
		penalties. """
		loans = Loan.objects.filter(player__game=self)
		for loan in loans:
			if self.year >= loan.year and self.season >= loan.season:
				## the loan has exceeded its term
				if logging:
					msg = "%s defaulted" % loan.player
					logger.info(msg)
				loan.player.defaulted = True
				loan.player.save()
				loan.player.assassinate()
				loan.delete()
	
	def process_expenses(self):
		## undo unconfirmed expenses
		invalid_expenses = Expense.objects.filter(player__game=self, confirmed=False)
		for e in invalid_expenses:
			e.undo()
		## log expenses (ignore diplomats)
		if signals:
			for e in Expense.objects.filter(player__game=self, confirmed=True).exclude(type__in=(10,11)):
				signals.expense_paid.send(sender=e)
		## then, process famine reliefs
		for e in Expense.objects.filter(player__game=self, type=0):
			e.area.famine = False
			e.area.save()
		## then, delete the rebellions
		for e in Expense.objects.filter(player__game=self, type=1):
			Rebellion.objects.filter(area=e.area).delete()
		## then, place new rebellions
		for e in Expense.objects.filter(player__game=self, type__in=(2,3)):
			try:
				rebellion = Rebellion(area=e.area)
				rebellion.save()
			except:
				continue
		## create diplomats
		for e in Expense.objects.filter(player__game=self, type__in=(10,11)):
			try:
				dip = Diplomat(player=e.player, area=e.area)
				dip.save()
			except:
				continue
		## then, delete bribes that are countered
		expenses = Expense.objects.filter(player__game=self)
		for e in expenses:
			if e.is_bribe():
				## get the sum of counter-bribes
				cb = Expense.objects.filter(player__game=self, type=4, unit=e.unit).aggregate(Sum('ducats'))
				if not cb['ducats__sum']:
					cb['ducats__sum'] = 0
				total_cost = get_expense_cost(e.type, e.unit) + cb['ducats__sum']
				if total_cost > e.ducats:
					e.delete()
		## then, resolve the bribes for each bribed unit
		bribed_ids = Expense.objects.filter(unit__player__game=self, type__in=(5,6,7,8,9)).values_list('unit', flat=True).distinct()
		chosen = []
		## TODO: if two bribes have the same value, decide randomly between them
		for i in bribed_ids:
			bribes = Expense.objects.filter(type__in=(5,6,7,8,9), unit__id=i).order_by('-ducats')
			chosen.append(bribes[0])
		## all bribes in 'chosen' are successful, and executed
		for c in chosen:
			if c.type in (5, 8): #disband unit
				c.unit.delete()
			elif c.type in (6, 9): #buy unit
				c.unit.change_player(c.player)
			elif c.type == 7: #to autonomous
				c.unit.to_autonomous()
		## finally, delete all the expenses
		Expense.objects.filter(player__game=self).delete()

	def get_rebellions(self):
		""" Returns a queryset with all the rebellions in this game """
		return Rebellion.objects.filter(area__game=self)

	def process_assassinations(self):
		""" Resolves all the assassination attempts """
		attempts = Assassination.objects.filter(killer__game=self)
		victims = []
		msg = u"Processing assassinations in game %s:\n" % self
		for a in attempts:
			msg += u"\n%s spends %s ducats to kill %s\n" % (a.killer, a.ducats, a.target)
			signals.assassination_attempted.send(sender=a.target)
			if a.target in victims:
				msg += u"%s already killed\n" % a.target
				continue
			if self.version < 2:
				dice_rolled = int(a.ducats / 12)
			else:
				dice_rolled = a.get_dice()
			if dice_rolled < 1:
				msg += u"%s are not enough" % a.ducats
				continue
			msg += u"%s dice will be rolled\n" % dice_rolled
			if dice.check_one_six(dice_rolled):
				msg += u"Attempt is successful\n"
				## attempt is successful
				a.target.assassinate()
				victims.append(a.target)
			else:
				msg += u"Attempt fails\n"
		attempts.delete()
		if logging:
			logger.info(msg)


	##------------------------
	## turn processing methods
	##------------------------

	def get_conflict_areas(self):
		""" Returns the orders that could result in a possible conflict these are the
		advancing units and the units that try to convert into A or F.
		"""

		conflict_orders = Order.objects.filter(unit__player__game=self, code__in=['-', '=']).exclude(type__exact='G')
		conflict_areas = []
		for o in conflict_orders:
			if o.code == '-':
				if o.unit.area.board_area.is_adjacent(o.destination.board_area, fleet=(o.unit.type=='F')) or \
					o.find_convoy_line():
						area = o.destination
				else:
					continue
			else:
				## unit trying to convert into A or F
				area = o.unit.area
			conflict_areas.append(area)
		return conflict_areas

	def filter_supports(self):
		""" Checks which Units with support orders are being attacked and delete their
		orders.
		"""

		conflict_areas = self.get_conflict_areas()
		for step in (1, 2):
			## This for sequence is run twice.
			## In the first pass, all the supporting units under attack are deleted, except the ones
			## where the attack comes from the area they are supporting an advance to.
			## In the second pass, every support order being attacked by a superior force is deleted
			## because the unit will be dislodged.
			if step == 1:
				info = u"Step 2a: Cancel supports from units under attack.\n"
			elif step == 2:
				info += u"Step 2b: Cancel supports from units that will be dislodged.\n"
			support_orders = Order.objects.filter(unit__player__game=self, code__exact='S')
			for s in support_orders:
				info += u"Checking order %s.\n" % s
				if s.unit.type != 'G' and s.unit.area in conflict_areas:
					attacks = Order.objects.filter(~Q(unit__player=s.unit.player) &
												((Q(code__exact='-') & Q(destination=s.unit.area)) |
												(Q(code__exact='=') & Q(unit__area=s.unit.area) &
												Q(unit__type__exact='G'))))
					if len(attacks) > 0:
						info += u"Supporting unit is being attacked.\n"
						for a in attacks:
							if (s.subcode == '-' and s.subdestination == a.unit.area) or \
							(s.subcode == '=' and s.subtype in ['A','F'] and s.subunit.area == a.unit.area):
								if step == 1:
									info += u"Attack comes from area where support is given. Support is not broken.\n"
									info += u"Support will be broken if the unit is dislodged.\n"
									continue
								elif step == 2:
									a_unit = Unit.objects.get_with_strength(self, id=a.unit.id)
									d_unit = Unit.objects.get_with_strength(self, id=s.unit.id)
									if a_unit.strength > d_unit.strength:
										info += u"Attack from %s breaks support (unit dislodged).\n" % a_unit
										signals.support_broken.send(sender=s.unit)
										s.delete()
										break
							else:
								if step == 1:
									info += u"Attack from %s breaks support.\n" % a.unit
									signals.support_broken.send(sender=s.unit)
									s.delete()
									break
		return info

	def filter_convoys(self):
		""" Checks which Units with C orders are being attacked. Checks if they
		are going to be defeated, and if so, delete the C order. However, it
		doesn't resolve the conflict
		"""

		info = u"Step 3: Cancel convoys by fleets that will be dislodged.\n"
		## find units attacking fleets
		sea_attackers = Unit.objects.filter(Q(player__game=self),
											(Q(order__code__exact='-') &
											Q(order__destination__board_area__is_sea=True)) |
											(Q(order__code__exact='=') &
											Q(area__board_area__mixed=True) &
											Q(type__exact='G')))
		for s in sea_attackers:
			order = s.get_order()
			try:
				## find the defender
				if order.code == '-':
					defender = Unit.objects.get(player__game=self,
											area=order.destination,
											type__exact='F',
											order__code__exact='C')
				elif order.code == '=' and s.area.board_area.mixed:
					defender = Unit.objects.get(player__game=self,
												area=s.area,
												type__exact='F',
												order__code__exact='C')
			except:
				## no attacked convoying fleet is found 
				continue
			else:
				info += u"Convoying %s is being attacked by %s.\n" % (defender, s)
				a_strength = Unit.objects.get_with_strength(self, id=s.id).strength
				d_strength = Unit.objects.get_with_strength(self, id=defender.id).strength
				if a_strength > d_strength:
					d_order = defender.get_order()
					if d_order:
						info += u"%s can't convoy.\n" % defender
						defender.delete_order()
					else:
						continue
		return info
	
	def filter_unreachable_attacks(self):
		""" Delete the orders of units trying to go to non-adjacent areas and not
		having a convoy line.
		"""

		info = u"Step 4: Cancel attacks to unreachable areas.\n"
		attackers = Order.objects.filter(unit__player__game=self, code__exact='-')
		for o in attackers:
			is_fleet = (o.unit.type == 'F')
			if not o.unit.area.board_area.is_adjacent(o.destination.board_area, is_fleet):
				if is_fleet:
					info += u"Impossible attack: %s.\n" % o
					o.delete()
				else:
					if not o.find_convoy_line():
						info += u"Impossible attack: %s.\n" % o
						o.delete()
		return info
	
	def resolve_auto_garrisons(self):
		""" Units with '= G' orders in areas without a garrison, convert into garrison.
		"""

		info = u"Step 1: Garrisoning units.\n"
		garrisoning = Unit.objects.filter(player__game=self,
									order__code__exact='=',
									order__type__exact='G')
		for g in garrisoning:
			info += u"%s tries to convert into garrison.\n" % g
			try:
				defender = Unit.objects.get(player__game=self,
										type__exact='G',
										area=g.area)
			except:
				try:
					Rebellion.objects.get(area=g.area, garrisoned=True)
				except ObjectDoesNotExist:
					info += u"Success!\n"
					g.convert('G')
				else:
					info += u"There is a garrisoned rebellion.\n"
				g.delete_order()
			else:
				info += u"Fail: there is a garrison in the city.\n"
		return info

	def resolve_conflicts(self):
		""" Conflict: When two or more units want to occupy the same area.
		
		This method takes all the units and decides which unit occupies each conflict
		area and which units must retreat.
		"""

		## units sorted (reverse) by a temporary strength attribute
		## strength = 1 means unit without supports
		info = u"Step 5: Process conflicts.\n"
		units = Unit.objects.list_with_strength(self)
		conditioned_invasions = []
		conditioned_origins = []
		finances = self.configuration.finances
		holding = []
		## iterate all the units
		for u in units:
			## discard all the units with H, S, B, C or no orders
			## they will not move
			u_order = u.get_order()
			if not u_order:
				info += u"%s has no orders.\n" % u
				continue
			else:
				info += u"%s was ordered: %s.\n" % (u, u_order)
				if finances and u_order.code == 'H' and not u.type == 'G':
					## the unit counts for removing a rebellion
					holding.append(u)
				if u_order.code in ['H', 'S', 'B', 'C']:
					continue
			##################
			s = u.strength
			info += u"Total strength = %s.\n" % s
			## rivals and defender are the units trying to enter into or stay
			## in the same area as 'u'
			rivals = u_order.get_rivals()
			defender = u_order.get_defender()
			info += u"Unit has %s rivals.\n" % len(rivals)
			conflict_area = u.get_attacked_area()
			##
			if conflict_area.standoff:
				info += u"Trying to enter a standoff area.\n"
				#u.delete_order()
				continue
			else:
				standoff = False
			## if there is a rival with the same strength as 'u', there is a
			## standoff.
			## if not, check for defenders
			for r in rivals:
				strength = Unit.objects.get_with_strength(self, id=r.id).strength
				info += u"Rival %s has strength %s.\n" % (r, strength)
				if strength >= s: #in fact, strength cannot be greater
					info += u"Rival wins.\n"
					standoff = True
					exit
				else:
					## the rival is defeated and loses its orders
					info += u"Deleting order of %s.\n" % r
					r.delete_order()
			## if there is a standoff, delete the order and all rivals' orders
			if standoff:
				conflict_area.mark_as_standoff()
				info += u"Standoff in %s.\n" % conflict_area
				for r in rivals:
					r.delete_order()
				u.delete_order()
				continue
			## if there is no standoff, rivals allow the unit to enter the area
			## then check what the defenders think
			else:
				## if there is a defender
				if isinstance(defender, Unit):
					## this is a hack to prevent a unit from invading a friend
					## a 'friend enemy' is always as strong as the invading unit
					if defender.player == u.player:
						strength = s
						info += u"Defender is a friend.\n"
					else:
						strength = Unit.objects.get_with_strength(self,
														id=defender.id).strength
					info += u"Defender %s has strength %s.\n" % (defender, strength)
					## if attacker is not as strong as defender
					if strength >= s:
						## if the defender is trying to exchange areas with
						## the attacker, there is a standoff in the defender's
						## area
						if defender.get_attacked_area() == u.area:			
							defender.area.mark_as_standoff()
							info += u"Trying to exchange areas.\n"
							info += u"Standoff in %s.\n" % defender.area
						else:
						## the invasion is conditioned to the defender leaving
							info += u"%s's movement is conditioned.\n" % u
							inv = Invasion(u, defender.area)
							if u_order.code == '-':
								info += u"%s might get empty.\n" % u.area
								conditioned_origins.append(u.area)
							elif u_order.code == '=':
								inv.conversion = u_order.type
							conditioned_invasions.append(inv)
					## if the defender is weaker, the area is invaded and the
					## defender must retreat
					else:
						defender.must_retreat = u.area.board_area.code
						defender.save()
						if u_order.code == '-':
							u.invade_area(defender.area)
							info += u"Invading %s.\n" % defender.area
						elif u_order.code == '=':
							info += u"Converting into %s.\n" % u_order.type
							u.convert(u_order.type)
						defender.delete_order()
				## no defender means either that the area is empty *OR*
				## that there is a unit trying to leave the area
				else:
					info += u"There is no defender.\n"
					try:
						unit_leaving = Unit.objects.get(type__in=['A','F'],
												area=conflict_area)
					except ObjectDoesNotExist:
						## if the province is empty, invade it
						info += u"Province is empty.\n"
						if u_order.code == '-':
							info += u"Invading %s.\n" % conflict_area
							u.invade_area(conflict_area)
						elif u_order.code == '=':
							info += u"Converting into %s.\n" % u_order.type
							u.convert(u_order.type)
					else:
						## if the area is not empty, and the unit in province
						## is not a friend, and the attacker has supports
						## it invades the area, and the unit in the province
						## must retreat (if it invades another area, it mustnt).
						if unit_leaving.player != u.player and u.strength > unit_leaving.power:
							info += u"There is a unit in %s, but attacker is supported and beats defender's power.\n" % conflict_area
							unit_leaving.must_retreat = u.area.board_area.code
							unit_leaving.save()
							if u_order.code == '-':
								u.invade_area(unit_leaving.area)
								info += u"Invading %s.\n" % unit_leaving.area
							elif u_order.code == '=':
								info += u"Converting into %s.\n" % u_order.type
								u.convert(u_order.type)
						## if the area is not empty, the invasion is conditioned
						else:
							info += u"Area is not empty and attacker isn't supported, or there is a friend\n"
							info += u"%s movement is conditioned.\n" % u
							inv = Invasion(u, conflict_area)
							if u_order.code == '-':
								info += u"%s might get empty.\n" % u.area
								conditioned_origins.append(u.area)
							elif u_order.code == '=':
								inv.conversion = u_order.type
							conditioned_invasions.append(inv)
		## at this point, all the 'easy' movements and conversions have been
		## made, and we have a conditioned_invasions sequence
		## conditioned_invasions is a list of Invasion objects:
		##
		## in a first iteration, we solve the conditioned_invasions directed
		## to now empty areas
		try_empty = True
		while try_empty:
			info += u"Looking for possible, conditioned invasions.\n"
			try_empty = False
			for ci in conditioned_invasions:
				if ci.area.province_is_empty():
					info += u"Found empty area in %s.\n" % ci.area
					if ci.unit.area in conditioned_origins:
						conditioned_origins.remove(ci.unit.area)
					if ci.conversion == '':
						ci.unit.invade_area(ci.area)
					else:
						ci.unit.convert(ci.conversion)
					conditioned_invasions.remove(ci)
					try_empty = True
					break
		## in a second iteration, we cancel the conditioned_invasions that
		## cannot be made
		try_impossible = True
		while try_impossible:
			info += u"Looking for impossible, conditioned.\n"
			try_impossible = False
			for ci in conditioned_invasions:
				if not ci.area in conditioned_origins:
					## the unit is trying to invade an area with a stationary
					## unit
					info += u"Found impossible invasion in %s.\n" % ci.area
					ci.area.mark_as_standoff()
					conditioned_invasions.remove(ci)
					if ci.unit.area in conditioned_origins:
						conditioned_origins.remove(ci.unit.area)
					try_impossible = True
					break
		## at this point, if there are any conditioned_invasions, they form
		## closed circuits, so all of them should be carried out
		info += u"Resolving closed circuits.\n"
		for ci in conditioned_invasions:
			if ci.conversion == '':
				info += u"%s invades %s.\n" % (ci.unit, ci.area)
				ci.unit.invade_area(ci.area)
			else:
				info += u"%s converts into %s.\n" % (ci.unit, ci.conversion)
				ci.unit.convert(ci.conversion)
		## units in 'holding' that don't need to retreat, can put rebellions down
		for h in holding:
			if h.must_retreat != '':
				continue
			else:
				reb = h.area.has_rebellion(h.player, same=True)
				if reb and not reb.garrisoned:
					info += u"Rebellion in %s is put down.\n" % h.area
					reb.delete()
		
		info += u"End of conflicts processing"
		return info

	def resolve_sieges(self):
		## get units that are besieging but do not besiege a second time
		info = u"Step 6: Process sieges.\n"
		broken = Unit.objects.filter(Q(player__game=self,
									besieging__exact=True),
									~Q(order__code__exact='B'))
		for b in broken:
			info += u"Siege of %s is discontinued.\n" % b
			b.besieging = False
			b.save()		
		## get besieging units
		besiegers = Unit.objects.filter(player__game=self,
										order__code__exact='B')
		for b in besiegers:
			info += u"%s besieges " % b
			mode = ''
			if b.player.assassinated:
				info += u"\n%s belongs to an assassinated player.\n" % b
				continue
			try:
				defender = Unit.objects.get(player__game=self,
										type__exact='G',
										area=b.area)
			except:
				reb = b.area.has_rebellion(b.player, same=True)
				if reb and reb.garrisoned:
					mode = 'rebellion'
					info += u"a rebellion "
				else:
					ok = False
					info += u"Besieging an empty city. Ignoring.\n"
					b.besieging = False
					b.save()
					continue
			else:
				mode = 'garrison'
			if mode != '':
				if b.besieging:
					info += u"for second time.\n"
					b.besieging = False
					info += u"Siege is successful. "
					if mode == 'garrison':
						info += u"Garrison disbanded.\n" 
						if signals:
							signals.unit_surrendered.send(sender=defender)
						else:
							self.log_event(UnitEvent, type=defender.type,
												area=defender.area.board_area,
												message=2)
						defender.delete()
					elif mode == 'rebellion':
						info += u"Rebellion is put down.\n"
						reb.delete()
					b.save()
				else:
					info += u"for first time.\n"
					b.besieging = True
					if signals:
						signals.siege_started.send(sender=b)
					else:
						self.log_event(UnitEvent, type=b.type, area=b.area.board_area, message=3)
					if mode == 'garrison' and defender.player.assassinated:
						info += u"Player is assassinated. Garrison surrenders\n"
						if signals:
							signals.unit_surrendered.send(sender=defender)
						else:
							log_event(UnitEvent, type=defender.type,
								area=defender.area.board_area,
								message=2)
						defender.delete()
						b.besieging = False	
					b.save()
			b.delete_order()
		return info
	
	def announce_retreats(self):
		info = u"Step 7: Retreats\n"
		retreating = Unit.objects.filter(player__game=self).exclude(must_retreat__exact='')
		for u in retreating:
			info += u"%s must retreat.\n" % u
			if signals:
				signals.forced_to_retreat.send(sender=u)
			else:
				self.log_event(UnitEvent, type=u.type, area=u.area.board_area, message=1)
			## if the unit has no possible retreat, disband it
			options = u.get_possible_retreats().count()
			if options == 0:
				u.delete()
		return info

	def preprocess_orders(self):
		"""
		Deletes unconfirmed orders and logs confirmed ones.
		"""
		## delete all orders sent by players that don't control the unit
		if self.configuration.finances:
			Order.objects.filter(player__game=self).exclude(player=F('unit__player')).delete()
		info = u"The following orders are not confirmed and will be deleted:\n"
		## delete all orders that were not confirmed
		for o in Order.objects.filter(unit__player__game=self, confirmed=False):
			info += u"%s\n" % o
			o.delete()
		info += u"---------------\n"
		## cancel interrupted sieges
		besieging = Unit.objects.filter(player__game=self, besieging=True)
		for u in besieging:
			try:
				Order.objects.get(unit=u, code='B')
			except ObjectDoesNotExist:
				u.besieging = False
				u.save()
		## log the rest of the orders
		for o in Order.objects.filter(player__game=self, confirmed=True):
			if o.code != 'H':
				if signals:
					signals.order_placed.send(sender=o)
			else:
				info += u"%s was ordered to hold\n" % o.unit
		return info
	
	def process_orders(self):
		""" Run a batch of methods in the correct order to process all the orders.
		"""

		info = u"Processing orders in game %s\n" % self.slug
		info += u"------------------------------\n\n"
		info += self.preprocess_orders()
		info += u"\n"
		## resolve =G that are not opposed
		info += self.resolve_auto_garrisons()
		info += u"\n"
		## delete supports from units in conflict areas
		info += self.filter_supports()
		info += u"\n"
		## delete convoys that will be invaded
		info += self.filter_convoys()
		info += u"\n"
		## delete attacks to areas that are not reachable
		info += self.filter_unreachable_attacks()
		info += u"\n"
		## process conflicts
		info += self.resolve_conflicts()
		info += u"\n"
		## resolve sieges
		info += self.resolve_sieges()
		info += u"\n"
		info += self.announce_retreats()
		info += u"--- END ---\n"
		if logging:
			logger.info(info)
		turn_log = TurnLog(game=self, year=self.year,
							season=self.season,
							phase=self.phase,
							log=info)
		turn_log.save()

	def process_retreats(self):
		""" From the saved RetreaOrders, process the retreats. """
		## disband retreating units that didn't receive a retreat order
		forced = Unit.objects.filter(player__game=self).exclude(must_retreat='')
		for f in forced:
			try:
				RetreatOrder.objects.get(unit=f)
			except ObjectDoesNotExist:
				f.delete()
		## disband units with a RetreatOrder without area
		disbands = RetreatOrder.objects.filter(unit__player__game=self, area__isnull=True)
		for d in disbands:
			d.unit.delete()
		retreat_areas = GameArea.objects.filter(game=self, retreatorder__isnull=False).annotate(
												number_of_retreats=Count('retreatorder'))
		for r in retreat_areas:
			if r.number_of_retreats > 1:
				disbands = RetreatOrder.objects.filter(area=r)
				for d in disbands:
					d.unit.delete()
			else:
				order = RetreatOrder.objects.get(area=r)
				unit = order.unit
				unit.retreat(order.area)
				order.delete()
	
	def process_strategic_movements(self):
		repeated = self.gamearea_set.annotate(str_count=Count('strategicorder')).filter(str_count__gt=1)
		orders = StrategicOrder.objects.filter(area__game=self)
		for o in orders:
			if not o.area in repeated:
				o.unit.invade_area(o.area)
		orders.delete()

	def update_controls(self):
		""" Checks which GameAreas have been controlled by a Player and update them.
		"""

		for area in self.gamearea_set.filter(Q(board_area__is_sea=False) |
											Q(board_area__mixed=True)).distinct():
			players = self.player_set.filter(unit__area=area).distinct()
			if len(players) > 2:
				err_msg = "%s units in %s (game %s)" % (len(players),area, self)
				raise exceptions.WrongUnitCount(err_msg)
			elif len(players) == 1 and players[0].user:
				## the area is controlled by a player
				if area.player != players[0]:
					## the player controlling the area changes
					area.player = players[0]
					area.years = 0
					area.save()
					signals.area_controlled.send(sender=area, new_home=False)
				else:
					## the player controlling the area is the same
					area.increase_control_counter()
			elif len(players) == 2: ## 2 units of two different countries
					area.player = None
					area.years = 0
					area.save()
			else: ## 0 units
				if area.player: ## control doesn't change
					area.increase_control_counter()

	##---------------------
	## logging methods
	##---------------------

	def log_event(self, e, **kwargs):
		## TODO: CATCH ERRORS
		#event = e(game=self, year=self.year, season=self.season, phase=self.phase, **kwargs)
		#event.save()
		pass


	##------------------------
	## game ending methods
	##------------------------

	def check_winner(self):
		""" Returns True if at least one player has reached the victory conditions. """
		if self.teams > 1:
			for t in self.team_set.all():
				if t.cities_count >= TEAM_GOAL:
					return t
			return False
		winner_found = False
		## get the players list ordered by cities, exclude assassinated players
		players = list(self.player_set.filter(user__isnull=False, assassinated=False))
		players.sort(cmp=lambda x,y: cmp(x.number_of_cities, y.number_of_cities), reverse=True)
		for p in players:
			if p.number_of_cities >= self.cities_to_win:
				if self.require_home_cities:
					try:
						## find a home city controlled by other player
						GameArea.objects.exclude(player=p).get(game=self,
											#board_area__home__scenario=self.scenario,
											#board_area__home__country=p.country,
											board_area__home__contender=p.contender,
											board_area__home__is_home=True,
											board_area__has_city=True)
					except ObjectDoesNotExist:
						## the player controls all his home cities
						pass
					except MultipleObjectsReturned:
						## at least two home cities are not controlled by the player
						continue
					else:
						## one home city is not controlled by the player
						continue
				if self.extra_conquered_cities > 0:
					## count the not home cities controled by the player
					extra = GameArea.objects.filter(player=p, board_area__has_city=True).exclude(
											#board_area__home__scenario=self.scenario,
											#board_area__home__country=p.country,
											board_area__home__contender=p.contender,
											board_area__home__is_home=True).count()
					if extra < self.extra_conquered_cities:
						continue
				if not winner_found:
					winner_found = p
				else:
					## more than one player meets the victory conditions
					if p.number_of_cities == winner_found.number_of_cities:
						## there is a tie
						return False
		if winner_found:
			return winner_found
		return False

	def assign_team_scores(self):
		teams = list(self.team_set.all())
		teams.sort(cmp=lambda x,y: cmp(x.cities_count, y.cities_count), reverse=True)
		pos = 1
		cities = teams[0].cities_count
		for t in teams:
			count = t.cities_count
			if count < cities:
				pos += 1
				cities = count
			for p in t.player_set.all():
				s = Score(user=p.user, game=self, country=p.contender.country,
					cities=p.number_of_cities, points=0, position=pos,
					ignore_avg=True, team=p.team)
				s.save()

	def assign_scores(self):
		scores = []
		for p in self.player_set.filter(user__isnull=False):
			#s = Score(user=p.user, game=p.game, country=p.country,
			s = Score(user=p.user, game=p.game, country=p.contender.country,
				cities=p.number_of_cities)
			scores.append(s)
		## sort the scores, more cities go first
		scores.sort(cmp=lambda x,y: cmp(x.cities, y.cities), reverse=True)
		#zeros = len(scores) - len(SCORES)
		bonus = SCORES # + [0] * zeros
		i = 0
		seconds = []
		thirds = []
		for s in scores:
			i += 1
			if i == 1:
				## the winner
				s.position = i
				winner = s
				#s.points = s.cities + bonus[0]
				#s.save()
			else:
				if s.cities == scores[i-2].cities:
					## tied with the previous player
					s.position = scores[i-2].position
					#s.points = scores[i-2].points
				else:
					## no tie -> next position
					s.position = i
					#s.points = s.cities + bonus[i-1]
				if s.position == 2:
					seconds.append(s)
				elif s.position == 3:
					thirds.append(s)
		## assign points
		if len(seconds) > 0:
			bonus[1] = bonus[1] / len(seconds)
		if len(thirds) > 0:
			bonus[2] = bonus[2] / len(thirds)
		for s in scores:
			s.points = s.cities
			if s.cities > 0:
				if s == winner:
					s.points += bonus[0]
				elif s in seconds:
					s.points += bonus[1]
				elif s in thirds:
					s.points += bonus[2]
			s.save()
			## add the points to the profile total_score
			profile = s.user.get_profile()
			profile.finished_games += 1
			if s.position == 1:
				profile.victories += 1
			profile.total_score += s.points
			profile.save()
		## assign negative points to overthrown players
		try:
			overthrow_penalty = settings.OVERTHROW_PENALTY
		except:
			overthrow_penalty = -10
		try:
			surrender_penalty = settings.SURRENDER_PENALTY
		except:
			surrender_penalty = -5
		if self.version >= 1:
			overthrows = self.revolution_set.filter(overthrow=True)
			pos = len(scores)
			for o in overthrows:
				if o.voluntary:
					p = surrender_penalty
				else:
					p = overthrow_penalty
				s = Score(user=o.government, game=self, country=o.country,
					points=p, cities=0, position=pos)
				s.save()
				s.user.get_profile().total_score += s.points
				s.user.get_profile().save()
		
	def game_over(self):
		self.phase = PHINACTIVE
		self.finished = datetime.now()
		self.save()
		self.make_map(fow=False)
		if signals:
			signals.game_finished.send(sender=self)
		self.notify_players("game_over", {"game": self})
		self.clean_useless_data()

	def clean_useless_data(self):
		""" In a finished game, delete all the data that is not going to be used
		anymore. """

		self.player_set.all().delete()
		self.gamearea_set.all().delete()
		self.invitation_set.all().delete()
		self.whisper_set.all().delete()
		self.revolution_set.filter(overthrow=False).delete()
		self.gameroute_set.all().delete()
	
	##------------------------
	## notification methods
	##------------------------

	def notify_players(self, label, extra_context={}, on_site=True):
		if notification:
			users = User.objects.filter(player__game=self,
										player__eliminated=False)
			extra_context.update({'STATIC_URL': settings.STATIC_URL, })
			if self.fast:
				notification.send_now(users, label, extra_context, on_site)
			else:
				notification.send(users, label, extra_context, on_site)

class GameCommentManager(models.Manager):
	def public(self):
		return self.get_query_set().filter(is_public=True)

class GameComment(models.Model):
	game = models.ForeignKey(Game, editable=False)
	user = models.ForeignKey(User, editable=False)
	comment = models.TextField(_('comment'))
	after_game = models.BooleanField(_('sent after the game'), default=False, editable=False)
	submit_date = models.DateTimeField(_('submission date'), auto_now_add=True,
		editable=False)
	is_public = models.BooleanField(_('is public'), default=True)

	objects = GameCommentManager()

	class Meta:
		verbose_name = _("Game comment")
		verbose_name_plural = _("Game comments")
		ordering = ['submit_date',]

	def save(self, *args, **kwargs):
		if not self.game.finished is None:
			self.after_game = True
		super(GameComment, self).save(*args, **kwargs)

	def __unicode__(self):
		return self.comment[:50]
		
class LiveGameManager(models.Manager):
	def get_query_set(self):
		return super(LiveGameManager, self).get_query_set().filter(finished__isnull=True, started__isnull=False)

class LiveGame(Game):
	objects = LiveGameManager()
	
	class Meta:
		proxy = True

class ErrorReport(models.Model):
	""" This class defines an error report sent by a player to the staff """
	game = models.ForeignKey(Game)
	user = models.ForeignKey(User)
	description = models.TextField()
	created_on = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = _("error report")
		verbose_name_plural = _("error reports")

	def __unicode__(self):
		return u"Report #%s in game %s" % (self.pk, self.game)

def send_error_report(sender, instance=None, **kwargs):
	if isinstance(instance, ErrorReport):
		subject = u"New error report in '%s'" % instance.game.slug
		message = u"%s reported a new error in the game '%s':\n\n" % (instance.user, instance.game)
		message += unicode(instance.description)
		message += u"\n\nThe user's email is %s\n" % instance.user.email
		mail_admins(subject, message)

models.signals.post_save.connect(send_error_report, sender=ErrorReport)

class GameArea(models.Model):
	""" This class defines the actual game areas where each game is played. """

	game = models.ForeignKey(Game)
	board_area = models.ForeignKey(Area)
	## player is who controls the area, if any
	player = models.ForeignKey('Player', blank=True, null=True)
	## the player whose this area is home
	home_of = models.ForeignKey('Player', blank=True, null=True, related_name="homes")
	## number of years that the area has belong to 'player'
	years = models.PositiveIntegerField(default=0)
	standoff = models.BooleanField(default=False)
	famine = models.BooleanField(default=False)
	storm = models.BooleanField(default=False)
	taxed = models.BooleanField(default=False)

	def abbr(self):
		return self.board_area.code
		#return "%s (%s)" % (self.board_area.code, self.board_area.name)

	def __unicode__(self):
		#return self.board_area.name
		#return "(%(code)s) %(name)s" % {'name': self.board_area.name, 'code': self.board_area.code}
		return unicode(self.board_area)

	def build_possible(self, type):
		return self.board_area.build_possible(type)
	
	def possible_reinforcements(self):
		""" Returns a list of possible unit types for an area. """

		existing_types = []
		result = []
		units = self.unit_set.all()
		for unit in units:
	        	existing_types.append(unit.type)
		if self.build_possible('G') and not "G" in existing_types:
			result.append('G')
		if self.build_possible('F') and not ("A" in existing_types or "F" in existing_types):
			result.append('F')
		if self.build_possible('A') and not ("A" in existing_types or "F" in existing_types):
			result.append('A')
		return result

	def mark_as_standoff(self):
		if signals:
			signals.standoff_happened.send(sender=self)
		else:
			self.game.log_event(StandoffEvent, area=self.board_area)
		self.standoff = True
		self.save()

	def province_is_empty(self):
		return self.unit_set.exclude(type__exact='G').count() == 0

	def get_adjacent_areas(self, include_self=False):
		""" Returns a queryset with all the adjacent GameAreas """
		if include_self:
			cond = Q(board_area__borders=self.board_area, game=self.game) | Q(id=self.id)
		else:
			cond = Q(board_area__borders=self.board_area, game=self.game)
		adj = GameArea.objects.filter(cond).distinct()
		return adj
	
	def has_rebellion(self, player, same=True):
		""" If there is a rebellion in the area, either against the player or
		against any other player, returns the rebellion. """
		try:
			if same:
				reb = Rebellion.objects.get(area=self, player=player)
			else:
				reb = Rebellion.objects.exclude(player=player).get(area=self)
		except ObjectDoesNotExist:
			return False
		return reb

	def check_assassination_rebellion(self, mod=0):
		""" When a player is assassinated this function checks if a new
		rebellion appears in the game area. """
		if not self.player:
			return False
		## if there are units of other players in the area, there is no rebellion
		## this is not too clear in the rules
		if Unit.objects.filter(area=self).exclude(player=self.player).count() > 0:
			return False
		result = False
		if not self.has_rebellion(self.player):
			if self.game.scenario.setting.configuration.religious_war:
				r_player = self.player.contender.country.religion
				r_area = self.board_area.religion
				if r_player and r_area:
					if r_player != r_area:
						mod += 1
						print "modifier is %s" % mod
			die = dice.roll_1d6() - mod
			try:
				Unit.objects.get(area=self, player=self.player)
			except ObjectDoesNotExist:
				occupied = False
			except MultipleObjectsReturned:
				occupied = True
			else:
				occupied = True
			## the province is a home province
			if self in self.player.home_country():
				if occupied and die <= 1:
					result = True
				elif not occupied and die <= 2:
					result = True
			## the province is conquered
			else:
				if occupied and die <= 3:
					result = True
				elif not occupied and die <= 5:
					result = True
			if result:
				rebellion = Rebellion(area=self)
				rebellion.save()
		return result
			
	def tax(self):
		if self.player is None or self.taxed or self.has_rebellion(self.player):
			return 0
		## if there is an enemy unit it cannot be taxed
		try:
			Unit.objects.exclude(player=self.player).get(area=self)
		except ObjectDoesNotExist:
			pass
		except MultipleObjectsReturned:
			return 0
		if self.board_area.control_income <= 1:
			return 0
		self.taxed = True
		ducats = self.board_area.control_income - 1
		self.save()
		logger.info("Player %s taxed %s" % (self.player, self))
		return ducats

	def increase_control_counter(self):
		if self.game.configuration.variable_home and self.years < 2:
			if not self.home_of or (self.home_of and self.home_of != self.player):
				self.years += 1
				if self.years == 2:
					self.home_of = self.player
					signals.area_controlled.send(sender=self, new_home=True)
				self.save()

def check_min_karma(sender, instance=None, **kwargs):
	if isinstance(instance, CondottieriProfile):
		if instance.karma < settings.KARMA_TO_JOIN:		
			players = Player.objects.filter(user=instance.user,
											game__slots__gt=0)
			for p in players:
				game = p.game
				if not game.private:
					p.delete()
					game.slots += 1
					game.save()
	
models.signals.post_save.connect(check_min_karma, sender=CondottieriProfile)


class Score(models.Model):
	""" This class defines the scores that a user got in a finished game. """

	user = models.ForeignKey(User)
	game = models.ForeignKey(Game)
	country = models.ForeignKey(Country)
	points = models.IntegerField(default=0)
	cities = models.PositiveIntegerField(default=0)
	position = models.PositiveIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	""" Ignore this score in averages (victories, points, etc) """
	ignore_avg = models.BooleanField(default=False)
	""" The score was got in a team game """
	team = models.ForeignKey('Team', null=True, blank=True, verbose_name=_("team"))

	def __unicode__(self):
		return "%s (%s)" % (self.user, self.game)

	class Meta:
		verbose_name = _("score")
		verbose_name_plural = _("scores")
		ordering = ["-game", "position"]

class Team(models.Model):
	""" This class defines a group of players that play together """
	game = models.ForeignKey(Game, verbose_name=_("game"))

	class Meta:
		verbose_name = _("team")
		verbose_name_plural = _("teams")
		ordering = ["-game",]

	def __unicode__(self):
		return _("Team %s") % self.pk

	def _get_cities_count(self):
		if self.game.finished is None:
			cities = GameArea.objects.filter(player__team=self, board_area__has_city=True)
			return cities.count()
		else:
			scores = self.score_set.all().aggregate(Sum('cities'))
			return scores['cities__sum']

	cities_count = property(_get_cities_count)

def generate_secret_key():
	min_size = getattr(settings, 'MIN_KEY_SIZE', 6)
	max_size = getattr(settings, 'MAX_KEY_SIZE', 10)
	size = random.randint(min_size, max_size)
	while 1:
		key = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(size))
		try:
			Player.objects.get(secret_key=key)
		except ObjectDoesNotExist:
			return key

class Player(models.Model):
	""" This class defines the relationship between a User and a Game. """

	user = models.ForeignKey(User, blank=True, null=True) # can be null because of autonomous units
	game = models.ForeignKey(Game)
	## country is deprecated and will be deleted. Only used here to ease the migration
	## to condottieri_scenarios. contender is used in its place
	country = models.ForeignKey(Country, blank=True, null=True)
	contender = models.ForeignKey(Contender, blank=True, null=True)
	done = models.BooleanField(default=False)
	eliminated = models.BooleanField(default=False)
	conqueror = models.ForeignKey('self', related_name='conquered', blank=True, null=True)
	excommunicated = models.PositiveIntegerField(blank=True, null=True)
	assassinated = models.BooleanField(default=False)
	defaulted = models.BooleanField(default=False)
	surrendered = models.BooleanField(default=False)
	ducats = models.PositiveIntegerField(default=0)
	double_income = models.BooleanField(default=False)
	may_excommunicate = models.BooleanField(default=False)
	static_name = models.CharField(max_length=20, default="")
	step = models.PositiveIntegerField(default=0)
	""" has_sentenced is True if the player has excommunicated OR forgiven any other player
	this turn; false if not."""
	has_sentenced = models.BooleanField(default=False)
	""" is_excommunicated is True if the player has been excommunicated, either explicitly or
	because of talking to other excommunicated player """
	is_excommunicated = models.BooleanField(default=False)
	""" pope_excommunicated is True if the player has been explicitly excommunicated """
	pope_excommunicated = models.BooleanField(default=False)
	""" the player may belong to a team, in a team game """
	team = models.ForeignKey(Team, null=True, blank=True, verbose_name=_("team"))
	secret_key = models.CharField(_("secret key"), max_length=20, default="", editable=False)

	## the 'deadline' is not persistent, and is used to order a user's players by the time
	## that they have to play
	def __init__(self, *args, **kwargs):
		self.__deadline = None
		super(Player, self,).__init__(*args, **kwargs)

	def save(self, *args, **kwargs):
		if self.id is None:
			self.secret_key = generate_secret_key()
		super(Player, self).save(*args, **kwargs)
	
	def _get_map_filename(self):
		return self.game.get_map_filename(player=self)

	map_filename = property(_get_map_filename)
	
	def _get_deadline(self):
		return self.__deadline
	
	def _set_deadline(self, d):
		self.__deadline = d

	deadline = property(_get_deadline, _set_deadline)

	def __unicode__(self):
		if self.user:
			return u"%s (%s)" % (self.user, self.game)
		else:
			return u"Autonomous in %s" % self.game

	def get_language(self):
		if self.user:
			return self.user.account_set.all()[0].get_language_display()
		else:
			return ''

	def clear_phase_cache(self):
		cache_keys = ["player-%s_log" % self.pk,]
		try:
			cache.delete_many(cache_keys)
		except:
			logger.error("Error while deleting player phase cache")

	def get_setups(self):
		#return self.game.scenario.setup_set.filter(country=self.country).select_related()
		return self.contender.setup_set.select_related()
	
	def home_control_markers(self):
		""" Assigns each GameArea the player as owner. """
		controls = GameArea.objects.filter(game=self.game,
			board_area__home__contender=self.contender)
		controls.update(player=self)
		homes = GameArea.objects.filter(game=self.game,
			board_area__home__contender=self.contender,
			board_area__home__is_home=True)
		homes.update(home_of=self)
	
	def place_initial_units(self):
		for s in self.get_setups():
			try:
				a = GameArea.objects.get(game=self.game, board_area=s.area)
			except:
				print "Error 2: Area not found!"
			else:
				if s.unit_type:
					new_unit = Unit(type=s.unit_type, area=a, player=self, paid=False)
					new_unit.save()
	
	def _get_number_of_cities(self):
		""" Returns the number of cities controlled by the player. """

		cities = GameArea.objects.filter(player=self, board_area__has_city=True)
		return len(cities)

	number_of_cities = property(_get_number_of_cities)

	def number_of_units(self):
		## this funcion is deprecated
		return self.unit_set.all().count()

	def placed_units_count(self):
		return self.unit_set.filter(placed=True).count()

	def strategic_units(self):
		""" Returns a queryset with the Units that are elegible for a strategic movement."""
		return self.unit_set.filter(~Q(type__exact='G') &
									Q(besieging=False) &
									(Q(area__player=self) |
									(Q(type__exact='F') & Q(area__board_area__is_sea=True)))).distinct()
	
	def units_to_place(self):
		""" Return the number of units that the player must place. Negative if
		the player has to remove units.
		"""

		if not self.user:
			return 0
		if self.game.version < 2:
			cities = self.number_of_cities
			if self.game.configuration.famine:
				famines = self.gamearea_set.filter(famine=True, board_area__has_city=True).exclude(unit__type__exact='G').count()
				cities -= famines
			units = len(self.unit_set.filter(placed=True))
			place = cities - units
			slots = len(self.get_areas_for_new_units())
			if place > slots:
				place = slots
			return place
		else:
			## new version
			cities = self.number_of_cities
			famines = self.gamearea_set.filter(famine=True, board_area__has_city=True).exclude(unit__type__exact='G').count()
			units = len(self.unit_set.filter(placed=True))
			if cities <= units:
				place = cities - units ## negative
			else:
				if cities - famines <= units:
					place = 0
				else:
					place = cities - famines - units
			slots = len(self.get_areas_for_new_units())
			if place > slots:
				place = slots
			return place
	
	def home_country(self):
		""" Returns a queryset with Game Areas in home country. """

		#return GameArea.objects.filter(game=self.game,
		#	board_area__home__contender=self.contender,
		#	board_area__home__is_home=True)
		return self.homes.all()

	def controlled_home_country(self):
		""" Returns a queryset with GameAreas in home country controlled by player.
		"""

		return self.home_country().filter(player=self)

	def controlled_home_cities(self):
		""" Returns a queryset with GameAreas in home country, with city, 
		controlled by the player """
		return self.controlled_home_country().filter(board_area__has_city=True)

	def get_areas_for_new_units(self, finances=False):
		""" Returns a queryset with the GameAreas that accept new units. """

		if self.game.configuration.conquering:
			conq_players = self.conquered.all()
			areas = GameArea.objects.filter(Q(player=self) &
										Q(board_area__has_city=True) &
										Q(famine=False) &
										(Q(home_of=self) |
										Q(home_of__in=conq_players)))
		else:
			areas = self.controlled_home_cities().exclude(famine=True)
		excludes = []
		for a in areas:
			if a.board_area.is_fortified and len(a.unit_set.all()) > 1:
				excludes.append(a.id)
			elif not a.board_area.is_fortified and len(a.unit_set.all()) > 0:
				excludes.append(a.id)
		if finances:
			## exclude areas where a unit has not been paid
			for u in self.unit_set.filter(placed=True, paid=False):
				excludes.append(u.area.id)
			## exclude areas with rebellion units
			rebellion_ids = Rebellion.objects.filter(player=self).values_list('area', flat=True)
			excludes += rebellion_ids
		areas = areas.exclude(id__in=excludes)
		return areas

	def visible_areas(self):
		""" Returns the Areas that are controlled or occupied by the player
		or adjacent to them """
		q = Q(gamearea__player=self) | \
			Q(gamearea__unit__player=self) | \
			Q(gamearea__diplomat__player=self) | \
			Q(borders__gamearea__player=self) | \
			Q(borders__gamearea__unit__player=self) | \
			Q(borders__gamearea__diplomat__player=self)
		return Area.objects.filter(q).distinct()

	def cancel_orders(self):
		""" Delete all the player's orders """
		self.order_set.all().delete()
	
	def check_eliminated(self):
		""" Before updating controls, check if the player is eliminated.

		VERSION 1:
		A player will be eliminated, **unless**:
		- He has at least one empty **and** controlled home city, **OR**
		- One of his home cities is occupied **only** by him.
		NEW IN VERSION 2:
		A player will be eliminated, unless he control at least one of his
		home provinces.
		"""

		if not self.user:
			return False
		if self.game.version < 2:
			## find a home city controlled by the player, and empty
			cities = self.controlled_home_cities().filter(unit__isnull=True).count()
			if cities > 0:
				return False
			## find a home city occupied only by the player
			enemies = self.game.player_set.exclude(id=self.id)
			occupied = self.game.gamearea_set.filter(unit__player__in=enemies).distinct().values('id')
			safe = self.home_country().filter(board_area__has_city=True, unit__player=self).exclude(id__in=occupied).count()
			if safe > 0:
				return False
			return True
		else:
			## new version of elimination rule
			## find a home province controlled by the player, and empty
			safe = self.controlled_home_country().filter(unit__isnull=True).count()
			if safe > 0:
				return False
			## find a home province occupied only by the player
			enemies = self.game.player_set.exclude(id=self.id)
			occupied = self.home_country().filter(unit__player__in=enemies).distinct().values('id')
			safe = self.home_country().filter(unit__player=self).exclude(id__in=occupied).count()
			if safe > 0:
				return False
			return True

	def eliminate(self):
		""" Eliminates the player and removes units, controls, etc.

		If excommunication rule is being used, clear excommunications.
		.. Warning::
			This only should be used while there's only one country that can excommunicate.
		"""
		
		if self.user:
			self.eliminated = True
			self.ducats = 0
			self.is_excommunicated = False
			self.pope_excommunicated = False
			self.save()
			signals.country_eliminated.send(sender=self, country=self.contender.country)
			if logging:
				msg = "Game %s: player %s has been eliminated." % (self.game.pk,
															self.pk)
				logger.info(msg)
			for unit in self.unit_set.all():
				unit.delete()
			for area in self.gamearea_set.all():
				area.player = None
				area.save()
			## if the player has active revolutions, clear them
			try:
				rev = Revolution.objects.get(game=self.game, government=self.user, active__isnull=False)
			except:
				pass
			else:
				rev.active = False
				rev.save()
			if self.game.configuration.excommunication:
				if self.may_excommunicate:
					self.game.player_set.all().update(is_excommunicated=False, pope_excommunicated=False)

	def surrender(self):
		self.surrendered = True
		self.done = True
		try:
			rev = Revolution.objects.get(game=self.game, government=self.user)
		except ObjectDoesNotExist:
			rev = Revolution(game=self.game, government=self.user,
				country = self.contender.country)
		rev.active = datetime.now()
		rev.voluntary = True
		rev.save()
		self.save()
		signals.player_surrendered.send(sender=self)

	def set_conqueror(self, player):
		if player != self:
			signals.country_conquered.send(sender=self, country=self.contender.country)
			if logging:
				msg = "Player %s conquered by player %s" % (self.pk, player.pk)
				logger.info(msg)
			self.conqueror = player
			self.save()

	def can_excommunicate(self):
		""" Returns true if player.may_excommunicate and the Player has not excommunicated or
		forgiven anyone this turn and there is no other player explicitly excommunicated """

		if self.eliminated:
			return False
		if self.game.configuration.excommunication:
			if self.may_excommunicate and not self.has_sentenced:
				try:
					Player.objects.get(game=self.game, pope_excommunicated=True)
				except ObjectDoesNotExist:
					return True
		return False

	def can_forgive(self):
		""" Returns true if player.may_excommunicate and the Player has not excommunicated or
		forgiven anyone this turn. """
		
		if self.eliminated:
			return False
		if self.game.configuration.excommunication:
			if self.may_excommunicate and not self.has_sentenced:
				return True
		return False

	def set_excommunication(self, by_pope=False):
		""" Excommunicates the player """
		self.is_excommunicated = True
		self.pope_excommunicated = by_pope
		self.save()
		self.game.reset_players_cache()
		signals.country_excommunicated.send(sender=self)
		if logging:
			msg = "Player %s excommunicated" % self.pk
			logger.info(msg)
		if notification:
			user = [self.user,]
			extra_context = {'game': self.game, 'STATIC_URL': settings.STATIC_URL,}
			notification.send(user, "player_excommunicated", extra_context,
				on_site=True)
	
	def unset_excommunication(self):
		self.is_excommunicated = False
		self.pope_excommunicated = False
		self.save()
		self.game.reset_players_cache()
		signals.country_forgiven.send(sender=self)
		if logging:
			msg = "Player %s is forgiven" % self.pk
			logger.info(msg)
		if notification:
			user = [self.user,]
			extra_context = {'game': self.game, 'STATIC_URL': settings.STATIC_URL,}
			notification.send(user, "player_absolved", extra_context,
				on_site=True)

	def assassinate(self):
		self.assassinated = True
		self.save()
		signals.player_assassinated.send(sender=self)

	def has_special_unit(self):
		try:
			Unit.objects.get(player=self, paid=True, cost__gt=3)
		except ObjectDoesNotExist:
			return False
		except MultipleObjectsReturned:
			return True
		else:
			return True

	def end_phase(self, forced=False):
		self.done = True
		self.step = 0
		self.save()
		if not forced:
			if self.game.uses_karma and self.game.check_bonus_time():
				## get a karma bonus
				self.user.get_profile().adjust_karma(1)
			## close possible revolutions
			self.close_revolution()
			msg = "Player %s ended phase" % self.pk
		else:
			msg = "Player %s forced to end phase" % self.pk
		if logging:
			logger.info(msg)

	def new_phase(self):
		## check that the player is not autonomous and is not eliminated
		if self.user and not self.eliminated and not self.surrendered:
			if self.game.phase == PHREINFORCE and not self.game.configuration.finances:
				if self.units_to_place() == 0:
					self.done = True
				else:
					self.done = False
			elif self.game.phase == PHORDERS:
				self.done = False
			## these lines are disabled so that the player can play expenses
			#	units = self.unit_set.all().count()
			#	if units <= 0:
			#		self.done = True
			#	else:
			#		self.done = False
			elif self.game.phase == PHRETREATS:
				retreats = self.unit_set.exclude(must_retreat__exact='').count()
				if retreats == 0:
					self.done = True
				else:
					self.done = False
			elif self.game.phase == PHSTRATEGIC:
				units = self.unit_set.exclude(type__exact='G').count()
				if units <= 0:
					self.done = True
				else:
					self.done = False
			else:
				self.done = False
			self.save()

	def next_phase_change(self):
		""" Returns the time that the next forced phase change would happen,
		if this were the only player (i.e. only his own karma is considered)
		"""
		
		if not self.game.uses_karma:
			karma = 100.
		else:
			karma = float(self.user.get_profile().karma)
		if karma > 100:
			if self.game.phase == PHORDERS:
				k = 1 + (karma - 100) / 200
			else:
				k = 1
		else:
			k = karma / 100
		time_limit = self.game.time_limit * k
		if self.game.extended_deadline:
			time_limit += self.game.time_limit
		
		duration = timedelta(0, time_limit)

		return self.game.last_phase_change + duration
	
	def time_to_limit(self):
		"""
		Calculates the time to the next phase change and returns it as a
		timedelta.
		"""
		return self.next_phase_change() - datetime.now()
	
	def in_last_seconds(self):
		"""
		Returns True if the next phase change would happen in a few minutes.
		"""
		return self.time_to_limit() <= timedelta(seconds=settings.LAST_SECONDS)
	
	def time_exceeded(self):
		""" Returns true if the player has exceeded his own time, and he is playing because
		other players have not yet finished. """

		return self.next_phase_change() < datetime.now()

	def get_time_status(self):
		""" Returns a string describing the status of the player depending on the time limits.
		This string is to be used as a css class to show the time """
		now = datetime.now()
		bonus = self.game.get_bonus_deadline()
		if now <= bonus:
			return 'bonus_time'
		safe = self.next_phase_change()
		if now <= safe:
			return 'safe_time'
		return 'unsafe_time'

	def check_revolution(self):
		""" If a player doesn't submit his orders, he loses karma points.
		If the game is not private, a new revolution is created, and he can be overthrown. """
		if self.game.uses_karma:
			self.user.get_profile().adjust_karma(-10)
			logger.info("%s lost 10 karma points" % self)
		if not self.game.private:
			created = False
			karma_to_revolution = getattr(settings, KARMA_TO_REVOLUTION, 170)
			if self.user.get_profile().karma < karma_to_revolution:
				revolution, created = Revolution.objects.get_or_create(game=self.game,
					government=self.user, overthrow=False)
				revolution.active = datetime.now()
				if created:
					logger.info("New revolution for player %s" % self)
					if notification:
						user = [self.user,]
						extra_context = {'game': self.game, 'STATIC_URL': settings.STATIC_URL,}
						notification.send(user, "new_revolution", extra_context,
							on_site=True)
				else:
					if revolution.opposition:
						revolution.resolve()
				revolution.save()
			else:
				logger.info("Karma prevents revolution for %s" % self)

	def close_revolution(self):
		""" The player made his actions, and any revolutions are closed """
		try:
			revolution = Revolution.objects.get(game=self.game,
				government=self.user, active__isnull=False)
		except ObjectDoesNotExist:
			return
		else:
			revolution.active = None
			revolution.save()
			logger.info("Revolution closed for player %s" % self)

	def unread_count(self):
		""" Gets the number of unread received letters """
		
		if condottieri_messages:
			return condottieri_messages.models.Letter.objects.filter(recipient_player=self, read_at__isnull=True, recipient_deleted_at__isnull=True).count()
		else:
			return 0
	
	
	##
	## Income calculation
	##
	def get_control_income(self, die, majors_ids, rebellion_ids):
		""" Gets the sum of the control income of all controlled AND empty
		provinces. Note that provinces affected by plague don't genearate
		any income"""
		area_ids = self.gamearea_set.filter(famine=False).exclude(id__in=rebellion_ids).values_list('board_area', flat=True)
		income = Area.objects.filter(id__in = area_ids).aggregate(Sum('control_income'))

		i =  income['control_income__sum']
		if i is None:
			return 0
		
		v = 0
		for a in majors_ids:
			if a in area_ids:
				city = Area.objects.get(id=a)
				v += city.get_random_income(die)
		return income['control_income__sum'] + v

	def get_occupation_income(self):
		""" Gets the sum of the income of all the armies and fleets in not controlled areas """
		units = self.unit_set.exclude(type="G").exclude(area__famine=True)
		units = units.filter(~Q(area__player=self) | Q(area__player__isnull=True))

		i = units.count()
		if i > 0:
			return i
		return 0

	def get_garrisons_income(self, die, majors_ids, rebellion_ids):
		""" Gets the sum of the income of all the non-besieged garrisons in non-controlled areas
		"""
		## get garrisons in non-controlled areas
		cond = ~Q(area__player=self)
		cond |= Q(area__player__isnull=True)
		cond |= (Q(area__player=self, area__famine=True))
		cond |= (Q(area__player=self, area__id__in=rebellion_ids))
		garrisons = self.unit_set.filter(type="G")
		garrisons = garrisons.filter(cond)
		garrisons = garrisons.values_list('area__board_area__id', flat=True)
		if len(garrisons) > 0:
			## get ids of gameareas where garrisons are under siege
			sieges = Unit.objects.filter(player__game=self.game, besieging=True)
			sieges = sieges.values_list('area__board_area__id', flat=True)
			## get the income
			income = Area.objects.filter(id__in=garrisons).exclude(id__in=sieges)
			if income.count() > 0:
				v = 0
				for a in income:
					if a.id in majors_ids:
						v += a.get_random_income(die)
				income = income.aggregate(Sum('garrison_income'))
				return income['garrison_income__sum'] + v
		return 0

	def get_variable_income(self, die):
		""" Gets the variable income for the country """
		setting = self.game.scenario.setting
		v = self.contender.country.get_random_income(setting, die,
			self.double_income)
		## the player gets the variable income of conquered players
		if self.game.configuration.conquering:
			conquered = self.game.player_set.filter(conqueror=self)
			for c in conquered:
				v += c.contender.country.get_random_income(setting, die,
					c.double_income)
		return v

	def get_trade_income(self):
		i = 0
		safe_routes = self.game.gameroute_set.filter(safe=True)
		for r in safe_routes:
			for t in r.traders:
				if t == self:
					i += 1
		return i
			
	def get_income(self, die, majors_ids):
		""" Gets the total income in one turn """
		rebellion_ids = Rebellion.objects.filter(player=self).values_list('area', flat=True)
		income = self.get_control_income(die, majors_ids, rebellion_ids)
		income += self.get_occupation_income()
		income += self.get_garrisons_income(die, majors_ids, rebellion_ids)
		income += self.get_variable_income(die)
		if self.game.scenario.setting.configuration.trade_routes:
			income += self.get_trade_income()
		return income

	def add_ducats(self, d):
		""" Adds d to the ducats field of the player."""
		self.ducats = F('ducats') + d
		self.save()
		signals.income_raised.send(sender=self, ducats=d)
		if logging:
			msg = "Player %s raised %s ducats." % (self.pk, d)
			logger.info(msg)

	def get_credit(self):
		""" Returns the number of ducats that the player can borrow from the bank. """
		if self.defaulted:
			return 0
		if self.game.configuration.unbalanced_loans:
			credit = 25
		else:
			credit = self.gamearea_set.count() + self.unit_set.count()
			if credit > 25:
				credit = 25
		return credit

class TeamMessage(models.Model):
	""" A message that any member of a team can write and read """
	player = models.ForeignKey(Player, verbose_name=_("player"))
	created_at = models.DateTimeField(auto_now_add=True)
	text = models.TextField(_("text"))

	class Meta:
		ordering = ["-created_at" ,]

	def __unicode__(self):
		return "%s" % self.pk

	def as_li(self):
		signature = _("Written by %(country)s %(date)s ago") % {'country': self.player.contender.country,
			'date': timesince(self.created_at),}
		html = u"<li>%(text)s<span class=\"date\">%(signature)s</span> </li>" % {
								'signature': signature,
								'text': force_escape(self.text), }
		return html

def notify_team_message(sender, instance, created, **kw):
	if notification and isinstance(instance, TeamMessage) and created:
		users = User.objects.filter(player__team=instance.player.team).exclude(player=instance.player)
		game = instance.player.game
		extra_context = {'game': game,
						'message': instance,
						'STATIC_URL': settings.STATIC_URL,}
		if game.fast:
			notification.send_now(users, "team_message_received", extra_context)
		else:
			notification.send(users, "team_message_received", extra_context)

models.signals.post_save.connect(notify_team_message, sender=TeamMessage)

class Revolution(models.Model):
	""" A Revolution instance means that ``government`` is not playing, and
	``opposition`` is trying to replace it.
	"""

	game = models.ForeignKey(Game)
	government = models.ForeignKey(User, related_name="revolutions")
	active = models.DateTimeField(null=True, blank=True)
	opposition = models.ForeignKey(User, blank=True, null=True,
		related_name="overthrows")
	overthrow = models.BooleanField(default=False)
	""" Copy of the country """
	country = models.ForeignKey(Country)
	voluntary = models.BooleanField(default=False)

	class Meta:
		verbose_name = _("Revolution")
		verbose_name_plural = _("Revolutions")
		unique_together = [('game', 'government'), ('game', 'opposition')]

	def __unicode__(self):
		return u"%s (%s)" % (self.government, self.game)

	def save(self, *args, **kwargs):
		if self.id is None:
			player = Player.objects.get(game=self.game, user=self.government)
			self.country = player.contender.country
		super(Revolution, self).save(*args, **kwargs)

	def _get_government_player(self):
		return Player.objects.get(game=self.game, user=self.government)

	government_player = property(_get_government_player)

	def _get_opposition_player(self):
		return Player.objects.get(game=self.game, user=self.opposition)

	opposition_player = property(_get_opposition_player)

	def get_country(self):
		try:
			player = Player.objects.get(game=self.game, user=self.government)
		except ObjectDoesNotExist:
			player = Player.objects.get(game=self.game, user=self.opposition)
		return player.contender.country
	
	def resolve(self):
		if notification:
			## notify the old player
			user = [self.government,]
			extra_context = {'game': self.game, 'STATIC_URL': settings.STATIC_URL,}
			notification.send(user, "lost_player", extra_context, on_site=True)
			## notify the new player
			user = [self.opposition]
			if self.game.fast:
				notification.send_now(user, "got_player", extra_context)	
			else:
				notification.send(user, "got_player", extra_context)
			logger.info("Government of %s is overthrown" % self.country)
		if signals:
			signals.government_overthrown.send(sender=self)
		player = Player.objects.get(game=self.game, user=self.government)
		player.user = self.opposition
		if self.voluntary:
			player.surrendered = False
		player.save()
		self.opposition.get_profile().adjust_karma(10)
		self.active = None
		self.overthrow = True
		self.save()

def notify_overthrow_attempt(sender, **kw):
	if notification and isinstance(sender, Revolution):
		user = [sender.government,]
		extra_context = {'game': sender.game,
			'STATIC_URL': settings.STATIC_URL,}
		notification.send(user, "overthrow_attempt", extra_context , on_site=True)

signals.overthrow_attempted.connect(notify_overthrow_attempt)

class UnitManager(models.Manager):
	def get_with_strength(self, game, **kwargs):
		u = self.get_query_set().get(**kwargs)
		query = Q(unit__player__game=game,
				  code__exact='S',
				  subunit=u)
		u_order = u.get_order()
		if not u_order:
			query &= Q(subcode__exact='H')
		else:
			if u_order.code in ('', 'H', 'S', 'C', 'B'): #unit is holding
				query &= Q(subcode__exact='H')
			elif u_order.code == '=':
				query &= Q(subcode__exact='=',
						   subtype=u_order.type)
			elif u_order.code == '-':
				query &= Q(subcode__exact='-',
						   subdestination=u_order.destination)
		#support = Order.objects.filter(query).count()
		support_sum = Order.objects.filter(query).aggregate(Sum('unit__power'))
		if support_sum['unit__power__sum'] is None:
			support = 0
		else:
			support = int(support_sum['unit__power__sum'])
		if game.configuration.finances:
			if not u_order is None and u_order.code == '-':
				if u_order.destination.has_rebellion(u.player, same=False):
					support += 1
		u.strength = u.power + support
		return u

	def list_with_strength(self, game):
		from django.db import connection
		cursor = connection.cursor()
		cursor.execute("SELECT u.id, \
							u.type, \
							u.area_id, \
							u.player_id, \
							u.besieging, \
							u.must_retreat, \
							u.placed, \
							u.paid, \
							u.cost, \
							u.power, \
							u.loyalty, \
							o.code, \
							o.destination_id, \
							o.type \
		FROM (machiavelli_player p INNER JOIN machiavelli_unit u on p.id=u.player_id) \
		LEFT JOIN machiavelli_order o ON u.id=o.unit_id \
		WHERE p.game_id=%s" % game.id)
		result_list = []
		for row in cursor.fetchall():
			support_query = Q(unit__player__game=game,
							  code__exact='S',
							  subunit__pk=row[0])
			if row[11] in (None, '', 'H', 'S', 'C', 'B'): #unit is holding
				support_query &= Q(subcode__exact='H')
			elif row[11] == '=':
				support_query &= Q(subcode__exact='=',
						   		subtype__exact=row[13])
			elif row[11] == '-':
				support_query &= Q(subcode__exact='-',
								subdestination__pk__exact=row[12])
			#support = Order.objects.filter(support_query).count()
			support_sum = Order.objects.filter(support_query).aggregate(Sum('unit__power'))
			if support_sum['unit__power__sum'] is None:
				support = 0
			else:
				support = int(support_sum['unit__power__sum'])
			unit = self.model(id=row[0], type=row[1], area_id=row[2],
							player_id=row[3], besieging=row[4],
							must_retreat=row[5], placed=row[6], paid=row[7],
							cost=row[8], power=row[9], loyalty=row[10])
			if game.configuration.finances:
				if row[11] == '-':
					destination = GameArea.objects.get(id=row[12])
					player = Player.objects.get(id=row[3])
					if destination.has_rebellion(player, same=False):
						support += 1
			unit.strength = unit.power + support
			result_list.append(unit)
		result_list.sort(cmp=lambda x,y: cmp(x.strength, y.strength), reverse=True)
		return result_list

class Unit(models.Model):
	""" This class defines a unit in a game, its location and status. """

	type = models.CharField(max_length=1, choices=UNIT_TYPES)
	area = models.ForeignKey(GameArea)
	player = models.ForeignKey(Player)
	besieging = models.BooleanField(default=0)
	""" must_retreat contains the code, if any, of the area where the attack came from """
	must_retreat = models.CharField(max_length=5, blank=True, default='')
	placed = models.BooleanField(default=True)
	paid = models.BooleanField(default=True)
	""" cost is the cost of the unit if finances are used, usually 3 """
	cost = models.PositiveIntegerField(default=3)
	""" power is the individual strength of the unit, usually 1 """
	power = models.PositiveIntegerField(default=1)
	""" loyalty is a multiplier to calculate the cost of a bribe against the unit """
	loyalty = models.PositiveIntegerField(default=1)
	
	objects = UnitManager()

	def get_order(self):
		""" If the unit has more than one order, raises an error. If not, return the order.
		When this method is called, each unit should have 0 or 1 order """
		try:
			order = Order.objects.get(unit=self)
		except MultipleObjectsReturned:
			raise MultipleObjectsReturned
		except:
			return None
		else:
			return order
	
	def get_attacked_area(self):
		""" If the unit has orders, get the attacked area, if any. This method is
		only a proxy of the Order method with the same name.
		"""
		order = self.get_order()
		if order:
			return order.get_attacked_area()
		else:
			return GameArea.objects.none()

	def supportable_order(self):
		supportable = "%s %s" % (self.type, self.area.board_area.code)
		order = self.get_order()
		if not order:
			supportable += " H"
		else:
			if order.code in ('', 'H', 'S', 'C', 'B'): #unit is holding
				supportable += " H"
			elif order.code == '=':
				supportable += " = %s" % order.type
			elif order.code == '-':
				supportable += " - %s" % order.destination.board_area.code
		return supportable

	def place(self):
		self.placed = True
		self.paid = False ## to be unpaid in the next reinforcement phase
		if signals:
			signals.unit_placed.send(sender=self)
		else:
			#self.player.game.log_event(NewUnitEvent, country=self.player.country,
			self.player.game.log_event(NewUnitEvent, country=self.player.contender.country,
								type=self.type, area=self.area.board_area)
		self.save()

	def delete(self):
		if signals:
			signals.unit_disbanded.send(sender=self)
		else:
			#self.player.game.log_event(DisbandEvent, country=self.player.country,
			self.player.game.log_event(DisbandEvent, country=self.player.contender.country,
								type=self.type, area=self.area.board_area)
		super(Unit, self).delete()
	
	def __unicode__(self):
		return _("%(type)s in %(area)s") % {'type': self.get_type_display(), 'area': self.area}

	def describe_with_cost(self):
		return _("%(type)s in %(area)s (%(cost)s ducats)") % {'type': self.get_type_display(),
														'area': self.area,
														'cost': self.cost,}
    
	def get_possible_retreats(self):
		## possible_retreats includes all adjancent, non-standoff areas, and the
		## same area where the unit is located (convert to garrison)
		cond = Q(game=self.player.game)
		cond = cond & Q(standoff=False)
		cond = cond & Q(board_area__borders=self.area.board_area)
		## exclude the area where the attack came from
		cond = cond & ~Q(board_area__code__exact=self.must_retreat)
		## exclude areas with 'A' or 'F'
		cond = cond & ~Q(unit__type__in=['A','F'])
		## for armies, exclude seas
		if self.type == 'A':
			cond = cond & Q(board_area__is_sea=False)
			cond = cond & ~Q(board_area__mixed=True)
		## for fleets, exclude areas that are adjacent but their coasts are not
		elif self.type == 'F':
			exclude = []
			for area in self.area.board_area.borders.all():
				if not area.is_adjacent(self.area.board_area, fleet=True):
					exclude.append(area.id)
			cond = cond & ~Q(board_area__id__in=exclude)
			## for fleets, exclude areas that are not seas or coasts
			cond = cond & ~Q(board_area__is_sea=False, board_area__is_coast=False)
		## add the own area if there is no garrison
		## and the attack didn't come from the city
		## and there is no rebellion in the city
		if self.area.board_area.is_fortified:
			if self.type == 'A' or (self.type == 'F' and self.area.board_area.has_port):
				if self.must_retreat != self.area.board_area.code:
					try:
						Unit.objects.get(area=self.area, type='G')
					except ObjectDoesNotExist:
						try:
							Rebellion.objects.get(area=self.area, garrisoned=True)
						except ObjectDoesNotExist:
							cond = cond | Q(id__exact=self.area.id)
	
		return GameArea.objects.filter(cond).distinct()

	def invade_area(self, ga):
		if signals:
			signals.unit_moved.send(sender=self, destination=ga)
		else:
			self.player.game.log_event(MovementEvent, type=self.type,
										origin=self.area.board_area,
										destination=ga.board_area)
		self.area = ga
		self.must_retreat = ''
		self.save()
		self.check_rebellion()

	def retreat(self, destination):
		if signals:
			signals.unit_retreated.send(sender=self, destination=destination)
		else:
			self.log_event(MovementEvent, type=self.type,
										origin=self.area.board_area,
										destination=destination.board_area)
		if self.area == destination:
			assert self.area.board_area.is_fortified == True, "trying to retreat to a non-fortified city"
			self.type = 'G'
			self.must_retreat = ''
			self.save()
		else:
			self.must_retreat = ''
			self.area = destination
			self.save()
			self.check_rebellion()

	def convert(self, new_type):
		if signals:
			signals.unit_converted.send(sender=self,
										before=self.type,
										after=new_type)
		else:
			self.player.game.log_event(ConversionEvent, area=self.area.board_area,
										before=self.type,
										after=new_type)
		self.type = new_type
		self.must_retreat = ''
		self.save()
		if new_type != 'G':
			self.check_rebellion()

	def check_rebellion(self):
		## if there is a rebellion against other player, mark it as repressed
		reb = self.area.has_rebellion(self.player, same=False)
		if reb:
			reb.repress()

	def delete_order(self):
		order = self.get_order()
		if order:
			order.delete()
		return True

	def change_player(self, player):
		assert isinstance(player, Player)
		self.player = player
		self.paid = False
		self.save()
		self.check_rebellion()
		if signals:
			signals.unit_changed_country.send(sender=self)

	def to_autonomous(self):
		assert self.type == 'G'
		## find the autonomous player
		try:
			aplayer = Player.objects.get(game=self.player.game, user__isnull=True)
		except ObjectDoesNotExist:
			return
		self.player = aplayer
		self.paid = True
		self.save()
		if signals:
			signals.unit_to_autonomous.send(sender=self)

	def valid_strategic_areas(self):
		game_areas = GameArea.objects.filter(game=self.area.game)
		## land areas with armies or fleets
		occupied_ids = game_areas.filter(unit__type__in=['A','F']).values_list('id', flat=True)
		land_filter = Q(player=self.player) & ~Q(id__in=occupied_ids)
		if self.type == "A":
			sea_filter = Q(board_area__is_sea=True) & Q(unit__type='F') & Q(unit__player=self.player)
		elif self.type == "F":
			land_filter = land_filter & Q(board_area__is_coast=True)
			sea_filter = Q(board_area__is_sea=True) & Q(unit__isnull=True) & Q(board_area__borders__gamearea__player=self.player)

		return game_areas.filter(land_filter | sea_filter).distinct()

	def check_strategic_movement(self, destination):
		""" Returns True if the unit is able to make a strategic movement to the area"""
		if self.type == "G" or self.besieging:
			return False
		if self.type == "A" and (not self.area.player or self.area.player != self.player):
			return False
		if self.type == "A" and destination.board_area.is_sea:
			return False
		if self.type == "F" and not (destination.board_area.is_coast or destination.board_area.is_sea):
			return False
		valid_areas = self.valid_strategic_areas()
		if not destination in valid_areas:
			return False
		##
		## find a valid strategic path
		##
		closed = []
		pending = [self.area, ]
		if len(valid_areas) < 1:
			return False ## there are no valid areas
		while len(pending) > 0:
			for area in pending:
				if area in closed:
					continue
				borders = list(valid_areas.filter(board_area__borders=area.board_area))
				if destination in borders:
					return True ## there is a valid strategic line
				closed.append(area)
				pending.remove(area)
				for b in borders:
					if not b in closed and not b in pending:
						pending.append(b)
				break
		return False ## there is not a valid convoy path

class Order(models.Model):
	""" This class defines an order from a player to a unit. The order will not be
	effective unless it is confirmed.
	"""

	#unit = models.OneToOneField(Unit)
	unit = models.ForeignKey(Unit)
	code = models.CharField(max_length=1, choices=ORDER_CODES)
	destination = models.ForeignKey(GameArea, blank=True, null=True)
	type = models.CharField(max_length=1, blank=True, null=True, choices=UNIT_TYPES)
	## suborder field is deprecated, and will be removed
	suborder = models.CharField(max_length=15, blank=True, null=True)
	subunit = models.ForeignKey(Unit, related_name='affecting_orders', blank=True, null=True)
	subcode = models.CharField(max_length=1, choices=ORDER_SUBCODES, blank=True, null=True)
	subdestination = models.ForeignKey(GameArea, related_name='affecting_orders', blank=True, null=True)
	subtype = models.CharField(max_length=1, blank=True, null=True, choices=UNIT_TYPES)
	confirmed = models.BooleanField(default=False)
	## player field is to be used when a player buys an enemy unit. It can be null for backwards
	## compatibility
	player = models.ForeignKey(Player, null=True)

	class Meta:
		unique_together = (('unit', 'player'),)
	
	def as_dict(self):
		result = {
			'id': self.pk,
			'unit': unicode(self.unit),
			'code': self.get_code_display(),
			'destination': '',
			'type': '',
			'subunit': '',
			'subcode': '',
			'subdestination': '',
			'subtype': ''
		}
		if isinstance(self.destination, GameArea):
			result.update({'destination': unicode(self.destination)})
		if not self.type == None:
			result.update({'type': self.get_type_display()})
		if isinstance(self.subunit, Unit):
			result.update({'subunit': unicode(self.subunit)})
			if not self.subcode == None:
				result.update({'subcode': self.get_subcode_display()})
			if isinstance(self.subdestination, GameArea):
				result.update({'subdestination': unicode(self.subdestination)})
			if not self.subtype == None:
				result.update({'subtype': self.get_subtype_display()})

		return result
	
	def explain(self):
		""" Returns a human readable order.	"""

		if self.code == 'H':
			msg = _("%(unit)s holds its position.") % {'unit': self.unit,}
		elif self.code == '-':
			msg = _("%(unit)s tries to go to %(area)s.") % {
							'unit': self.unit,
							'area': self.destination
							}
		elif self.code == 'B':
			msg = _("%(unit)s besieges the city.") % {'unit': self.unit}
		elif self.code == '=':
			msg = _("%(unit)s tries to convert into %(type)s.") % {
							'unit': self.unit,
							'type': self.get_type_display()
							}
		elif self.code == 'C':
			msg = _("%(unit)s must convoy %(subunit)s to %(area)s.") % {
							'unit': self.unit,
							'subunit': self.subunit,
							'area': self.subdestination
							}
		elif self.code == 'S':
			if self.subcode == 'H':
				msg=_("%(unit)s supports %(subunit)s to hold its position.") % {
							'unit': self.unit,
							'subunit': self.subunit
							}
			elif self.subcode == '-':
				msg = _("%(unit)s supports %(subunit)s to go to %(area)s.") % {
							'unit': self.unit,
							'subunit': self.subunit,
							'area': self.subdestination
							}
			elif self.subcode == '=':
				msg = _("%(unit)s supports %(subunit)s to convert into %(type)s.") % {
							'unit': self.unit,
							'subunit': self.subunit,
							'type': self.get_subtype_display()
							}
		return msg
	
	def confirm(self):
		self.confirmed = True
		self.save()
	
	def format_suborder(self):
		""" Returns a string with the abbreviated code (as in Machiavelli) of
		the suborder.
		"""

		if not self.subunit:
			return ''
		f = "%s %s" % (self.subunit.type, self.subunit.area.board_area.code)
		f += " %s" % self.subcode
		if self.subcode == None and self.subdestination != None:
			f += "- %s" % self.subdestination.board_area.code
		elif self.subcode == '-':
			f += " %s" % self.subdestination.board_area.code
		elif self.subcode == '=':
			f += " %s" % self.subtype
		return f

	def format(self):
		""" Returns a string with the abreviated code (as in Machiavelli) of
		the order.
		"""

		f = "%s %s" % (self.unit.type, self.unit.area.board_area.code)
		f += " %s" % self.code
		if self.code == '-':
			f += " %s" % self.destination.board_area.code
		elif self.code == '=':
			f += " %s" % self.type
		elif self.code == 'S' or self.code == 'C':
			f += " %s" % self.format_suborder()
		return f

	def find_convoy_line(self):
		"""
		Returns True if there is a continuous line of convoy orders from 
		the origin to the destination of the order.
		"""

		closed = []
		pending = [self.unit.area, ]
		destination = self.destination
		convoy_areas = GameArea.objects.filter(
						## in this game
						(Q(game=self.unit.player.game) &
						## being sea areas or Venice
						(Q(board_area__is_sea=True) | Q(board_area__mixed=True)) & 
						## with convoy orders
						Q(unit__order__code__exact='C') &
						## convoying this unit
						Q(unit__order__subunit=self.unit) &
						## convoying to this destination
						Q(unit__order__subdestination=self.destination)) |
						## OR being the destination
						Q(id=self.destination.id))
		if len(convoy_areas) <= 1:
			return False ## there are no units with valid convoy orders
		while len(pending) > 0:
			for area in pending:
				if area in closed:
					continue
				borders = list(convoy_areas.filter(game=self.unit.player.game,
					board_area__borders=area.board_area))
				if destination in borders:
					return True ## there is a valid convoy line
				closed.append(area)
				pending.remove(area)
				for b in borders:
					if not b in closed and not b in pending:
						pending.append(b)
				break
		return False ## there is not a valid convoy path

	def get_enemies(self):
		""" Returns a Queryset with all the units trying to oppose an advance or
		conversion order.
		"""

		if self.code == '-':
			enemies = Unit.objects.filter(Q(player__game=self.unit.player.game),
										## trying to go to the same area
										Q(order__destination=self.destination) |
										## trying to exchange areas
										(Q(area=self.destination) &
										Q(order__destination=self.unit.area)) |
										## trying to convert in the same area
										(Q(type__exact='G') &
										Q(area=self.destination) &
										Q(order__code__exact='=')) |
										## trying to stay in the area
										(Q(type__in=['A','F']) &
										Q(area=self.destination) &
										(Q(order__isnull=True) |
										Q(order__code__in=['B','H','S','C'])))
										).exclude(id=self.unit.id)
		elif self.code == '=':
			enemies = Unit.objects.filter(Q(player__game=self.unit.player.game),
										## trying to go to the same area
										Q(order__destination=self.unit.area) |
										## trying to stay in the area
										(Q(type__in=['A','F']) & 
										Q(area=self.unit.area) &
										(Q(order__isnull=True) |
										Q(order__code__in=['B','H','S','C','='])
										))).exclude(id=self.unit.id)
			
		else:
			enemies = Unit.objects.none()
		return enemies
	
	def get_rivals(self):
		""" Returns a Queryset with all the units trying to enter the same
		province as the unit that gave this order.
		"""

		if self.code == '-':
			rivals = Unit.objects.filter(Q(player__game=self.unit.player.game),
										## trying to go to the same area
										Q(order__destination=self.destination) |
										## trying to convert in the same area
										(Q(type__exact='G') &
										Q(area=self.destination) &
										Q(order__code__exact='='))
										).exclude(id=self.unit.id)
		elif self.code == '=':
			rivals = Unit.objects.filter(Q(player__game=self.unit.player.game),
										## trying to go to the same area
										Q(order__destination=self.unit.area)
										).exclude(id=self.unit.id)
			
		else:
			rivals = Unit.objects.none()
		return rivals
	
	def get_defender(self):
		""" Returns a Unit trying to stay in the destination area of this order, or
		None.
		"""

		try:
			if self.code == '-':
				defender = Unit.objects.get(Q(player__game=self.unit.player.game),
										## trying to exchange areas
										(Q(area=self.destination) &
										Q(order__destination=self.unit.area)) |
										## trying to stay in the area
										(Q(type__in=['A','F']) &
										Q(area=self.destination) &
										(Q(order__isnull=True) |
										Q(order__code__in=['B','H','S','C'])))
										)
			elif self.code == '=':
				defender = Unit.objects.get(Q(player__game=self.unit.player.game),
										## trying to stay in the area
										(Q(type__in=['A','F']) & 
										Q(area=self.unit.area) &
										(Q(order__isnull=True) |
										Q(order__code__in=['B','H','S','C','='])
										)))
			else:
				defender = Unit.objects.none()
		except ObjectDoesNotExist:
			defender = Unit.objects.none()
		return defender
	
	def get_attacked_area(self):
		""" Returns the game area being attacked by this order. """

		if self.code == '-':
			return self.destination
		elif self.code == '=':
			return self.unit.area
		else:
			return GameArea.objects.none()
	
	def is_possible(self):
		"""
		Checks if an Order is possible as stated in the rules.
		"""
	
		if self.code == 'H':
			return True
		elif self.code == '-':
			## only A and F can advance
			if self.unit.type == 'A':
				## it only can advance to adjacent or coastal provinces (with convoy)
				## it cannot go to Venice or seas
				if self.destination.board_area.is_sea or self.destination.board_area.mixed:
					return False
				if self.unit.area.board_area.is_coast and self.destination.board_area.is_coast:
					return True
				if self.unit.area.board_area.is_adjacent(self.destination.board_area):
					return True
			elif self.unit.type == 'F':
				## it only can go to adjacent seas or coastal provinces
				if self.destination.board_area.is_sea or self.destination.board_area.is_coast:
					if self.unit.area.board_area.is_adjacent(self.destination.board_area, fleet=True):
						return True
		elif self.code == 'B':
			## only fortified cities can be besieged
			if self.unit.area.board_area.is_fortified:
				## only As and Fs in ports can besiege
				if self.unit.type == 'A' or (self.unit.type == 'F' and self.unit.area.board_area.has_port):
					## is there an enemy Garrison in the city
					try:
						gar = Unit.objects.get(type='G', area=self.unit.area)
					except:
						reb = self.unit.area.has_rebellion(self.unit.player, same=True)
						if reb and reb.garrisoned:
							return True
						else:
							return False
					else:
						if gar.player != self.unit.player:
							return True
		elif self.code == '=':
			if self.unit.area.board_area.is_fortified:
				if self.unit.type == 'G':
					if self.type == 'A' and not self.unit.area.board_area.is_sea and not self.unit.area.board_area.mixed:
						return True
					if self.type == 'F' and self.unit.area.board_area.has_port:
						return True
				if self.type == 'G':
					try:
						## if there is already a garrison, the unit cannot be converted
						gar = Unit.objects.get(type='G', area=self.unit.area)
					except:
						if self.unit.type == 'A':
							return True
						if self.unit.type == 'F' and self.unit.area.board_area.has_port:
							return True
		elif self.code == 'C':
			if self.unit.type == 'F':
				if self.subunit.type == 'A':
					if self.unit.area.board_area.is_sea or self.unit.area.board_area.mixed:
						return True
		elif self.code == 'S':
			if self.subunit.type == 'G' and self.subcode != '=':
				return False
			if self.unit.type == 'G':
				if self.subcode == '-' and self.subdestination == self.unit.area:
					return True
				if self.subcode == 'H' and self.subunit.area == self.unit.area:
					return True
			elif self.unit.type == 'F':
				if self.subcode == '-':
					sup_area = self.subdestination.board_area
				elif self.subcode in ('H', 'B', '='):
					sup_area = self.subunit.area.board_area
				if sup_area.is_sea or sup_area.is_coast:
					if sup_area.is_adjacent(self.unit.area.board_area, fleet=True):
						return True
			elif self.unit.type == 'A':
				if self.subcode == '-':
					sup_area = self.subdestination.board_area
				elif self.subcode in ('H', 'B', '='):
					sup_area = self.subunit.area.board_area
				if not sup_area.is_sea and sup_area.is_adjacent(self.unit.area.board_area):
					return True
		return False

	def __unicode__(self):
		return self.format()

class RetreatOrder(models.Model):
	""" Defines the area where the unit must try to retreat. If ``area`` is
	blank, the unit will be disbanded.
	"""

	unit = models.ForeignKey(Unit)
	area = models.ForeignKey(GameArea, null=True, blank=True)

	def __unicode__(self):
		return "%s" % self.unit

class StrategicOrder(models.Model):
	""" Defines the area where the unit will try to go with a strategic movement.
	"""
	unit = models.ForeignKey(Unit)
	area = models.ForeignKey(GameArea)

	def __unicode__(self):
		return _("%(unit)s moves to %(area)s") % {'unit': self.unit,
			'area': self.area.board_area.name}

class TurnLog(models.Model):
	""" A TurnLog is text describing the processing of the method
	``Game.process_orders()``.
	"""

	game = models.ForeignKey(Game)
	year = models.PositiveIntegerField()
	season = models.PositiveIntegerField(choices=SEASONS)
	phase = models.PositiveIntegerField(choices=GAME_PHASES)
	timestamp = models.DateTimeField(auto_now_add=True)
	log = models.TextField()

	class Meta:
		ordering = ['-timestamp',]

	def __unicode__(self):
		return self.log

PRESS_TYPES = (
	(0, _("Normal (private letters, anonymous gossip)")),
	(1, _("Gunboat diplomacy (no letters, no gossip)")),
	#(2, _("Public press (no letters, public messages)")),
)

class Configuration(models.Model):
	""" Defines the configuration options for each game. 
	
	At the moment, only some of them are actually implemented.
	"""

	game = models.OneToOneField(Game, verbose_name=_('game'), editable=False)
	finances = models.BooleanField(_('finances'), default=False)
	assassinations = models.BooleanField(_('assassinations'), default=False,
					help_text=_('will enable Finances'))
	excommunication = models.BooleanField(_('excommunication'), default=False)
	special_units = models.BooleanField(_('special units'), default=False,
					help_text=_('will enable Finances'))
	lenders = models.BooleanField(_('money lenders'), default=False,
					help_text=_('will enable Finances'))
	unbalanced_loans = models.BooleanField(_('unbalanced loans'), default=False,
		help_text=_('the credit for all players will be 25d'))
	conquering = models.BooleanField(_('conquering'), default=False)
	famine = models.BooleanField(_('famine'), default=False)
	plague = models.BooleanField(_('plague'), default=False)
	storms = models.BooleanField(_('storms'), default=False)
	strategic = models.BooleanField(_('strategic movement'), default=False)
	variable_home = models.BooleanField(_('variable home country'), default=False, help_text=_('conquering will be disabled'))
	taxation = models.BooleanField(_('taxation'), default=False,
					help_text=_('will enable Finances and Famine'))
	fow = models.BooleanField(_('fog of war'), default=False,
		help_text=_('each player sees only what happens near his borders'))
	press = models.PositiveIntegerField(_('press'), choices=PRESS_TYPES, default=0)

	def __unicode__(self):
		return unicode(self.game)

	def get_enabled_rules(self):
		rules = []
		for f in self._meta.fields:
			if isinstance(f, models.BooleanField):
				if f.value_from_object(self):
					rules.append(unicode(f.verbose_name))
		return rules

	def _get_gossip(self):
		if self.press in (0, 2):
			return True
		return False

	gossip = property(_get_gossip)

	def _get_letters(self):
		return self.press == 0

	letters = property(_get_letters)

	def _get_public_gossip(self):
		return self.press == 2

	public_gossip = property(_get_public_gossip)
	
def create_configuration(sender, instance, created, **kwargs):
    if isinstance(instance, Game) and created:
		config = Configuration(game=instance)
		config.save()

models.signals.post_save.connect(create_configuration, sender=Game)

###
### EXPENSES
###

EXPENSE_TYPES = (
	(0, _("Famine relief")),
	(1, _("Pacify rebellion")),
	(2, _("Conquered province to rebel")),
	(3, _("Home province to rebel")),
	(4, _("Counter bribe")),
	(5, _("Disband autonomous garrison")),
	(6, _("Buy autonomous garrison")),
	(7, _("Convert garrison unit")),
	(8, _("Disband enemy unit")),
	(9, _("Buy enemy unit")),
	(10, _("Hire a diplomat in own area")),
	(11, _("Hire a diplomat in foreign area")),
)

EXPENSE_COST = {
	0: 3,
	1: 12,
	2: 9,
	3: 15,
	4: 3,
	5: 6,
	6: 9,
	7: 9,
	8: 12,
	9: 18,
	10: 1,
	11: 3,
}

def get_expense_cost(type, unit=None, area=None):
	assert type in EXPENSE_COST.keys()
	k = 1
	if type in (5, 6, 7, 8, 9):
		assert isinstance(unit, Unit)
		## if the unit is in a major city
		if unit.type == 'G' and unit.area.board_area.garrison_income > 1:
			k = 2
		return k * unit.loyalty * EXPENSE_COST[type]
	elif type in (2, 3):
		assert isinstance(area, GameArea)
		if area.game.scenario.setting.configuration.religious_war:
			r_player = area.player.contender.country.religion
			r_area = area.board_area.religion
			if r_player and r_area:
				if r_player != r_area:
					return (k * EXPENSE_COST[type]) - 3
	return k * EXPENSE_COST[type]

class Expense(models.Model):
	""" A player may expend unit to affect some units or areas in the game. """
	player = models.ForeignKey(Player)
	ducats = models.PositiveIntegerField(default=0)
	type = models.PositiveIntegerField(choices=EXPENSE_TYPES)
	area = models.ForeignKey(GameArea, null=True, blank=True)
	unit = models.ForeignKey(Unit, null=True, blank=True)
	confirmed = models.BooleanField(default=False)

	def save(self, *args, **kwargs):
		## expenses that need an area
		if self.type in (0, 1, 2, 3, 10, 11):
			assert isinstance(self.area, GameArea), "Expense needs a GameArea"
		## expenses that need a unit
		elif self.type in (4, 5, 6, 7, 8, 9):
			assert isinstance(self.unit, Unit), "Expense needs a Unit"
		else:
			raise ValueError, "Wrong expense type %s" % self.type
		## if no errors raised, save the expense
		super(Expense, self).save(*args, **kwargs)
		if logging:
			msg = "New expense in game %s: %s" % (self.player.game.id,
													self)
			logger.info(msg)
	
	def __unicode__(self):
		data = {
			#'country': self.player.country,
			'country': self.player.contender.country,
			'area': self.area,
			'unit': self.unit,
		}
		messages = {
			0: _("%(country)s reliefs famine in %(area)s"),
			1: _("%(country)s pacifies rebellion in %(area)s"),
			2: _("%(country)s promotes a rebellion in %(area)s"),
			3: _("%(country)s promotes a rebellion in %(area)s"),
			4: _("%(country)s tries to counter bribe on %(unit)s"),
			5: _("%(country)s tries to disband %(unit)s"),
			6: _("%(country)s tries to buy %(unit)s"),
			7: _("%(country)s tries to turn %(unit)s into an autonomous garrison"),
			8: _("%(country)s tries to disband %(unit)s"),
			9: _("%(country)s tries to buy %(unit)s"),
			10: _("%(country)s hires a diplomat in %(area)s"),
			11: _("%(country)s hires a diplomat in %(area)s"),
		}

		if self.type in messages.keys():
			return messages[self.type] % data
		else:
			return "Unknown expense"
	
	def is_bribe(self):
		return self.type in (5, 6, 7, 8, 9)

	def is_allowed(self):
		""" Return true if it's not a bribe or the unit is in a valid area as
		stated in the rules. """
		if self.type in (0, 1, 2, 3, 4, 10, 11):
			return True
		elif self.is_bribe():
			## self.unit must be adjacent to a unit or area of self.player
			## then, find the borders of self.unit
			adjacent = self.unit.area.get_adjacent_areas()

	def undo(self):
		""" Deletes the expense and returns the money to the player """
		if self.type in (6, 9):
			## trying to buy a unit
			try:
				order = Order.objects.get(player=self.player, unit=self.unit)
			except ObjectDoesNotExist:
				pass
			else:
				order.delete()
		self.player.ducats += self.ducats
		self.player.save()
		if logging:
			msg = "Deleting expense in game %s: %s." % (self.player.game.id,
													self)
			logger.info(msg)
		self.delete()

class Rebellion(models.Model):
	"""
	A Rebellion may be placed in a GameArea if finances rules are applied.
	Rebellion.player is the player who controlled the GameArea when the
	Rebellion was placed. Rebellion.garrisoned is True if the Rebellion is
	in a garrisoned city.
	"""
	area = models.ForeignKey(GameArea, unique=True)
	player = models.ForeignKey(Player)
	garrisoned = models.BooleanField(default=False)
	"""
	A rebellion marked as repressed will be deleted at the end of the season
	"""
	repressed = models.BooleanField(default=False)

	def __unicode__(self):
		return "Rebellion in %(area)s against %(player)s" % {'area': self.area,
														'player': self.player}
	
	def save(self, *args, **kwargs):
		if self.id is None:
			## area must be controlled by a player, who is assigned to the rebellion
			try:
				self.player = self.area.player
			except:
				return False
			## a rebellion cannot be placed in a sea area
			if self.area.board_area.is_sea:
				return False
			## check if the rebellion is to be garrisoned
			if self.area.board_area.is_fortified:
				try:
					Unit.objects.get(area=self.area, type='G')
				except ObjectDoesNotExist:
					self.garrisoned = True
				else:
					## there is a garrison in the city
					if self.area.board_area.mixed:
						## there cannot be a rebellion in Venice sea area
						return False
			if signals:
				signals.rebellion_started.send(sender=self.area)
		super(Rebellion, self).save(*args, **kwargs)

	def repress(self):
		self.repressed = True
		self.save()
	
class Loan(models.Model):
	""" A Loan describes a quantity of money that a player borrows from the bank, with a term """
	player = models.OneToOneField(Player)
	debt = models.PositiveIntegerField(default=0)
	season = models.PositiveIntegerField(choices=SEASONS)
	year = models.PositiveIntegerField(default=0)

	def __unicode__(self):
		return "%(player)s ows %(debt)s ducats" % {'player': self.player, 'debt': self.debt, }

class Assassin(models.Model):
	""" An Assassin represents a counter that a Player owns, to murder the leader of a country """
	owner = models.ForeignKey(Player)
	target = models.ForeignKey(Country)

	def __unicode__(self):
		return "%(owner)s may assassinate %(target)s" % {'owner': self.owner, 'target': self.target, }

class Assassination(models.Model):
	""" An Assassination describes an attempt made by a Player to murder the leader of another
	Country, spending some Ducats """
	killer = models.ForeignKey(Player, related_name="assassination_attempts")
	target = models.ForeignKey(Player, related_name="assassination_targets")
	ducats = models.PositiveIntegerField(default=0)

	def __unicode__(self):
		return "%(killer)s tries to kill %(target)s" % {'killer': self.killer, 'target': self.target, }

	def explain(self):
		return _("%(ducats)sd to kill the leader of %(country)s.") % {'ducats': self.ducats,
																	#'country': self.target.country}
																	'country': self.target.contender.country}

	def get_dice(self):
		costs = [10, 18, 25, 31, 36, 40, 43, 46, 48, 50]
		if not self.ducats in costs:
			return 0
		else:
			return costs.index(self.ducats) + 1

class Whisper(models.Model):
	""" A whisper is an _anonymous_ message that is shown in the game screen. """
	created_at = models.DateTimeField(auto_now_add=True)
	user = models.ForeignKey(User)
	as_admin = models.BooleanField(default=False)
	game = models.ForeignKey(Game)
	text = models.CharField(max_length=140,
		help_text=_("limit of 140 characters"))
	order = models.PositiveIntegerField(editable=False, default=0)

	class Meta:
		ordering = ["-created_at" ,]
		unique_together = (("game", "order"),)

	def __unicode__(self):
		return self.text

	def as_li(self):
		if self.as_admin:
			li = u"<li class=\"admin\">"
		else:
			li = u"<li>"
		html = u"%(li)s<strong>#%(order)s</strong>&nbsp;&nbsp;%(text)s<span class=\"date\">%(date)s</span> </li>" % {
								'order': self.order,
								'li': li,
								'date': timesince(self.created_at),
								'text': force_escape(self.text), }
		return html

def whisper_order(sender, instance, **kw):
	""" Checks if a whisper has already an 'order' value and, if not, calculate
	and assign one """
	if instance.order is None or instance.order == 0:
		whispers = Whisper.objects.filter(game=instance.game).order_by("-order")
		try:
			last = whispers[0].order
			instance.order = last + 1
		except IndexError:
			instance.order = 1

models.signals.pre_save.connect(whisper_order, sender=Whisper)

class Invitation(models.Model):
	""" A private game accepts only users that have been invited by the creator
	of the game. """
	game = models.ForeignKey(Game)
	user = models.ForeignKey(User)
	message = models.TextField(default="", blank=True)

	class Meta:
		unique_together = (('game', 'user'),)

	def __unicode__(self):
		return "%s" % self.user

def notify_new_invitation(sender, instance, created, **kw):
	if notification and isinstance(instance, Invitation) and created:
		user = [instance.user,]
		extra_context = {'game': instance.game,
						'invitation': instance,
						'STATIC_URL': settings.STATIC_URL, }
		notification.send(user, "new_invitation", extra_context , on_site=True)

models.signals.post_save.connect(notify_new_invitation, sender=Invitation)

class Journal(models.Model):
	user = models.ForeignKey(User)
	game = models.ForeignKey(Game)
	content = models.TextField(default="", blank=True)

	class Meta:
		unique_together = (('user', 'game'),)

	def __unicode__(self):
		return u"%s in %s" % (self.user, self.game)

	def _get_excerpt(self):
		return self.content.split("%%")[0]
	
	excerpt = property(_get_excerpt)

class GameRoute(models.Model):
	game = models.ForeignKey(Game)
	trade_route = models.ForeignKey(TradeRoute)
	safe = models.BooleanField(default=True)

	class Meta:
		unique_together = (('game', 'trade_route'),)

	def __unicode__(self):
		return unicode(self.trade_route)
	
	def _get_traders(self):
		""" gets the two players who control the trade route ends. The same player can be
		returned twice """

		return Player.objects.filter(gamearea__board_area__routestep__is_end=True,
			gamearea__board_area__routestep__route=self.trade_route)
	
	traders = property(_get_traders)

	def update_status(self):
		trader_ids = self.traders.values_list('id', flat=True)
		enemies = Unit.objects.filter(player__game=self.game, player__user__isnull=False).exclude(player__id__in=trader_ids).filter(area__board_area__routestep__route=self.trade_route).count()
		if enemies > 0:
			self.safe = False
		else:
			self.safe = True
		self.save()

class Diplomat(models.Model):
	player = models.ForeignKey(Player)
	area = models.ForeignKey(GameArea)

	class Meta:
		unique_together = (('player', 'area'),)
		verbose_name = _("diplomat")
		verbose_name_plural = _("diplomats")

	def __unicode__(self):
		return _("%(country)s's diplomat in %(area)s") % {
			'country': self.player.contender.country,
			'area': self.area}

	def save(self, *args, **kwargs):
		logger.info("Saving diplomat in %s" % self.area)
		if self.area.board_area.is_sea:
			return
		super(Diplomat, self).save(*args, **kwargs)

	def uncover(self):
		d = random.choice(range(1, 7))
		if self.area.player == self.player:
			return False
		if not self.area.player:
			if d in (3, 4, 5, 6):
				return False
		elif self.area.player != self.player:
			if d in (4, 5, 6):
				return False
		## the diplomat is uncovered
		signals.diplomat_uncovered.send(sender=self)
		self.delete()
		return True
