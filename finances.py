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

""" This module defines functions to get random variable income. 
"""

## the first value of each list is never used
INCOME_TABLE = {
	'austria':  [0, 1, 2, 3, 3, 4, 4],
	'florence': [0, 1, 2, 3, 3, 4, 5],
	'FLO':      [0, 1, 2, 3, 3, 4, 5],
	'france':   [0, 1, 2, 3, 4, 5, 6],
	'GEN':      [0, 1, 2, 2, 3, 3, 4],
	'genoa':    [0, 2, 2, 3, 3, 4, 5],
	'hre':      [0, 1, 2, 3, 3, 4, 4],
	'milan':    [0, 2, 3, 3, 4, 4, 5],
	'MIL':      [0, 2, 3, 3, 4, 4, 5],
	'naples':   [0, 1, 2, 2, 3, 3, 4],
	'NAP':      [0, 1, 2, 2, 3, 3, 4],
	'papacy':   [0, 1, 2, 2, 3, 4, 5],
	'ROME':     [0, 2, 3, 3, 4, 5, 6],
	'savoy':    [0, 1, 2, 3, 4, 5, 6],
	'spain':    [0, 1, 2, 3, 3, 4, 4],
	'turks':    [0, 1, 2, 3, 4, 5, 6],
	'TUN':      [0, 1, 2, 3, 4, 5, 6],
	'venice':   [0, 2, 3, 3, 4, 4, 5],
	'VEN':      [0, 2, 3, 3, 4, 4, 5],
}

def get_ducats(row, column, double=False):
	""" Given a country or city, and the result of the die, return the number
	of ducats"""
	if not row in list(INCOME_TABLE.keys()):
		return 0
	if not column in (1,2,3,4,5,6):
		return 0
	v = INCOME_TABLE[row][column]
	if double:
		return v * 2
	else:
		return v
	

