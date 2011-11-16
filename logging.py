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

""" This module defines functions to log some info about the game flow.

At the moment, only a XML snapshot of each turn status is saved. It's useful
if an error happens and we have to restore a previous turn.
"""

import os

from django.conf import settings

SNAPSHOTS_DIR = os.path.join(settings.PROJECT_ROOT, 'machiavelli/media/machiavelli/maps/snapshots')

def save_snapshot(game):
	""" Saves a XML snapshot of the current status of ``game``. """

	filename = "%s.snap" % game.id
	try:
		path = os.path.join(SNAPSHOTS_DIR, filename)
		fd = open(path, mode='a')
	except IOError, v:
		print v
		return
	else:
		fd.write("\n")
		fd.write("<turn year=\"%s\" season=\"%s\">\n" % (game.year, game.season))
		for player in game.player_set.all():
			if player.country:
				fd.write("<player country=\"%s\">\n" % (player.country))
			else:
				fd.write("<player>\n")
			for unit in player.unit_set.all():
				fd.write("<unit ")
				fd.write("id=\"%(id)s\" type=\"%(type)s\" area=\"%(area)s\" besieging=\"%(bes)s\" />" %
							{ 'id': unit.id,
							  'type': unit.type,
							  'area': unit.area.board_area.code,
							  'bes': unit.besieging })
				fd.write("\n")
			fd.write("</player>\n")
		fd.write("</turn>\n")
		fd.close()
