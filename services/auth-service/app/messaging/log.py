import logging

from app.messaging.contracts import AuthEventPublisher, UserRegisteredEvent

logger = logging.getLogger(__name__)


class LoggingAuthEventPublisher(AuthEventPublisher):
    async def publish_user_registered(self, event: UserRegisteredEvent) -> None:
        logger.info(
            "event_type=user_registered user_id=%s email=%s role=%s",
            event.user_id,
            event.email,
            event.role,
        )
