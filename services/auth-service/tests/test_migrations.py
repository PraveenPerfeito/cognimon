from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_users_and_revoked_refresh_token_tables() -> None:
    service_root = Path(__file__).resolve().parent.parent
    database_path = service_root / "tests" / "auth-service-migrations.db"
    if database_path.exists():
        database_path.unlink()

    alembic_config = Config(str(service_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(service_root / "migrations"))
    alembic_config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    try:
        command.upgrade(alembic_config, "head")

        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            inspector = inspect(engine)

            assert "users" in inspector.get_table_names()
            assert "revoked_refresh_tokens" in inspector.get_table_names()
            column_names = {column["name"] for column in inspector.get_columns("users")}
            assert {"id", "email", "display_name", "password_hash", "role"} <= column_names
            revoked_column_names = {
                column["name"] for column in inspector.get_columns("revoked_refresh_tokens")
            }
            assert {"token_id", "user_id", "expires_at", "revoked_at"} <= revoked_column_names
        finally:
            engine.dispose()
    finally:
        if database_path.exists():
            database_path.unlink()
