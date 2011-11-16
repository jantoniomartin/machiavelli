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

""" This module defines custom field types. """

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

if 'south' in settings.INSTALLED_APPS:
	from south import modelsinspector
else:
	modelsinspector = None

class AutoTranslateField(models.CharField):
	""" This class is a CharField whose contents are translated when shown to
	the user. You need an aux file (translate.py) for manage.py to make the
	messages.

	Taken from http://overtag.dk/wordpress/2008/07/django-auto-translation-of-field-values/
	"""
	__metaclass__ = models.SubfieldBase
	def to_python(self, value):
		return unicode(_(value))

if modelsinspector:
	modelsinspector.add_introspection_rules([], ["^machiavelli\.fields\.AutoTranslateField"])

