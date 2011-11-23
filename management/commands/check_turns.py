from datetime import datetime, timedelta

from django.core.management.base import NoArgsCommand, CommandError
from django.conf import settings

import logging
logger = logging.getLogger(__name__)

from machiavelli import models

class Command(NoArgsCommand):
	"""
This script checks in every active game if the current turn must change. This happens either
when all the players have finished OR the time limit is exceeded

Of all the live games, it will adjudicate any existing fast games and only one of the normal
games (to prevent a long running time). To select only one game, it will use the oldest
value of 'Game.last_phase_change'. 
	"""

	help = 'This script checks in every active game if the current turn must change. \
	This happens either when all the players have finished OR the time limit is exceeded.'

	def handle_noargs(self, **options):
		self.stdout.write("Checking phase changes.")
		if settings.MAINTENANCE_MODE:
			logger.warning("App is in maintenance mode. Exiting.")
			self.stderr.write("App is in maintenance mode. Exiting.")
			return
		try:
			game = models.LiveGame.objects.filter(fast=False).order_by('last_phase_change')[0]
		except IndexError: # no live games
			self.stderr.write("There are no live games.")
		else:
			game.check_finished_phase()
		fast_games = models.LiveGame.objects.filter(fast=True)
		for game in fast_games:
			try:
				game.check_finished_phase()
			except Exception, e:
				self.stderr.write("Error while checking if phase is finished in game %s\n\n" % game.pk)
				self.stderr.write(e)
				continue
		## check for fast games that have not yet started and are older than
		## one hour
		fast_games = models.Game.objects.filter(slots__gt=0, fast=True)
		term = timedelta(0, settings.FAST_EXPIRATION)
		for f in fast_games:
			expiration = f.created + term
			if datetime.now() > expiration:
				self.stdout.write("Deleting game %s\n" % f)
				f.delete()
