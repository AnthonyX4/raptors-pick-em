"""
    Loads Backend/nba_data.json (written by harvest.py) into the database.

    usage (from Backend/):
        uv run python harvest_scripts/seed.py

    Safe to re-run: every row is keyed by the nba's own id, so a second seed after a fresh
    harvest updates scores and statuses in place instead of inserting duplicates. That is
    what lets you re-harvest mid-season without wiping the database.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR)) # so database/models are importable regardless of cwd

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, Base, engine
import models

DATA_PATH = BACKEND_DIR / "nba_data.json"


def upsert(db: AsyncSession, model, existing: dict, key, fields: dict) -> str:
    """Update the row if we already have it, otherwise add it. Returns which happened."""
    row = existing.get(key)
    if row is None:
        db.add(model(**fields))
        return "created"
    for name, value in fields.items():
        setattr(row, name, value)
    return "updated"


async def seed_teams(db: AsyncSession, teams: list[dict]) -> dict:
    result = await db.execute(select(models.Team))
    existing = {team.team_id: team for team in result.scalars()}

    counts = {"created": 0, "updated": 0}
    for team in teams:
        counts[upsert(db, models.Team, existing, team["team_id"], team)] += 1
    await db.flush() # games and players reference teams, so the rows have to exist first
    return counts


async def seed_players(db: AsyncSession, players: list[dict]) -> dict:
    result = await db.execute(select(models.Player))
    existing = {player.player_id: player for player in result.scalars()}

    counts = {"created": 0, "updated": 0}
    for player in players:
        counts[upsert(db, models.Player, existing, player["player_id"], player)] += 1
        existing.setdefault(player["player_id"], None) # a player on two rosters in one file is one row
    await db.flush()
    return counts


async def seed_games(db: AsyncSession, games: list[dict]) -> dict:
    result = await db.execute(select(models.Game))
    existing = {game.game_id: game for game in result.scalars()}

    counts = {"created": 0, "updated": 0}
    for game in games:
        fields = dict(game)
        fields["tipoff_utc"] = datetime.fromisoformat(fields["tipoff_utc"]) # json has no datetime type
        counts[upsert(db, models.Game, existing, game["game_id"], fields)] += 1
    await db.flush()
    return counts


async def seed_player_stats(db: AsyncSession, stats: list[dict]) -> dict:
    result = await db.execute(select(models.PlayerGameStat))
    existing = {(row.game_id, row.player_id): row for row in result.scalars()}

    # a box score can name someone no roster did: a 10-day contract, or a player since traded away.
    # they still need a Player row for the foreign key, with no current team
    known_players = set((await db.execute(select(models.Player.player_id))).scalars())
    counts = {"created": 0, "updated": 0}

    for stat in stats:
        player_id = stat["player_id"]
        if player_id not in known_players:
            full_name = f"{stat['first_name']} {stat['last_name']}".strip()
            db.add(models.Player(
                player_id=player_id,
                full_name=full_name,
                first_name=stat["first_name"] or full_name,
                last_name=stat["last_name"] or full_name,
                team_id=None,
            ))
            known_players.add(player_id)

        fields = {name: value for name, value in stat.items() if name not in ("first_name", "last_name")}
        counts[upsert(db, models.PlayerGameStat, existing, (stat["game_id"], player_id), fields)] += 1

    await db.flush()
    return counts


async def main() -> int:
    if not DATA_PATH.exists():
        print(f"No {DATA_PATH.name}. Run harvest.py first (on a machine the nba doesn't block) ❌")
        return 1

    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    print(f"Seeding {payload['team_tricode']} {payload['season']}, harvested {payload['harvested_at'][:19]}\n")

    # the api creates tables on startup, but seeding may well run before the server ever has
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        for label, counts in [
            ("teams", await seed_teams(db, payload["teams"])),
            ("players", await seed_players(db, payload["players"])),
            ("games", await seed_games(db, payload["games"])),
            ("stat lines", await seed_player_stats(db, payload["player_game_stats"])),
        ]:
            print(f"  {label}: {counts['created']} created, {counts['updated']} updated")
        await db.commit()

    await engine.dispose() # close the connection before asyncio.run shuts the event loop down
    print("\nSeeded ✅")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
