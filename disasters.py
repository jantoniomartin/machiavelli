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

""" This module defines two 2-dimension arrays, taken from Machiavelli(R),
to get random natural disasters. 

The arrays are ``FAMINE_TABLE`` and ``PLAGUE_TABLE``.
"""


from machiavelli import dice

PLAGUE_TABLE = [
[''     , 'SWI'  , ''     , ''     , 'CAR'  , ''     , ''     , ''     , ''     , 'MON'  , 'CAP'  ],
['RAG'  , 'BOS'  , 'SLA'  , ''     , ''     , ''     , 'CRO'  , ''     , ''     , 'BARI' , 'TYR'  ],
['SAV'  , ''     , ''     , 'FRI'  , ''     , 'ROME' , ''     , 'MAR'  , 'PAV'  , ''     , ''     ],
[''     , 'SAL'  , 'VER'  , ''     , 'DAL'  , 'LUC'  , 'BOL'  , 'CARIN', 'PRO'  , ''     , ''     ],
[''     , ''     , 'TUR'  , 'SIE'  , 'MES'  , 'PAD'  , 'AUS'  , 'FER'  , ''     , ''     , ''     ],
['PAL'  , ''     , 'GEN'  , 'ALB'  , 'PISA' , 'TUN'  , 'AVI'  , 'MIL'  , ''     , ''     , 'SAR'  ],
['DUR'  , ''     , 'NAP'  , 'MOD'  , 'PER'  , 'CRE'  , 'VEN'  , 'FLO'  , ''     , ''     , ''     ],
[''     , 'BER'  , 'ANC'  , 'PAR'  , ''     , ''     , ''     , ''     , 'MAN'  , 'IST'  , ''     ],
['PIO'  , 'HUN'  , ''     , 'URB'  , ''     , ''     , ''     , ''     , 'TRE'  , ''     , 'COMO' ],
['ARE'  , 'FOR'  , ''     , ''     , ''     , ''     , ''     , 'OTR'  , ''     , 'AQU'  , 'SPO'  ],
['TRENT', 'HER'  , ''     , 'PIS'  , ''     , ''     , ''     , 'COR'  , ''     , 'PAT'  , 'SALZ' ]
]

FAMINE_TABLE = [
[''     , ''     , 'PRO'  , 'PAT'  , 'MOD'  , ''     , 'COR'  , 'ANC'  , ''     , ''     , ''     ],
[''     , 'PIO'  , ''     , ''     , ''     , ''     , ''     , 'TUN'  , ''     , ''     , 'PAL'  ],
['PER'  , ''     , 'OTR'  , 'PAD'  , 'SWI'  , 'CRE'  , ''     , ''     , 'HER'  , ''     , ''     ],
['FRI'  , ''     , 'BOL'  , 'SAL'  , 'VER'  , 'AUS'  , 'MIL'  , 'SIE'  , ''     , ''     , 'DUR'  ],
['MAR'  , 'RAG'  , ''     , 'CARIN', 'BER'  , 'PIS'  , 'SPO'  , ''     , ''     , 'HUN'  , ''     ],
[''     , 'BARI' , 'SLA'  , 'MON'  , 'URB'  , 'FOR'  , ''     , 'COMO' , 'TRENT', ''     , ''     ],
['FER'  , ''     , 'ROME' , 'PAV'  , ''     , ''     , 'ARE'  , ''     , 'SALZ' , 'ALB'  , 'GEN'  ],
[''     , ''     , 'CRO'  , ''     , 'FLO'  , 'TUR'  , 'MAN'  , 'CAP'  , 'TRE'  , ''     , ''     ],
['SAV'  , ''     , 'SAR'  , ''     , 'PAR'  , 'BOS'  , 'TYR'  , ''     , 'NAP'  , ''     , 'DAL'  ],
[''     , ''     , 'VEN'  , ''     , ''     , ''     , ''     , 'CAR'  , ''     , 'MES'  , ''     ],
[''     , ''     , ''     , 'PISA' , 'AQU'  , 'AVI'  , 'LUC'  , ''     , 'IST'  , ''     , ''     ]
]

STORM_TABLE = [
[''     , ''     , ''     , 'IS'   , ''     , ''     , ''     , ''     , ''     , ''     , ''     ],
['UA'   , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , 'WM'   , ''     ],
[''     , ''     , 'GOL'  , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     ],
[''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     ],
[''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     ],
[''     , ''     , ''     , ''     , ''     , 'TS'   , ''     , ''     , ''     , ''     , ''     ],
[''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     ],
[''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     ],
[''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , ''     , 'LS'   , ''     ],
[''     , 'CM'   , ''     , ''     , ''     , ''     , ''     , ''     , 'GON'  , ''     , ''     ],
[''     , ''     , ''     , ''     , ''     , ''     , ''     , 'LA'   , ''     , ''     , ''     ],
]

def get_year():
	""" Returns an int (1-6) that will be used to determine if the year is *good*, *bad* or *very bad*, regarding natural disasters.
	"""

	return dice.roll_1d6()

def get_row(year):
	""" If the year roll is 2, 3 or 6, returns a row index (0-10).
	"""

	if year in [2, 3, 6]:
		return dice.roll_2d6() - 2
	else:
		return False

def get_column(year):
	""" If the year roll is 4, 5, or 6, returns a column index (0-10).
	"""

	if year in [4, 5, 6]:
		return dice.roll_2d6() - 2
	else:
		return False

def get_provinces(table):
	""" Returns a list of province codes that will be affected by a natural
	disaster in the current season.
	"""

	year = get_year()
	row = get_row(year)
	column = get_column(year)
	provinces = []
	if row:	
		for p in table[row]:
			provinces.append(p)
	if column:
		for r in table:
			provinces.append(r[column])
	return provinces

def get_plague():
	""" A proxy function to call ``get_provinces`` with ``PLAGUE_TABLE``. """
	return get_provinces(PLAGUE_TABLE)

def get_famine():
	""" A proxy function to call ``get_provinces`` with ``FAMINE_TABLE``. """
	return get_provinces(FAMINE_TABLE)

def get_storms():
	""" A proxy function to call ``get_provinces`` with ``STORM_TABLE``. """
	return get_provinces(STORM_TABLE)

