from django import template
from django.conf import settings

register = template.Library()

def rule_icons(config):
	icons = []
	if config.finances:
		icons.append('finances')
	if config.assassinations:
		icons.append('assassinations')
	if config.bribes:
		icons.append('bribes')
	if config.excommunication:
		icons.append('excommunication')
	if config.famine:
		icons.append('famine')
	if config.plague:
		icons.append('plague')
	if config.storms:
		icons.append('storms')
	if config.special_units:
		icons.append('special-units')
	if config.strategic:
		icons.append('strategic')
	if config.lenders:
		icons.append('lenders')
	if config.unbalanced_loans:
		icons.append('unbalanced-loans')
	if config.conquering:
		icons.append('conquering')

	return {'icons' : icons,
			'STATIC_URL': settings.STATIC_URL}

register.inclusion_tag('machiavelli/rule_icons.html')(rule_icons)
