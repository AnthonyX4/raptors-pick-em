from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# connect sqlalchemy to the database named by settings.database_url (postgres through asyncpg).
# pool_pre_ping checks a pooled connection is still alive before handing it out, so a database restart
# (or rds failing over) costs one reconnect instead of an error on the first request after it
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False, # keep attributes loaded after commit, an expired attribute would need a lazy load (not allowed in async)
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as db:
        yield db


NOT_MIGRATED = "The database has no tables yet. Create them with: uv run alembic upgrade head"


async def has_table(name: str) -> bool:
    """Whether the migrations have run, checked before anything else touches the database, so a fresh
    database fails with that instruction instead of a "relation does not exist" error mid-request."""
    async with engine.connect() as conn:
        return await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table(name))
