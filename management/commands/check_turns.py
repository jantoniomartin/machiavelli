from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import logging
logger = logging.getLogger(__name__)

from machiavelli import models

class Command(BaseCommand):
	"""
This script checks in every active game if the current turn must change. This happens either
when all the players have finished OR the time limit is exceeded
	"""

	help = 'This script checks in every active game if the current turn must change. \
	This happens either when all the players have finished OR the time limit is exceeded.'

	def handle_noargs(self, **options):
		self.stdout.write("Checking phase changes.")
		if settings.MAINTENANCE_MODE:
			logger.warning("App is in maintenance mode. Exiting.")
			self.stderr.write("App is in maintenance mode. Exiting.")
			return
		games = models.LiveGame.objects.filter(fast=False, paused=False)
		for g in games:
			self.stdout.write("Checking game %s" % g.slug)
			try:
				g.check_finished_phase()
			except Exception as e:
				msg = "Error while checking if phase is finished in game %s\n\n" % g.pk
				logger.error(msg)
				logger.error(e)
				self.stderr.write(msg)
				self.stderr.write(e)
				continue
		fast_games = models.LiveGame.objects.filter(fast=True, paused=False)
		for game in fast_games:
			try:
				game.check_finished_phase()
			except Exception as e:
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
		## try to resolve revolutions in games with extended deadline, when the lazy players have not
		## acted and half the extended deadline has been reached.
		revolutions = models.Revolution.objects.filter(active__isnull=False, opposition__isnull=False, overthrow=False)
		for r in revolutions:
			if r.game.extended_deadline:
				if r.game.time_to_limit().total_seconds() < r.game.time_limit / 2:
					r.resolve()
