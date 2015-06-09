from django.apps import AppConfig
from django.db.models.signals import post_migrate

from machiavelli.signals import handlers

class MachiavelliConfig(AppConfig):
    name = 'machiavelli'
    verbose_name = 'Machiavelli'

    def ready(self):
        post_migrate.connect(handlers.create_notice_types, sender=self)
