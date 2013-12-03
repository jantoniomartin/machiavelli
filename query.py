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

	def get_promoted(self, user=None):
		"""Return a Game that is about to start"""
		s = getattr(settings, 'GAME_PROMOTION', 60*60*24*7)
		after = datetime.now() - timedelta(seconds=s)
		g = self.filter(
			slots__gt=0,
			private=False,
			created__gt=after).order_by('slots')
		if user:
			g = g.exclude(player__user=user)
		try:
			promoted = g[0]
		except IndexError:
			return self.none()
		
class GameCommentQuerySet(models.query.QuerySet):
	"""A lazy database lookup for a set of game comments"""
	def public(self):
		return self.filter(is_public=True)

class PlayerQuerySet(models.query.QuerySet):
	"""A lazy database lookup for a set of players"""
	def waited(self, user):
		"""Return a queryset of players that must confirm their actions
		"""
		p = self.filter(
			game__started__isnull=False,
			done = False,
			surrendered = False
		)
		if user:
			p = p.filter(user=user)
		return p

