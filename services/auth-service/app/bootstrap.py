import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import Database

logger = logging.getLogger(__name__)


async def bootstrap() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = Database(
        settings.database_url,
        echo=settings.environment in {"local", "development"},
    )
    await database.create_schema()
    await database.dispose()
    logger.info("Auth service schema bootstrap completed.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
