# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

Raptors Pick'em: users predict each Toronto Raptors game (winner, margin, stat leaders) before tipoff and chat in a per-game chat room. Backend only so far. `HANDOFF.md` has the decisions made so far and the design agreed for steps not yet built.

- `Backend/` — FastAPI + SQLAlchemy 2.x (async) on PostgreSQL (`asyncpg` driver), schema managed with Alembic, managed with `uv`, Python >=3.14. Tests run on SQLite (`aiosqlite`) by default and on Postgres when `TEST_DATABASE_URL` is set.
- Built step by step, the plan and current state are the table in `README.md`. Keep that table up to date when a step is finished.
- Forked from the account system of the sneaker store project, so the conventions below match that codebase.

## Commands (run from `Backend/`)

- Install deps: `uv sync`
- Database: the `db` service in `docker-compose.yml` (repo root), Postgres 17 on port 5433, data on the `raptors-pgdata` volume. `docker compose up -d db` for `uv run` development; `psql`: `docker compose exec db psql -U raptors`.
- Migrations: `uv run alembic upgrade head`. After changing a model: `uv run alembic revision --autogenerate -m "..."`, read the file in `alembic/versions/`, then upgrade. `uv run alembic check` fails on drift between models and migrations; CI runs it.
- Dev server: `uv run fastapi dev main.py` (port 8000). Needs a `.env` with `DATABASE_URL`, see `.env.example`.
- Tests: `uv run pytest`. They need no `.env`: `conftest.py` sets `SECRET_KEY`/`S3_BUCKET_NAME`/`DATABASE_URL`, and the autouse `s3_bucket` and `outbox` fixtures replace S3 and email with in-memory fakes. A temp SQLite file by default; `TEST_DATABASE_URL=postgresql+asyncpg://.../raptors_test` runs them on Postgres (the name must end in `_test`, every test drops all tables). CI always uses Postgres. Tests build tables with `create_all`, not migrations.
- Grant admin: `uv run python harvest_scripts/make_admin.py <email> [--revoke]` (deliberately no endpoint).
- `.github/workflows/nba-reachability.yml` — manual GitHub Action checking the cdn.nba.com feeds are reachable from a datacenter IP, which the production poller depends on.
- Verify the real bucket: `uv run check_s3.py`.
- Poller: `uv run python poller.py` (or `--once`). A separate process from the api; run exactly one.
- Docker: `docker compose up -d --build` from the repo root runs `db`, a one-shot `migrate` (`alembic upgrade head`), then `api` (health check on `/health`) and `poller`, all from one image (`Backend/Dockerfile`: the api by default, other commands for the rest). No data in the image: secrets from `Backend/.env` via `env_file`, and Compose overrides `DATABASE_URL` to `db:5432`. Seed a fresh volume with `docker compose run --rm --no-deps api python harvest_scripts/seed.py`. Don't run the Compose api/poller and `uv run` ones at the same time (one port 8000, exactly one poller). `.github/workflows/backend-ci.yml` checks the migrations, runs the tests on Postgres and brings the Compose file up on every backend push.
- Old SQLite data: `uv run python harvest_scripts/copy_sqlite_to_postgres.py raptors.db` copies a pre-step-14 database into an empty migrated Postgres, ids and sequences intact.
- `.github/workflows/capture-nba-samples.yml` saves real cdn payloads (also printed into the job log, since artifact downloads may be unreachable); `poller-smoke.yml` runs the real poller once against the live cdn on a fresh seeded database. Both manual.
- Load NBA data: `uv run python harvest_scripts/seed.py` (reads the committed `nba_data.json`). Refresh it with `harvest_scripts/harvest.py`, which only works off-cloud.

## Architecture

- `main.py` — app entrypoint. The `lifespan` refuses to start if the tables don't exist (they come only from Alembic, never `create_all`), then inserts the default pick categories. CORS for `localhost:5173` and `localhost:3000`. Routers are mounted here with their prefix and tag. `GET /` is a cheap health message that touches no database (for a load balancer's routine check); `GET /health` runs `SELECT 1` and is a 503 without a database. A middleware adds security headers to every response.
- `config.py` — `Settings` (pydantic-settings) read from `.env`. `app_name` is the display name used in the docs and emails.
- `database.py` — async engine on `settings.database_url` (required, no default; `pool_pre_ping`), `AsyncSessionLocal` (`expire_on_commit=False`), the `get_db()` dependency, and `has_table()`, which the api, poller and seed use to fail with "run alembic upgrade head" on an unmigrated database.
- `alembic/` + `alembic.ini` — migrations. `env.py` takes the url from `settings.database_url` (the ini has none), imports `models` for autogenerate, and renders `UTCDateTime` as plain `sa.DateTime(timezone=True)` so migration files never import the models.
- `models.py` — `User`, `PasswordResetToken`, `PickCategory`, `Pick`, `Message`, `MessageLike`, `Mute`, and the NBA data: `Team`, `Player`, `Game`, `PlayerGameStat` (`Mapped`/`mapped_column` style). NBA rows use the NBA's own ids as primary keys, which is what makes re-seeding an update rather than a duplicate. Every datetime column is `UTCDateTime`, never a plain `DateTime`.
- `schemas.py` — Pydantic v2 models with `ConfigDict(from_attributes=True)`. Paginated lists subclass `PaginatedResponse`.
- `auth.py` — argon2 hashing (`pwdlib`), JWT (`pyjwt`), the `CurrentUser` / `AdminUser` dependencies. A deleted user's still-unexpired token stops working at the next request, because the user is looked up every time. `OptionalUser` is the same check for public pages that show more to a logged-in reader: None without a token, still a 401 with an invalid one.
- `routers/users.py` → `/api/users`: register, `POST /token` login (OAuth2 form, `username` = email), `GET /me`, `PATCH /me/password`, get/patch/delete by id (path id must match the token's user), profile picture upload/delete, forgot/reset password.
- `routers/admins.py` → `/api/admin`: router-level admin dependency. List users, get one, delete one (refuses admins). Moderation: delete any message, `PUT`/`DELETE /users/{id}/mute` (timed, refuses admins), `GET /mutes` (active ones).
- `routers/games.py` → `/api/games`: public. Paginated list, oldest first, filtered by `?season=`, `?status=`, `?opponent=` (a tricode, 400 if unknown), `?upcoming=` (true: not final, false: final). Detail includes the box score, highest scorer first. Every game carries `picks_open`, set by `game_response()` from `routers.picks.picks_open` so it can't disagree with the lock.
- `routers/players.py` → `/api/players`: public. Paginated list by name, filtered by `?team=` and `?search=`, and get by id.
- `routers/pick_categories.py` → `/api/pick-categories`: public list of active categories in form order. Also holds `DEFAULT_CATEGORIES` and `ensure_default_categories`, which `main.py`'s lifespan runs at startup (insert-only, never overwrites an admin's edits). Admins manage categories through `/api/admin/pick-categories` (list all, create, patch; no delete, only deactivate).
- `routers/picks.py` → `/api/picks`: `POST` make a pick, `PATCH`/`DELETE /{pick_id}` edit or withdraw your own (both bodies have one Swagger example per category kind), `GET /me` your picks, `GET ?game_id=` everyone's once the game has started. A pick fills in exactly one answer field, chosen by its category's kind (`team_id` winner, `margin`, `player_id` stat leader). Open, revealed, the winner-first rule and why someone else's pick is a 404 are explained in `HANDOFF.md`. Tests move time by monkeypatching `routers.picks.utcnow`.
- `harvest_scripts/harvest.py` — pulls teams (offline dataset), the followed team's schedule, every roster on that schedule, and finished games' box scores into `nba_data.json`, already shaped like the models. Translates the NBA's integer game status into `GameStatus` so nothing downstream sees it.
- `harvest_scripts/seed.py` — upserts `nba_data.json`. Creates a `Player` for anyone in a box score but on no roster.
- `scoring.py` — `score_game(db, game, force=False)` scores every pick for a final game from its stored box score and sets `Game.scored_at`. Kept out of the routers because the step 11 poller will call it too, so it raises `ScoringError`, not `HTTPException`. Skips a scored game unless forced; a forced rescore overwrites points. Admins trigger it with `POST /api/admin/games/{game_id}/score?force=`.
- `routers/leaderboard.py` → `/api/leaderboard` (`?season=`, all time without it) and `/api/leaderboard/games/{game_id}`: public, derived per request as `SUM(points_awarded)` over scored picks, ranked with a SQL `rank()` window function so tied totals share a rank and ranks stay true across pages.
- `poller.py` — step 11, a worker process. Each tick: daily schedule refresh, pick reminder emails (step 12, `send_reminders`, at most once per game via `Game.reminder_sent_at`), live scoreboard for games on or about to start, then box score + `scoring.score_game` for finished unscored games (oldest first). Sleeps 30s while a game is watched, otherwise until the next watch or reminder window (at most 15 min). `fetch_*` are the only network calls (nba_api in a thread; tests replace them); `parse_*` translate the cdn's formats and are tested against real payloads in `tests/fixtures/nba/`; `apply_schedule`, `apply_live`, `ingest_box_score` write. A failed fetch is logged and retried, never fatal. `tick(db, now, state)` takes the time as an argument, so tests drive it directly.
- `routers/messages.py` → mounted at `/api`: `GET`/`POST /games/{game_id}/messages` (read is public; post needs the room open and the user not muted), `PATCH`/`DELETE /messages/{id}` (author only; edit within 5 minutes and not muted, delete any time), `PUT`/`DELETE /messages/{id}/like` (idempotent). Chat pages by cursor (`?before=`/`?after=` message id, oldest first, `has_older`/`has_newer`), deliberately not skip/limit. A room is open from 24h before tipoff until 3h after `Game.final_at`; postponed, or final with no `final_at`, is closed. Rules live in `config.py` (`chat_*`, `message_*`). Tests move time by monkeypatching `routers.messages.utcnow`, which mutes use too.
- `image_utils.py` — profile pictures live in S3 under `profile_pics/`. Pillow and boto3 are sync, so routes call them through `run_in_threadpool`.
- `email_utils.py` — async SMTP (`aiosmtplib`), the password reset and pick reminder emails (Jinja templates in `templates/email/`). `format_tipoff` shows times in `settings.display_timezone`. Users opt out of reminders with `User.email_reminders`.

### Deleting users

`delete_user_account` in `routers/users.py` removes the row outright. There is no soft delete: it was removed on purpose to keep the code simple, so a deleted user's row is gone and their token stops working at the next request (`get_current_user` looks the user up every time).

What goes with the account: picks (cascade, `User.picks`), likes and any mute. What stays: chat messages, with `user_id` set to None, which the API returns as `author: null` and the frontend shows as "[deleted]", so conversations still read. All done in `delete_user_account`. Don't reintroduce `deleted_at` by reflex.

## Conventions

- Handlers and dependencies are `async def`; inject the session with `Annotated[AsyncSession, Depends(get_db)]` and `await` `execute`/`commit`/`refresh`/`flush`/`delete` (`db.add` is not awaited).
- New resources get their own file under `routers/`, with the prefix and tag set in `main.py`.
- Async sessions can't lazy load: eager load what the response schema needs with `selectinload(...)`, or `await db.refresh(obj, attribute_names=[...])` after a commit.
- List endpoints take `?skip=` and `?limit=` and return `{<items key>, total, skip, limit, has_more}`. Each list query needs an `order_by`, and its count query must use the same filters.
- Sync or CPU-bound work (Pillow, boto3, and later `nba_api`, which uses `requests`) goes through `run_in_threadpool`.
- Never call `nba_api` from a request handler: stats.nba.com is slow, rate limited and blocks cloud provider IPs. NBA data is loaded into the database by scripts and background tasks, and endpoints read only from the database.
- Fetch cdn.nba.com through `nba_api`'s live endpoints or with `NBALiveHTTP.headers`. Its bot protection refuses a bare client such as `curl` with a 403, even where `nba_api` gets through (see `HANDOFF.md`).
- Comments are lowercase, explain why rather than what, and sit at the end of the line or just above the code.
- Datetime columns use `UTCDateTime` (models.py): a `timestamptz` on Postgres. It's a no-op there but keeps the SQLite test database returning aware datetimes; a naive datetime serializes without an offset (a browser reads it as local time) and can't be compared with `datetime.now(UTC)`.
- Schema changes go through a new Alembic migration, never by editing an applied one; `sqlite_autoincrement` on `users`/`messages` only matters to the SQLite test database (Postgres sequences never reuse ids).
- The followed team is `settings.team_tricode` ("TOR"), never hardcoded.
- The chat's schemas are `ChatMessage*`: `MessageResponse` is the generic `{"message": ...}` reply used by the health check and password reset.
- Anything that writes a game's status goes through `schemas.can_move_status`: never backwards (except scheduled <-> postponed). The seed script, the scoreboard and the schedule refresh all write games and aren't equally fresh.

## Known issues

- `hash_password`/`verify_password` are CPU-bound and called directly from async routes. Fine at this scale; wrap in `run_in_threadpool` if it matters.
