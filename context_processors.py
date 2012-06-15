from django.conf import settings
from django.core.cache import cache

import machiavelli.models as machiavelli

def banners(request):
	context = {}
	try:
		conf = settings.BANNERS
	except AttributeError:
		return context
	else:
		for k, v in conf.items():
			if not v['banner'] is None and v['banner'] != "":
				context.update({'%s_banner' % k: v['banner']})
			if not v['url'] is None:
				context.update({'%s_url' % k: v['url']})
	return context

def activity(request):
	cache_key = "activity"
	context = cache.get(cache_key)
	if not context:
		context = {}
		context['activity'] = machiavelli.Player.objects.exclude(user__isnull=True).values("user").distinct().count()
		context['games'] = machiavelli.LiveGame.objects.count()
		cache.set(cache_key, context)
	return context

def latest_gossip(request):
	cache_key = "latest_gossip"
	context = cache.get(cache_key)
	if not context:
		context = {}
		context['whispers'] = machiavelli.Whisper.objects.all()[:5]
		cache.set(cache_key, context)
	return context

