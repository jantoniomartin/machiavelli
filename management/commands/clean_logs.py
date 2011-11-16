from datetime import datetime, timedelta

from django.core.management.base import NoArgsCommand, CommandError

import jogging.models as jogging

AGE=10*24*60*60

class Command(NoArgsCommand):
	"""
This script deletes all log entries that are older than AGE days.
	"""
	help = 'This command deletes all log entries that are older than AGE days.'

	def handle_noargs(self, **options):
		age = timedelta(0, AGE)
		threshold = datetime.now() - age
		print "Deleting logs that were added before %s" % threshold
		old_logs = jogging.Log.objects.filter(datetime__lt=threshold)
		print "%s logs will be deleted" % len(old_logs)
		old_logs.delete()
