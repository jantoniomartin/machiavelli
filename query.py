from datetime import datetime, timedelta

from django.conf import settings
from django.db import models

class GameQuerySet(models.query.QuerySet):
	"""A lazy database lookup for a set of games"""
	def joinable(self, user=None):
		qs = self.exclude(slots=0)
		if user:
			qs = qs.exclude(player__user=user)
		return qs

	def pending(self, user=None):
		qs = self.filter(started__isnull=True)
		if user:
			qs = qs.filter(player__user=user)
		return qs
	
	def in_progress(self, user=None):
		qs = self.filter(started__isnull=False, finished__isnull=True)
		if user:
			qs = qs.filter(player__user=user)
		return qs

	def finished(self):
		return self.filter(finished__isnull=False)

	def private(self):
		return self.filter(private=True)

	def by_teams(self):
		return self.filter(teams__gt=0)
	
	def expired(self):
		"""Return a queryset of games that have not started and are too
		old."""
		s = getattr(settings, 'GAME_EXPIRATION', 60*60*24*30) 
		old_date = datetime.now() - timedelta(seconds=s)
		return self.filter(
			started__isnull=True,
			finished__isnull=True,
			created__lt=old_date
		)

class GameCommentQuerySet(models.query.QuerySet):
	"""A lazy database lookup for a set of game comments"""
	def public(self):
		return self.filter(is_public=True)
