from django.conf import settings
from django.utils.translation import ugettext_noop as _

def create_notice_types(sender, **kwargs):
    if "pinax.notifications" in settings.INSTALLED_APPS:
        from pinax.notifications.models import NoticeType 
        print("Creating notices for machiavelli")
        NoticeType.create("game_started",
            _("Game started"),
            _("a game that you're a player in has started"))
        NoticeType.create("game_over",
            _("Game over"),
            _("a game that you're playing is over"))
        NoticeType.create("new_phase",
            _("New phase"),
            _("a new phase has begun"))
        NoticeType.create("received_ducats",
            _("Ducats received"),
            _("you have received some ducats"))
        NoticeType.create("new_revolution",
            _("New revolution"),
            _("you skipped your turn"))
        NoticeType.create("missed_turn",
            _("Missed turn"),
            _("you missed your turn"))
        NoticeType.create("overthrow_attempt",
            _("Overthrow attempt"),
            _("you are being overthrown"))
        NoticeType.create("lost_player",
            _("Overthrow"),
            _("you have been overthrown"))
        NoticeType.create("got_player",
            _("Overthrow"),
            _("you have overthrown a government"))
        NoticeType.create("new_invitation",
            _("New invitation"),
            _("you have been invited to a private game"))
        NoticeType.create("lost_invitation",
            _("Invitation revoked"),
            _("your invitation to a private game has been revoked"))
        NoticeType.create("team_message_received",
            _("Team message received"),
            _("you receive a team message"))
        NoticeType.create("player_excommunicated",
            _("Player excommunicated"),
            _("you are excommunicated in a game"))
        NoticeType.create("player_absolved",
            _("Player absolved"),
            _("your excommunication is lifted"))
        NoticeType.create("game_expired",
            _("Expired game"),
            _("one of your games expires and is deleted"))
    else:
        print("machiavelli: Skipping creation of NoticeTypes")
