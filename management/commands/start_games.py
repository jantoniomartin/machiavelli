from django.core.management.base import NoArgsCommand, CommandError
from django.conf import settings

import logging
logger = logging.getLogger(__name__)

from machiavelli import models

class Command(NoArgsCommand):
	"""
	Starts games that have all their players and have not started.
	"""

	help = 'Starts games that have all their players and have not started.'
	
	def handle_noargs(self, **options):
		self.stdout.write("Starting games...\n")
		if settings.MAINTENANCE_MODE:
			logger.warning("App is in maintenance mode. Exiting.\n")
			self.stderr.write("App is in maintenance mode. Exiting.\n")
			return
		games = models.Game.objects.filter(slots=0,
											started__isnull=True,
											autostart=True)
		if games.count() > 0:
			for g in games:
				msg = "Starting game %s\n" % g.slug
				self.stdout.write(msg)
				logger.info(msg)
				g.start()
		else:
			self.stdout.write("No games ready to start.\n")
