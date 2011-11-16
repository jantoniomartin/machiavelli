from django.conf import settings
from django.utils.translation import ugettext_noop as _
from django.db.models import signals

if "notification" in settings.INSTALLED_APPS:
	from notification import models as notification

	def create_notice_types(app, created_models, verbosity, **kwargs):
		print "Creating notices"
		notification.create_notice_type("game_started",
										_("Game started"),
										_("a game that you're a player in has started"))
		notification.create_notice_type("game_over",
										_("Game over"),
										_("a game that you're playing is over"))
		notification.create_notice_type("new_phase",
										_("New phase"),
										_("a new phase has begun"))
		notification.create_notice_type("received_ducats",
										_("Ducats received"),
										_("you have received some ducats"))
		notification.create_notice_type("overthrow_attempt",
										_("Overthrow attempt"),
										_("you are being overthrown"))
		notification.create_notice_type("lost_player",
										_("Overthrow"),
										_("you have been overthrown"))
		notification.create_notice_type("got_player",
										_("Overthrow"),
										_("you have overthrown a government"))
		notification.create_notice_type("new_invitation",
										_("New invitation"),
										_("you have been invited to a private game"))
		notification.create_notice_type("lost_invitation",
										_("Invitation revoked"),
										_("your invitation to a private game has been revoked"))

	signals.post_syncdb.connect(create_notice_types, sender=notification)
else:
	print "Skipping creation of NoticeTypes as notification app not found"
