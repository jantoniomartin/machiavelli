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

import Image
import os
import os.path

from django.conf import settings

import models as machiavelli

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


def load_unit_tokens(game):
	tokens = dict()
	for player in game.player_set.filter(user__isnull=False):
		t = dict()
		name = player.static_name
		t.update({'A': Image.open("%s/A-%s.png" % (TOKENS_DIR, name))})
		t.update({'F': Image.open("%s/F-%s.png" % (TOKENS_DIR, name))})
		t.update({'G': Image.open("%s/G-%s.png" % (TOKENS_DIR, name))})
		tokens.update({name: t })
	tokens.update({'autonomous': {'G': Image.open("%s/G-autonomous.png" % TOKENS_DIR)}})
	return tokens


def paste_units(board, game, watcher=None):
	tokens = load_unit_tokens(game)
	if isinstance(watcher, machiavelli.Player):
		visible = watcher.visible_areas()
		print "Making secret map for %s" % watcher.static_name
	afs = machiavelli.Unit.objects.filter(type__in=('A','F'), player__game=game, placed=True)
	gars = machiavelli.Unit.objects.filter(type__exact='G', player__game=game, placed=True)
	if isinstance(watcher, machiavelli.Player):
		afs = afs.filter(area__board_area__in=visible)
		gars = gars.filter(area__board_area__in=visible)
	## paste Armies and Fleets
	for unit in afs:
			t = tokens[unit.player.static_name][unit.type]
			if unit.besieging:
				coords = (unit.area.board_area.gtoken.x, unit.area.board_area.gtoken.y)
			else:
				coords = (unit.area.board_area.aftoken.x, unit.area.board_area.aftoken.y)
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
		coords = (unit.area.board_area.gtoken.x, unit.area.board_area.gtoken.y)
		board.paste(t, coords, t)
		if unit.power > 1:
			board.paste(ELITE_G, coords, ELITE_G)
		if unit.loyalty > 1:
			board.paste(LOYAL_G, coords, LOYAL_G)
	
def make_map(game, fow=False):
	""" Opens the base map and add flags, control markers, unit tokens and other tokens. Then saves
	the map with an appropriate name in the maps directory.
	If fow == True, makes one map for every player and doesn't make a thumbnail
	"""
	if game.finished:
		fow = False
	base_map = Image.open(game.scenario.setting.board)
	## if there are disabled areas, mark them
	marker = Image.open("%s/disabled.png" % TOKENS_DIR)
	for a in game.get_disabled_areas():
		base_map.paste(marker, (a.aftoken.x, a.aftoken.y), marker)
	## mark special city incomes
	marker = Image.open("%s/chest.png" % TOKENS_DIR)
	for i in game.scenario.cityincome_set.all():
		base_map.paste(marker, (i.city.gtoken.x + 32, i.city.gtoken.y), marker)
	##
	for player in game.player_set.filter(user__isnull=False):
		## paste control markers
		controls = player.gamearea_set.all()
		marker = Image.open("%s/control-%s.png" % (TOKENS_DIR, player.static_name))
		for area in controls:
			base_map.paste(marker, (area.board_area.controltoken.x, area.board_area.controltoken.y), marker)
		## paste flags
		home = player.home_country()
		flag = Image.open("%s/flag-%s.png" % (TOKENS_DIR, player.static_name))
		for game_area in home:
			area = game_area.board_area
			base_map.paste(flag, (area.controltoken.x, area.controltoken.y - 10), flag)
	## paste famine markers
	if game.configuration.famine:
		famine = Image.open("%s/famine-marker.png" % TOKENS_DIR)
		for a in game.gamearea_set.filter(famine=True):
			coords = (a.board_area.controltoken.x + 12, a.board_area.controltoken.y + 12)
			base_map.paste(famine, coords, famine)
	## paste storm markers
	if game.configuration.storms:
		storm = Image.open("%s/storm-marker.png" % TOKENS_DIR)
		for a in game.gamearea_set.filter(storm=True):
			coords = (a.board_area.controltoken.x + 12, a.board_area.controltoken.y + 12)
			base_map.paste(storm, coords, storm)
	## paste rebellion markers
	if game.configuration.finances:
		rebellion_marker = Image.open("%s/rebellion-marker.png" % TOKENS_DIR)
		for r in game.get_rebellions():
			if r.garrisoned:
				coords = (r.area.board_area.gtoken.x, r.area.board_area.gtoken.y)
			else:
				coords = (r.area.board_area.controltoken.x - 12, r.area.board_area.controltoken.y - 12)
			base_map.paste(rebellion_marker, coords, rebellion_marker)
	if fow:
		for player in game.player_set.filter(user__isnull=False):
			player_map = base_map.copy()
			paste_units(player_map, game, watcher=player)
			result = player_map
			filename = game.get_map_path(player)
			ensure_dir(filename)
			result.save(filename)
	else:
		paste_units(base_map, game)
		result = base_map
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

