import os
import sys
import tempfile
from datetime import datetime, UTC
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# config.py reads its settings on import and has no default for these two, so a fresh clone with no .env can still run the tests
# real environment variables win over .env, so the tests also never see the real key or bucket name
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR)) # so main/models/database are importable when pytest runs from anywhere

import database

# swap in a throwaway database BEFORE main is imported, main's lifespan create_all must never touch raptors.db
# it's a temp file rather than in-memory so two engines can share it:
#   - the app gets an async (aiosqlite) engine, same as production
#   - fixtures get a plain sync engine, so tests can set up and inspect data without an event loop
TEST_DB_DIR = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
TEST_DB_PATH = Path(TEST_DB_DIR.name) / "test.db"

# NullPool opens a fresh connection per session, so no connection is reused across the event loops
# TestClient and asyncio.run create (a pooled aiosqlite connection is tied to the loop that opened it)
test_async_engine = create_async_engine(
    f"sqlite+aiosqlite:///{TEST_DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)
database.engine = test_async_engine
TestAsyncSession = async_sessionmaker(test_async_engine, class_=AsyncSession, expire_on_commit=False)

test_sync_engine = create_engine(f"sqlite:///{TEST_DB_PATH}", poolclass=NullPool)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_sync_engine)

import main
import models
import email_utils
import image_utils

PASSWORD = "password123"


async def get_test_db():
    async with TestAsyncSession() as db:
        yield db


@pytest.fixture
def db():
    # fresh tables for every test so tests can't leak data into each other
    database.Base.metadata.create_all(bind=test_sync_engine)
    with TestSession() as session:
        yield session
    database.Base.metadata.drop_all(bind=test_sync_engine)


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    # every email a test triggers is recorded here instead of sent, .env has real smtp credentials
    sent = []

    async def fake_send_email(to_email, subject, plain_text, html_content=None):
        sent.append({"to_email": to_email, "subject": subject, "plain_text": plain_text, "html_content": html_content})

    monkeypatch.setattr(email_utils, "send_email", fake_send_email)
    return sent


@pytest.fixture(autouse=True)
def s3_bucket(monkeypatch):
    # a dict standing in for the bucket ({key: bytes}), .env has real AWS credentials and tests must never use them
    bucket = {}

    def fake_upload(file_bytes, key):
        bucket[key] = file_bytes

    def fake_delete(key):
        bucket.pop(key, None) # like S3, deleting a missing key isn't an error

    monkeypatch.setattr(image_utils, "_upload_to_s3", fake_upload)
    monkeypatch.setattr(image_utils, "_delete_from_s3", fake_delete)
    return bucket


@pytest.fixture
def client(db):
    main.app.dependency_overrides[database.get_db] = get_test_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


# --- NBA fixtures -----------------------------------------------------------
# a miniature season: three teams, four games (one in a previous season, one not yet played)
# and a box score for the first game. small enough to assert on exactly, shaped like real data

TOR, BOS, MIA = 1610612761, 1610612738, 1610612748


@pytest.fixture
def teams(db):
    rows = [
        models.Team(team_id=TOR, tricode="TOR", city="Toronto", nickname="Raptors", full_name="Toronto Raptors"),
        models.Team(team_id=BOS, tricode="BOS", city="Boston", nickname="Celtics", full_name="Boston Celtics"),
        models.Team(team_id=MIA, tricode="MIA", city="Miami", nickname="Heat", full_name="Miami Heat"),
    ]
    db.add_all(rows)
    db.commit()
    return {team.tricode: team.team_id for team in rows}


@pytest.fixture
def games(db, teams):
    """Returns the game ids in the order the api should list them, oldest first."""
    rows = [
        models.Game(
            game_id="0022500001", season="2025-26", tipoff_utc=datetime(2026, 1, 5, 0, 0, tzinfo=UTC),
            status="final", status_text="Final", home_team_id=TOR, away_team_id=MIA,
            home_score=101, away_score=99, arena_name="Scotiabank Arena",
        ),
        models.Game(
            game_id="0022600001", season="2026-27", tipoff_utc=datetime(2026, 10, 22, 23, 30, tzinfo=UTC),
            status="final", status_text="Final", home_team_id=TOR, away_team_id=BOS,
            home_score=115, away_score=108, arena_name="Scotiabank Arena",
        ),
        models.Game(
            game_id="0022600002", season="2026-27", tipoff_utc=datetime(2026, 10, 25, 0, 0, tzinfo=UTC),
            status="final", status_text="Final", home_team_id=MIA, away_team_id=TOR,
            home_score=97, away_score=104, arena_name="Kaseya Center",
        ),
        models.Game(
            game_id="0022600003", season="2026-27", tipoff_utc=datetime(2026, 12, 1, 0, 30, tzinfo=UTC),
            status="scheduled", status_text="7:30 pm ET", home_team_id=TOR, away_team_id=BOS,
            arena_name="Scotiabank Arena",
        ),
    ]
    db.add_all(rows)
    db.commit()
    return [game.game_id for game in rows]


@pytest.fixture
def players(db, teams):
    rows = [
        models.Player(player_id=1, full_name="Scottie Barnes", first_name="Scottie", last_name="Barnes",
                      team_id=TOR, jersey_number="4", position="F"),
        models.Player(player_id=2, full_name="Immanuel Quickley", first_name="Immanuel", last_name="Quickley",
                      team_id=TOR, jersey_number="5", position="G"),
        models.Player(player_id=3, full_name="Jayson Tatum", first_name="Jayson", last_name="Tatum",
                      team_id=BOS, jersey_number="0", position="F"),
        models.Player(player_id=4, full_name="Free Agent", first_name="Free", last_name="Agent",
                      team_id=None), # in an old box score, on nobody's roster now
    ]
    db.add_all(rows)
    db.commit()
    return [player.player_id for player in rows]


@pytest.fixture
def box_score(db, games, players):
    """The first 2026-27 game's box score. Deliberately not in points order."""
    db.add_all([
        models.PlayerGameStat(game_id="0022600001", player_id=1, team_id=TOR, minutes="34:12",
                              points=22, rebounds_offensive=2, rebounds_defensive=7, rebounds_total=9,
                              assists=5, steals=2, blocks=1, turnovers=3, three_pointers_made=2),
        models.PlayerGameStat(game_id="0022600001", player_id=3, team_id=BOS, minutes="36:40",
                              points=30, rebounds_offensive=1, rebounds_defensive=5, rebounds_total=6,
                              assists=4, steals=1, blocks=0, turnovers=2, three_pointers_made=4),
        models.PlayerGameStat(game_id="0022600001", player_id=2, team_id=TOR, minutes=None,
                              comment="DNP - Coach's Decision"),
    ])
    db.commit()


def register_and_login(client, email: str, username: str | None = None) -> dict:
    """Create a user through the API and return headers carrying their token."""
    username = username or email.split("@")[0] # "customer@example.com" registers as "customer"
    response = client.post("/api/users", json={"username": username, "email": email, "password": PASSWORD})
    assert response.status_code == 201
    response = client.post("/api/users/token", data={"username": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def user_headers(client):
    return register_and_login(client, "customer@example.com")


@pytest.fixture
def admin_headers(client, db):
    headers = register_and_login(client, "admin@example.com")
    # promoted directly in the db, the same way make_admin.py does, the api has no way to do this
    admin = db.execute(select(models.User).where(models.User.email == "admin@example.com")).scalars().one()
    admin.is_admin = True
    db.commit()
    return headers
