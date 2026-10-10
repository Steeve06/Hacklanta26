import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class AiConfig(AppConfig):
    name = "ai"

    def ready(self):
        if not (settings.AI_PROVIDER and settings.AI_API_KEY):
            logger.warning(
                "AI_PROVIDER or AI_API_KEY is not set; Leon will use deterministic fallbacks."
            )
