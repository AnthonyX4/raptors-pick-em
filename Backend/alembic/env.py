"""How Alembic connects and what it compares against. Run from Backend/:

    uv run alembic upgrade head                                  # apply every migration not applied yet
    uv run alembic revision --autogenerate -m "add x to games"  # after changing a model: write the next one
    uv run alembic downgrade -1                                  # undo the last one
    uv run alembic check                                         # fails if the models and migrations disagree
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

import models # noqa: F401, registers every table on Base.metadata, autogenerate would see an empty schema without it
from config import settings
from database import Base

config = context.config
# one source of truth: the same DATABASE_URL the app uses (from .env, or the container's environment),
# so alembic.ini holds no url and no password
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%")) # % escaped, the ini parser reads it as interpolation

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# what autogenerate compares the database against
target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Write UTCDateTime into migration files as the plain column type it stores.

    UTCDateTime only adds python-side behaviour (utc in, aware datetimes out); the database just sees a
    timestamptz. A migration that imported models would break the day a model it names changes or goes.
    """
    if type_ == "type" and isinstance(obj, models.UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False # anything else: alembic's default rendering


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it, no database needed."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        render_item=render_item,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_item=render_item)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # alembic itself is sync; the app's driver (asyncpg) is async, so connect async and hand
    # alembic the connection through run_sync, the same trick the api used for create_all
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool, # a one-off command, nothing to pool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
