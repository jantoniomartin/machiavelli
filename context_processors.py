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
		for k, v in list(conf.items()):
			if not v['banner'] is None and v['banner'] != "":
				context.update({'%s_banner' % k: v['banner']})
			if not v['url'] is None:
				context.update({'%s_url' % k: v['url']})
	return context

def activity(request):
	user = request.user
	if user.is_authenticated():
		cache_key = "activity_%s" % user.pk
	else:
		cache_key = "activity_anon"
	context = cache.get(cache_key)
	if not context:
		context = {}
		context['activity'] = machiavelli.Player.objects.exclude(user__isnull=True).values("user").distinct().count()
		context['games'] = machiavelli.LiveGame.objects.count()
		if user.is_authenticated():
			context['revolution_counter'] = machiavelli.Revolution.objects.filter(overthrow=False, active__isnull=False, opposition__isnull=True).count()
			context['active_counter'] = machiavelli.Player.objects.filter(user=user, game__started__isnull=False, game__finished__isnull=True).count()
			context['pending_counter'] = machiavelli.Player.objects.filter(user=user, game__started__isnull=True, game__finished__isnull=True).count()
			context['joinable_counter'] = machiavelli.Game.objects.joinable(user).exclude(private=True).count()
		else:	
			context['joinable_counter'] = machiavelli.Game.objects.joinable().exclude(private=True).count()
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

