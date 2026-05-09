import logging

from app.messaging.contracts import AuthEventPublisher, UserRegisteredEvent

logger = logging.getLogger(__name__)


class NoopAuthEventPublisher(AuthEventPublisher):
    async def publish_user_registered(self, event: UserRegisteredEvent) -> None:
        logger.debug("Suppressed event publish for %s", event)

