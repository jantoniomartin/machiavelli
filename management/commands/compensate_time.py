from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from machiavelli.models import LiveGame

class Command(BaseCommand):
    """
Changes the value of 'last_phase_change' for a live game (or all, if no argument is given), adding a number of minutes,
to compensate downtime periods.
    """

    help = """ Adds --minutes minutes to "last_phase_change" of specified games. If no game
    is given, it will update ALL live games. """
    
    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('slug', nargs='*', type=str)

        # Named (optional) arguments
        parser.add_argument(
            '--minutes',
            type=int,
            action='store',
            help='Minutes to be added to live games',
        )

    def handle(self, *args, **options):
        minutes = options.get('minutes')
        tplus = timedelta(minutes=minutes)
        if len(args) > 0:
            games = LiveGame.objects.filter(slug__in=args)
        else:
            games = LiveGame.objects.all()
        if games.count() == 0:
            self.stdout.write("No games found. Exiting.\n")
            return
        for g in games:
            current = g.last_phase_change
            self.stdout.write("Changing time for game %s\n" % g.slug)
            self.stdout.write("Current time is %s\n" % current)
            try:
                t = current + tplus
                g.last_phase_change = t
                g.save()
            except:
                self.stderr.write("ERROR: Could not change time of game %s\n" % g.slug)
            else:
                self.stdout.write("New time is %s\n" % t)
