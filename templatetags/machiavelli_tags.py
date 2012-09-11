from django import template
from django.conf import settings

register = template.Library()

def rule_icons(config):
	icons = []
	if config.finances:
		icons.append('finances')
	if config.assassinations:
		icons.append('assassinations')
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
	if config.lenders:
		icons.append('lenders')
	if config.unbalanced_loans:
		icons.append('unbalanced-loans')
	if config.conquering:
		icons.append('conquering')
	if config.strategic:
		icons.append('strategic')
	if config.variable_home:
		icons.append('variable-home')
	if config.taxation:
		icons.append('taxation')
	if config.fow:
		icons.append('fow')
	if config.press == 1:
		icons.append('gunboat')

	return {'icons' : icons,
			'STATIC_URL': settings.STATIC_URL}

register.inclusion_tag('machiavelli/rule_icons.html')(rule_icons)

@register.filter
def truncatesmart(value, limit=80):
    """
	Taken from http://djangosnippets.org/snippets/1259/
    Truncates a string after a given number of chars keeping whole words.
    
    Usage:
        {{ string|truncatesmart }}
        {{ string|truncatesmart:50 }}
    """
    
    try:
        limit = int(limit)
    # invalid literal for int()
    except ValueError:
        # Fail silently.
        return value
    
    # Make sure it's unicode
    value = unicode(value)
    
    # Return the string itself if length is smaller or equal to the limit
    if len(value) <= limit:
        return value
    
    # Cut the string
    value = value[:limit]
    
    # Break into words and remove the last
    words = value.split(' ')[:-1]
    
    # Join the words and return
    return ' '.join(words) + '...'
