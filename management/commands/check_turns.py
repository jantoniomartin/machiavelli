from datetime import datetime, timedelta

from django.core.management.base import NoArgsCommand, CommandError
from django.conf import settings

from jogging import logging

from machiavelli import models

class Command(NoArgsCommand):
	"""
This script checks in every active game if the current turn must change. This happens either
when all the players have finished OR the time limit is exceeded
	"""
	help = 'This script checks in every active game if the current turn must change. \
	This happens either when all the players have finished OR the time limit is exceeded.'

	def handle_noargs(self, **options):
		if settings.MAINTENANCE_MODE:
			print "App is in maintenance mode. Exiting."
			return
		active_games = models.Game.objects.exclude(phase=0)
		for game in active_games:
			try:
				game.check_finished_phase()
			except Exception, e:
				print "Error while checking if phase is finished in game %s\n\n" % game.pk
				print e
				continue
		## check for fast games that have not yet started and are older than
		## one hour
		fast_games = models.Game.objects.filter(slots__gt=0, fast=True)
		term = timedelta(0, settings.FAST_EXPIRATION)
		for f in fast_games:
			expiration = f.created + term
			if datetime.now() > expiration:
				print "Deleting game %s\n" % f
				f.delete()
