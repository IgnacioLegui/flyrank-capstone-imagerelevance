"""Alembic entry point: runs migrations against the database from the app settings."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings
from app.db.models import Base
from app.db.session import sqlalchemy_url

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False: running migrations from inside the app (or tests) must not
    # silence loggers the app already created, like "worker.ingest"
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Lets `alembic check` / `--autogenerate` compare the models with the real database
target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(sqlalchemy_url(get_settings().database_url))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
