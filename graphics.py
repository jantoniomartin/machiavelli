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

#BASE_DIR=os.path.join(settings.PROJECT_ROOT, 'machiavelli/media/machiavelli/tokens')
APP_ROOT=os.path.abspath(os.path.dirname(__file__))
TOKENS_DIR=os.path.join(APP_ROOT, 'media/machiavelli/tokens')

BASEMAP='base-map.png'
#if settings.DEBUG:
#	MAPSDIR = os.path.join(settings.PROJECT_ROOT, 'machiavelli/media/machiavelli/maps')
#else:
#	MAPSDIR = os.path.join(settings.MEDIA_ROOT, 'maps')
MAPSDIR=os.path.join(settings.MEDIA_ROOT, 'maps')
SCENARIOSDIR=os.path.join(settings.MEDIA_ROOT, 'scenarios')

def ensure_dir(f):
	d = os.path.dirname(f)
	if not os.path.exists(d):
		os.makedirs(d)

def make_map(game):
	""" Opens the base map and add flags, control markers, unit tokens and other tokens. Then saves
	the map with an appropriate name in the maps directory.
	"""
	base_map = Image.open(os.path.join(TOKENS_DIR, BASEMAP))
	if game.configuration.special_units:
		loyal_army = Image.open("%s/loyal-army.png" % TOKENS_DIR)
		loyal_fleet = Image.open("%s/loyal-fleet.png" % TOKENS_DIR)
		loyal_garrison = Image.open("%s/loyal-garrison.png" % TOKENS_DIR)
		elite_army = Image.open("%s/elite-army.png" % TOKENS_DIR)
		elite_fleet = Image.open("%s/elite-fleet.png" % TOKENS_DIR)
		elite_garrison = Image.open("%s/elite-garrison.png" % TOKENS_DIR)
	## if there are disabled areas, mark them
	marker = Image.open("%s/disabled.png" % TOKENS_DIR)
	for a in game.get_disabled_areas():
		base_map.paste(marker, (a.aftoken.x, a.aftoken.y), marker)
	## mark special city incomes
	marker = Image.open("%s/chest.png" % TOKENS_DIR)
	for i in game.scenario.cityincome_set.all():
		base_map.paste(marker, (i.city.gtoken.x + 48, i.city.gtoken.y), marker)
	##
	garrisons = []
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
			base_map.paste(flag, (area.controltoken.x, area.controltoken.y - 15), flag)
		## paste As and Fs (not garrisons because of sieges)
		units = player.unit_set.filter(placed=True)
		army = Image.open("%s/A-%s.png" % (TOKENS_DIR, player.static_name))
		fleet = Image.open("%s/F-%s.png" % (TOKENS_DIR, player.static_name))
		for unit in units:
			if unit.besieging:
				coords = (unit.area.board_area.gtoken.x, unit.area.board_area.gtoken.y)
			else:
				coords = (unit.area.board_area.aftoken.x, unit.area.board_area.aftoken.y)
			if unit.type == 'A':
				base_map.paste(army, coords, army)
				if unit.power > 1:
					base_map.paste(elite_army, coords, elite_army)
				if unit.loyalty > 1:
					base_map.paste(loyal_army, coords, loyal_army)
			elif unit.type == 'F':
				base_map.paste(fleet, coords, fleet)
				if unit.power > 1:
					base_map.paste(elite_fleet, coords, elite_fleet)
				if unit.loyalty > 1:
					base_map.paste(loyal_fleet, coords, loyal_fleet)
			else:
				pass
	## paste garrisons
	for player in game.player_set.all():
		if player.user:
			garrison = Image.open("%s/G-%s.png" % (TOKENS_DIR, player.static_name))
		else:
			## autonomous
			garrison = Image.open("%s/G-autonomous.png" % TOKENS_DIR)
		for unit in player.unit_set.filter(type__exact='G'):
			coords = (unit.area.board_area.gtoken.x, unit.area.board_area.gtoken.y)
			base_map.paste(garrison, coords, garrison)
			if unit.power > 1:
				base_map.paste(elite_garrison, coords, elite_garrison)
			if unit.loyalty > 1:
				base_map.paste(loyal_garrison, coords, loyal_garrison)
	## paste famine markers
	if game.configuration.famine:
		famine = Image.open("%s/famine-marker.png" % TOKENS_DIR)
		for a in game.gamearea_set.filter(famine=True):
			coords = (a.board_area.aftoken.x + 16, a.board_area.aftoken.y + 16)
			base_map.paste(famine, coords, famine)
	## paste storm markers
	if game.configuration.storms:
		storm = Image.open("%s/storm-marker.png" % TOKENS_DIR)
		for a in game.gamearea_set.filter(storm=True):
			coords = (a.board_area.aftoken.x + 16, a.board_area.aftoken.y + 16)
			base_map.paste(storm, coords, storm)
	## paste rebellion markers
	if game.configuration.finances:
		rebellion_marker = Image.open("%s/rebellion-marker.png" % TOKENS_DIR)
		for r in game.get_rebellions():
			if r.garrisoned:
				coords = (r.area.board_area.gtoken.x, r.area.board_area.gtoken.y)
			else:
				coords = (r.area.board_area.aftoken.x, r.area.board_area.aftoken.y)
			base_map.paste(rebellion_marker, coords, rebellion_marker)
	## save the map
	#result = base_map
	result = base_map.resize((1250, 1780), Image.ANTIALIAS)
	filename = os.path.join(MAPSDIR, game.map_dir, game.map_filename)
	ensure_dir(filename)
	result.save(filename)
	make_game_thumb(game, 187, 267)
	return True

def make_game_thumb(game, w, h):
	""" Make a thumbnail of the game map image """
	size = w, h
	fd = os.path.join(MAPSDIR, game.map_dir, game.map_filename)
	outfile = os.path.join(MAPSDIR, game.map_dir, "thumb", game.map_filename)
	im = Image.open(fd)
	im.thumbnail(size, Image.ANTIALIAS)
	ensure_dir(outfile)
	im.save(outfile, "JPEG")

