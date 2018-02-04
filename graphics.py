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

""" This module defines functions to generate the map. """

from PIL import Image
import os
import os.path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger(__name__)

import models as machiavelli
from machiavelli.exceptions import GraphicsError

TOKENS_DIR=os.path.join(settings.MEDIA_ROOT, settings.SCENARIOS_ROOT, 'tokens')

def ensure_dir(f):
	d = os.path.dirname(f)
	if not os.path.exists(d):
		os.makedirs(d)

LOYAL_A = Image.open("%s/loyal-army.png" % TOKENS_DIR)
LOYAL_F = Image.open("%s/loyal-fleet.png" % TOKENS_DIR)
LOYAL_G = Image.open("%s/loyal-garrison.png" % TOKENS_DIR)
ELITE_A = Image.open("%s/elite-army.png" % TOKENS_DIR)
ELITE_F = Image.open("%s/elite-fleet.png" % TOKENS_DIR)
ELITE_G = Image.open("%s/elite-garrison.png" % TOKENS_DIR)
DIPLOMAT = Image.open("%s/diplomat-icon.png" % TOKENS_DIR)

def load_unit_tokens(game):
	tokens = dict()
	for player in game.player_set.filter(user__isnull=False):
		t = dict()
		name = player.static_name
		try:
			t.update({'A': Image.open("%s/A-%s.png" % (TOKENS_DIR, name))})
			t.update({'F': Image.open("%s/F-%s.png" % (TOKENS_DIR, name))})
			t.update({'G': Image.open("%s/G-%s.png" % (TOKENS_DIR, name))})
		except IOError:
			logger.error("Missing unit token for %s" % name)
			raise GraphicsError
		tokens.update({name: t })
	try:
		tokens.update({'autonomous': {'G': Image.open("%s/G-autonomous.png" % TOKENS_DIR)}})
	except IOError:
		logger.error("Missing autonomous garrison token")
		raise GraphicsError
	return tokens


def paste_units(board, game, watcher=None):
	tokens = load_unit_tokens(game)
	if isinstance(watcher, machiavelli.Player):
		visible = watcher.visible_areas()
		print "Making secret map for %s" % watcher.static_name
	afs = machiavelli.Unit.objects.filter(type__in=('A','F'), player__game=game, placed=True)
	gars = machiavelli.Unit.objects.filter(type__exact='G', player__game=game, placed=True)
	dips = None
	if isinstance(watcher, machiavelli.Player):
		afs = afs.filter(area__board_area__in=visible)
		gars = gars.filter(area__board_area__in=visible)
		dips = watcher.diplomat_set.all()
	## paste Armies and Fleets
	for unit in afs:
			t = tokens[unit.player.static_name][unit.type]
			if unit.besieging:
				try:
					coords = (unit.area.board_area.gtoken.x, unit.area.board_area.gtoken.y)
				except ObjectDoesNotExist:
					logger.error("GToken object not found for area %s" % unit.area.board_area.code)
					raise GraphicsError
			else:
				try:
					coords = (unit.area.board_area.aftoken.x, unit.area.board_area.aftoken.y)
				except ObjectDoesNotExist:
					logger.error("AFToken object not found for area %s" % unit.area.board_area.code)
					raise GraphicsError
				if unit.must_retreat != '':
					coords = (coords[0] + 15, coords[1] + 15)
			if unit.type == 'A':
				board.paste(t, coords, t)
				if unit.power > 1:
					board.paste(ELITE_A, coords, ELITE_A)
				if unit.loyalty > 1:
					board.paste(LOYAL_A, coords, LOYAL_A)
			elif unit.type == 'F':
				board.paste(t, coords, t)
				if unit.power > 1:
					board.paste(ELITE_F, coords, ELITE_F)
				if unit.loyalty > 1:
					board.paste(LOYAL_F, coords, LOYAL_F)
			else:
				pass
	## paste Garrisons
	for unit in gars:
		if unit.player.user:
			t = tokens[unit.player.static_name]['G']
		else:
			t = tokens['autonomous']['G']
		try:
			coords = (unit.area.board_area.gtoken.x, unit.area.board_area.gtoken.y)
		except ObjectDoesNotExist:
			logger.error("GToken not found for area %s" % unit.area.board_area.code)
			raise GraphicsError
		board.paste(t, coords, t)
		if unit.power > 1:
			board.paste(ELITE_G, coords, ELITE_G)
		if unit.loyalty > 1:
			board.paste(LOYAL_G, coords, LOYAL_G)
	## paste diplomat icons
	if dips:
		for d in dips:
			try:
				coords = (d.area.board_area.controltoken.x - 24, d.area.board_area.controltoken.y - 4)
			except ObjectDoesNotExist:
				logger.error("ControlToken not found for %s" % d.area.board_area.code)
				raise GraphicsError
			board.paste(DIPLOMAT, coords, DIPLOMAT)
	
def make_map(game, fow=False):
	""" Opens the base map and add flags, control markers, unit tokens and other tokens. Then saves
	the map with an appropriate name in the maps directory.
	If fow == True, makes one map for every player and doesn't make a thumbnail
	"""
	if game.finished:
		fow = False
	try:
		base_map = Image.open(game.scenario.setting.board)
	except IOError:
		logger.error("Base map not found for scenario %s" % game.scenario.slug)
		raise GraphicsError
	## if there are disabled areas, mark them
	try:
		marker = Image.open("%s/disabled.png" % TOKENS_DIR)
	except IOError:
		logger.error("Disabled token not found")
		raise GraphicsError
	for a in game.get_disabled_areas():
		try:
			base_map.paste(marker, (a.aftoken.x, a.aftoken.y), marker)
		except ObjectDoesNotExist:
			logger.error("AFToken not found for area %s" % a.code)
			raise GraphicsError
	## mark special city incomes
	try:
		marker = Image.open("%s/chest.png" % TOKENS_DIR)
	except IOError:
		logger.error("Chest token not found")
		raise GraphicsError
	for i in game.scenario.cityincome_set.all():
		try:
			base_map.paste(marker, (i.city.gtoken.x + 32, i.city.gtoken.y), marker)
		except ObjectDoesNotExist:
			logger.error("GToken not found for area %s" % i.city.code)
			raise GraphicsError
	##
	for player in game.player_set.filter(user__isnull=False):
		## paste control markers
		controls = player.gamearea_set.all()
		try:
			marker = Image.open("%s/control-%s.png" % (TOKENS_DIR, player.static_name))
		except IOError:
			logger.error("Control token not found for player %s" % player.static_name)
			raise GraphicsError
		for area in controls:
			try:
				base_map.paste(marker, (area.board_area.controltoken.x, area.board_area.controltoken.y), marker)
			except ObjectDoesNotExist:
				logger.error("ControlToken object not found for area %s" % area.board_area.code)
				raise GraphicsError
		## paste flags
		home = player.home_country()
		try:
			flag = Image.open("%s/flag-%s.png" % (TOKENS_DIR, player.static_name))
		except IOError:
			logger.error("Flag token not found for player %s" % player.static_name)
			raise GraphicsError
		for game_area in home:
			area = game_area.board_area
			try:
				base_map.paste(flag, (area.controltoken.x, area.controltoken.y - 10), flag)
			except ObjectDoesNotExist:
				logger.error("ControlToken object not found for area %s" % area.board_area.code)
				raise GraphicsError
	## paste famine markers
	if game.configuration.famine:
		try:
			famine = Image.open("%s/famine-marker.png" % TOKENS_DIR)
		except IOError:
			logger.error("Famine token not found")
			raise GraphicsError
		for a in game.gamearea_set.filter(famine=True):
			try:
				coords = (a.board_area.controltoken.x + 12, a.board_area.controltoken.y + 12)
			except ObjectDoesNotExist:
				logger.error("ControlToken object not found for area %s" % a.board_area.code)
				raise GraphicsError
			base_map.paste(famine, coords, famine)
	## paste storm markers
	if game.configuration.storms:
		try:
			storm = Image.open("%s/storm-marker.png" % TOKENS_DIR)
		except IOError:
			logger.error("Storm token not found")
			raise GraphicsError
		for a in game.gamearea_set.filter(storm=True):
			try:
				coords = (a.board_area.aftoken.x - 20, a.board_area.aftoken.y + 30)
			except ObjectDoesNotExist:
				logger.error("AFToken object not found for area %s" % a.board_area.code)
				raise GraphicsError
			base_map.paste(storm, coords, storm)
	## paste rebellion markers
	if game.configuration.finances:
		try:
			rebellion_marker = Image.open("%s/rebellion-marker.png" % TOKENS_DIR)
		except IOError:
			logger.error("Rebellion token not found")
			raise GraphicsError
		for r in game.get_rebellions():
			try:
				if r.garrisoned:
					coords = (r.area.board_area.gtoken.x, r.area.board_area.gtoken.y)
				else:
					coords = (r.area.board_area.controltoken.x - 12, r.area.board_area.controltoken.y - 12)
			except ObjectDoesNotExist:
				logger.error("ControlToken object not found for area %s" % r.area.board_area.code)
				raise GraphicsError
			base_map.paste(rebellion_marker, coords, rebellion_marker)
	if fow:
		for player in game.player_set.filter(user__isnull=False):
			player_map = base_map.copy()
			paste_units(player_map, game, watcher=player)
			result = player_map.convert("RBG")
			filename = game.get_map_path(player)
			ensure_dir(filename)
			result.save(filename)
	else:
		paste_units(base_map, game)
		result = base_map.convert("RGB")
		filename = game.get_map_path()
		ensure_dir(filename)
		result.save(filename)
		make_game_thumb(game, 187, 267)

	return True

def make_game_thumb(game, w, h):
	""" Make a thumbnail of the game map image """
	size = w, h
	fd = game.get_map_path()
	outfile = game.thumbnail_path
	im = Image.open(fd)
	im.thumbnail(size, Image.ANTIALIAS)
	ensure_dir(outfile)
	im.save(outfile, "JPEG")

