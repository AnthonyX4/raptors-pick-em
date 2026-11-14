from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# connect sqlalchemy to the database named by settings.database_url (sqlite+aiosqlite unless told otherwise)
engine = create_async_engine(
    settings.database_url,
    # sqlite only: allow the connection to be used from the thread aiosqlite runs it on
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

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
