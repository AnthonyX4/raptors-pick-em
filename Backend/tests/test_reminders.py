"""Step 12: the poller emails users who haven't finished their picks a couple of hours before tipoff."""
import asyncio
from datetime import datetime, timedelta, UTC

import pytest
from sqlalchemy import select

import email_utils
import models
import poller
from conftest import TestAsyncSession, register_and_login
from routers.pick_categories import ensure_default_categories

GAME = "0022600003" # BOS @ TOR in the games fixture, scheduled
TIPOFF = datetime(2026, 12, 1, 0, 30, tzinfo=UTC)
WINDOW_OPENS = TIPOFF - timedelta(hours=2)


def run(work):
    async def go():
        async with TestAsyncSession() as session:
            return await work(session)
    return asyncio.run(go())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # the games fixture has finished games with no box score, which a tick would try to fetch
    def refuse(*args):
        raise ConnectionError("tests never reach the nba")
    for name in ("fetch_schedule", "fetch_scoreboard", "fetch_box_score"):
        monkeypatch.setattr(poller, name, refuse)


@pytest.fixture
def categories(db, games):
    run(ensure_default_categories)
    return {c.key: c.pick_category_id for c in db.execute(select(models.PickCategory)).scalars()}


def add_user(db, name, reminders=True) -> int:
    user = models.User(username=name, email=f"{name}@example.com", password_hash="x", email_reminders=reminders)
    db.add(user)
    db.commit()
    return user.user_id


def pick(db, user_id, category_id, **answer):
    db.add(models.Pick(user_id=user_id, game_id=GAME, pick_category_id=category_id, **answer))
    db.commit()


def tick(now):
    state = poller.PollerState(last_schedule_attempt=now, last_schedule_ok=True) # no schedule refresh due
    return run(lambda db: poller.tick(db, now, state))


def reminded_at(db):
    db.expire_all()
    return db.get(models.Game, GAME).reminder_sent_at


def test_users_missing_picks_get_one_email_listing_what_is_missing(db, categories, outbox):
    nobody = add_user(db, "nobody") # no picks at all
    halfway = add_user(db, "halfway") # only the winner
    done = add_user(db, "done") # every category
    pick(db, halfway, categories["winner"], team_id=1610612761)
    for key, category_id in categories.items():
        pick(db, done, category_id, margin=5 if key == "margin" else None)

    tick(WINDOW_OPENS + timedelta(minutes=5))

    assert sorted(m["to_email"] for m in outbox) == ["halfway@example.com", "nobody@example.com"]
    halfway_mail = next(m for m in outbox if m["to_email"] == "halfway@example.com")
    assert halfway_mail["subject"].startswith("Picks lock soon: Boston Celtics at Toronto Raptors")
    assert "Margin of victory" in halfway_mail["plain_text"]
    assert "- Winner" not in halfway_mail["plain_text"] # already made
    assert "Mon Nov 30, 7:30 pm EST" in halfway_mail["plain_text"] # shown in toronto time, not utc
    assert f"/games/{GAME}" in halfway_mail["html_content"]
    assert reminded_at(db) is not None
    assert nobody and done # all three users existed


def test_reminders_are_sent_once(db, categories, outbox):
    add_user(db, "fan")
    tick(WINDOW_OPENS + timedelta(minutes=5))
    tick(WINDOW_OPENS + timedelta(minutes=20)) # a later tick, or a restarted poller
    assert len(outbox) == 1


def test_users_who_turned_reminders_off_get_nothing(db, categories, outbox):
    add_user(db, "quiet", reminders=False)
    tick(WINDOW_OPENS + timedelta(minutes=5))
    assert outbox == []
    assert reminded_at(db) is not None # the game is still done


@pytest.mark.parametrize("now", [
    WINDOW_OPENS - timedelta(minutes=1), # too early
    TIPOFF, # picks already locked, a reminder would be useless
])
def test_nothing_is_sent_outside_the_window(db, categories, outbox, now):
    add_user(db, "fan")
    tick(now)
    assert outbox == []
    assert reminded_at(db) is None


def test_a_late_poller_still_reminds_while_picks_are_open(db, categories, outbox):
    # off when the window opened, back on 10 minutes before tipoff
    add_user(db, "fan")
    tick(TIPOFF - timedelta(minutes=10))
    assert len(outbox) == 1


def test_a_postponed_game_is_not_reminded(db, categories, outbox):
    add_user(db, "fan")
    db.get(models.Game, GAME).status = "postponed"
    db.commit()
    tick(WINDOW_OPENS + timedelta(minutes=5))
    assert outbox == []


def test_a_moved_tipoff_gets_reminded_again(db, categories, outbox):
    add_user(db, "fan")
    tick(WINDOW_OPENS + timedelta(minutes=5))
    assert reminded_at(db) is not None

    new_tipoff = TIPOFF + timedelta(days=3)
    schedule = [{
        "game_id": GAME, "season": "2026-27", "tipoff_utc": new_tipoff, "status": "scheduled",
        "status_text": "7:30 pm ET", "home_team_id": 1610612761, "away_team_id": 1610612738,
        "home_score": None, "away_score": None, "arena_name": "Scotiabank Arena",
    }]
    run(lambda s: poller.apply_schedule(s, schedule))
    assert reminded_at(db) is None

    tick(new_tipoff - timedelta(hours=1))
    assert len(outbox) == 2


def test_one_failed_email_does_not_stop_the_rest(db, categories, outbox, monkeypatch):
    add_user(db, "bounces")
    add_user(db, "fan")
    fake_send = email_utils.send_email # the outbox fixture's recorder

    async def flaky(to_email, *args, **kwargs):
        if to_email.startswith("bounces"):
            raise OSError("smtp said no")
        await fake_send(to_email, *args, **kwargs)
    monkeypatch.setattr(email_utils, "send_email", flaky)

    tick(WINDOW_OPENS + timedelta(minutes=5))
    assert [m["to_email"] for m in outbox] == ["fan@example.com"]


def test_the_poller_wakes_up_for_reminders():
    game = models.Game(game_id="x", season="2026-27", status="scheduled", tipoff_utc=TIPOFF,
                       home_team_id=1, away_team_id=2)
    # 2h20m before tipoff: the reminders are 20 minutes away, the watch even further
    assert poller.next_interval([game], TIPOFF - timedelta(hours=2, minutes=20)) == poller.IDLE_INTERVAL
    assert poller.next_interval([game], TIPOFF - timedelta(hours=2, minutes=10)) == 10 * 60

    game.reminder_sent_at = TIPOFF - timedelta(hours=2) # already done: back to waiting for the watch
    assert poller.next_interval([game], TIPOFF - timedelta(hours=1)) == poller.IDLE_INTERVAL


# --- the setting, through the api ---

def test_reminders_are_on_by_default_and_can_be_turned_off(client):
    headers = register_and_login(client, "fan@example.com")
    me = client.get("/api/users/me", headers=headers).json()
    assert me["email_reminders"] is True

    response = client.patch(f"/api/users/{me['user_id']}", json={"email_reminders": False}, headers=headers)
    assert response.status_code == 200
    assert response.json()["email_reminders"] is False # no current_password needed, it's not a credential


def test_other_people_cannot_see_the_setting(client):
    headers = register_and_login(client, "fan@example.com")
    me = client.get("/api/users/me", headers=headers).json()
    assert "email_reminders" not in client.get(f"/api/users/{me['user_id']}").json()
