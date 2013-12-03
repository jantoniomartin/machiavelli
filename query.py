from django.db import models

class GameQuerySet(models.query.QuerySet):
	"""A lazy database lookup for a set of games"""
	def joinable(self, user=None):
		qs = self.exclude(slots=0)
		if user:
			qs = qs.exclude(player__user=user)
		return qs

	def pending(self, user=None):
		qs = self.filter(slots=0, started__isnull=True)
		if user:
			qs = qs.filter(player__user=user)
		return qs

	def finished(self):
		return self.filter(finished__isnull=False)
