from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class UserRegisteredEvent:
    user_id: str
    email: str
    role: str


class AuthEventPublisher(Protocol):
    async def publish_user_registered(self, event: UserRegisteredEvent) -> None:
        """Publish a user registration event."""

