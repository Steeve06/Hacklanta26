from django.apps import AppConfig


class LmsConfig(AppConfig):
    name = "lms"

    def ready(self):
        from . import catalog

        catalog.connect()
