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

""" This module defines ``Signals`` to be sent by machiavelli objects. 

These signals are closely related to ``condottieri_events``, so whenever a
new Signal is defined, a related Event should be defined, and conversely.
"""

from django.dispatch import Signal

player_joined = Signal(providing_args=[])
## unit_placed is sent by Unit when placed
unit_placed = Signal(providing_args=[])
## unit_disbanded is sent by Unit when deleted 
unit_disbanded = Signal(providing_args=[])

## maybe this one could be replaced by a post_save signal
order_placed = Signal(providing_args=["destination", "subtype",
									"suborigin", "subcode", "subdestination",
									"subconversion"])
standoff_happened = Signal(providing_args=[])
unit_converted = Signal(providing_args=["before", "after"])
area_controlled = Signal(providing_args=["new_home",])
unit_moved = Signal(providing_args=["destination"])
unit_retreated = Signal(providing_args=["destination"])
support_broken = Signal(providing_args=[])
forced_to_retreat = Signal(providing_args=[])
unit_surrendered = Signal(providing_args=[])
siege_started = Signal(providing_args=[])
unit_changed_country = Signal(providing_args=[])
unit_to_autonomous = Signal(providing_args=[])
government_overthrown = Signal(providing_args=[])
overthrow_attempted = Signal(providing_args=[])
player_surrendered = Signal(providing_args=[])
country_conquered = Signal(providing_args=["country"])
country_eliminated = Signal(providing_args=["country"])
famine_marker_placed = Signal(providing_args=[])
storm_marker_placed = Signal(providing_args=[])
plague_placed = Signal(providing_args=[])
rebellion_started = Signal(providing_args=[])
country_excommunicated = Signal(providing_args=[])
country_forgiven = Signal(providing_args=[])
income_raised = Signal(providing_args=["ducats"])
expense_paid = Signal(providing_args=[])
player_assassinated = Signal(providing_args=[])
assassination_attempted = Signal(providing_args=[])
game_finished = Signal(providing_args=[])
diplomat_uncovered = Signal(providing_args=[])
