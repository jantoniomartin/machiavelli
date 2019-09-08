from datetime import datetime, timedelta

from django.core.management.base import NoArgsCommand, CommandError

from notification import models as notification

AGE=10*24*60*60

class Command(NoArgsCommand):
	"""
This script deletes all notices that are older than AGE days.
	"""
	help = 'This command deletes all notices that are older than AGE days.'

	def handle_noargs(self, **options):
		age = timedelta(0, AGE)
		threshold = datetime.now() - age
		print("Deleting notices that were added before %s" % threshold)
		old_notices = notification.Notice.objects.filter(added__lt=threshold)
		print("%s notices will be deleted" % len(old_notices))
		old_notices.delete()
