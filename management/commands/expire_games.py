from django.core.management.base import NoArgsCommand, CommandError
from django.conf import settings

import logging
logger = logging.getLogger(__name__)

from machiavelli import models

class Command(NoArgsCommand):
	"""
This script checks for too old, not started games and deletes them.
	"""

	help = 'This script checks for too old, not started games and deletes them.'

	def handle_noargs(self, **options):
		self.stdout.write("Looking for expired games...")
		if settings.MAINTENANCE_MODE:
			self.stderr.write("App is in maintenance mode. Exiting.")
			return
		games = models.Game.objects.exclude(started__isnull=False).exclude(finished__isnull=False)
		for g in games:
			if g.expired:
				msg = "%s is expired and will be deleted." % g.slug
				logger.info(msg)
				self.stdout.write(msg)
				g.notify_players("game_expired", {"title": g.title })
				g.delete()

				
