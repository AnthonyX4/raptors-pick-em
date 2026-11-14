"""One-off move of an old SQLite database (raptors.db, from before step 14) into Postgres.

Copies every row of every table, so accounts, picks, chat and the season's games all come across with
their ids unchanged (tokens and links that name an id keep working). Run it once, from Backend/:

    uv run alembic upgrade head                                        # the tables, empty
    uv run python harvest_scripts/copy_sqlite_to_postgres.py raptors.db

The target is DATABASE_URL from .env, and it must be migrated and empty: copying into a database that
already has rows would clash on ids. No need to seed afterwards, the games come across too.
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR)) # so database/models are importable regardless of cwd

from sqlalchemy import Integer, create_engine, func, inspect, select, text

import models # noqa: F401, registers every table on Base.metadata
from database import Base, NOT_MIGRATED, engine, has_table

# parents before children (teams before games before picks), so every foreign key finds its row
TABLES = Base.metadata.sorted_tables


def read_sqlite(path: Path) -> dict[str, list[dict]]:
    """Every row of every table, read through the models' column types: UTCDateTime hands back
    timezone-aware datetimes and booleans come back as True/False, ready for postgres."""
    sqlite = create_engine(f"sqlite:///{path}")
    present = set(inspect(sqlite).get_table_names())
    rows = {}
    with sqlite.connect() as conn:
        for table in TABLES:
            if table.name not in present:
                print(f"  {table.name}: not in the old database, skipped")
                continue
            rows[table.name] = [dict(row._mapping) for row in conn.execute(select(table))]
    sqlite.dispose()
    return rows


async def copy(rows: dict[str, list[dict]]) -> int:
    if not await has_table("alembic_version"):
        print(f"{NOT_MIGRATED} ❌")
        return 1

    async with engine.begin() as conn: # one transaction: if anything fails, nothing is half copied
        for table in TABLES:
            if await conn.scalar(select(func.count()).select_from(table)):
                print(f"Postgres already has rows in {table.name}. This only copies into an empty database ❌")
                return 1

        for table in TABLES:
            batch = rows.get(table.name, [])
            if batch:
                await conn.execute(table.insert(), batch)
            print(f"  {table.name}: {len(batch)} rows")

        # the rows kept their ids, but postgres hands out new ones from a sequence that still starts at 1.
        # move each sequence past the largest copied id, or the next signup would collide with user 1
        for table in TABLES:
            pk = list(table.primary_key.columns)
            if len(pk) == 1 and isinstance(pk[0].type, Integer) and pk[0].autoincrement in (True, "auto"):
                await conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0].name}'), "
                    f"COALESCE(MAX({pk[0].name}), 1), MAX({pk[0].name}) IS NOT NULL) FROM {table.name}"
                ))

    await engine.dispose()
    print("\nCopied ✅")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"No file at {path} ❌")
        return 1
    if not engine.url.get_backend_name().startswith("postgresql"):
        print(f"DATABASE_URL points at {engine.url.get_backend_name()}, not postgres ❌")
        return 1

    print(f"Copying {path} into {engine.url.render_as_string(hide_password=True)}\n")
    return asyncio.run(copy(read_sqlite(path)))


if __name__ == "__main__":
    sys.exit(main())
