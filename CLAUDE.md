# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

Raptors Pick'em: users predict each Toronto Raptors game (winner, margin, stat leaders) before tipoff and chat in a per-game chatroom. Backend only so far.

- `Backend/` — FastAPI + SQLAlchemy 2.x (async, `aiosqlite` driver), managed with `uv`, Python >=3.14.
- Built step by step, the plan and current state are the table in `README.md`. Keep that table up to date when a step is finished.
- Forked from the account system of the sneaker store project, so the conventions below match that codebase.

## Commands (run from `Backend/`)

- Install deps: `uv sync`
- Dev server: `uv run fastapi dev main.py` (port 8000). Needs a `.env`, see `.env.example`.
- Tests: `uv run pytest`. They need no `.env`: `conftest.py` sets `SECRET_KEY`/`S3_BUCKET_NAME`, and the autouse `s3_bucket` and `outbox` fixtures replace S3 and email with in-memory fakes.
- Grant admin: `uv run python harvest_scripts/make_admin.py <email> [--revoke]` (deliberately no endpoint).
- Verify the real bucket: `uv run check_s3.py`.

## Architecture

- `main.py` — app entrypoint. Creates tables in the `lifespan` startup with `Base.metadata.create_all` (**no Alembic**: changing a model means deleting `raptors.db`). CORS for `localhost:5173` and `localhost:3000`. Routers are mounted here with their prefix and tag. `GET /` is a placeholder health message until games exist.
- `config.py` — `Settings` (pydantic-settings) read from `.env`. `app_name` is the display name used in the docs and emails.
- `database.py` — async engine on `raptors.db` (anchored to `Backend/`), `AsyncSessionLocal` (`expire_on_commit=False`), the `get_db()` dependency.
- `models.py` — `User`, `PasswordResetToken` (`Mapped`/`mapped_column` style).
- `schemas.py` — Pydantic v2 models with `ConfigDict(from_attributes=True)`. Paginated lists subclass `PaginatedResponse`.
- `auth.py` — argon2 hashing (`pwdlib`), JWT (`pyjwt`), the `CurrentUser` / `AdminUser` dependencies. Soft-deleted users are rejected even with a valid token.
- `routers/users.py` → `/api/users`: register, `POST /token` login (OAuth2 form, `username` = email), `GET /me`, `PATCH /me/password`, get/patch/delete by id (path id must match the token's user), profile picture upload/delete, forgot/reset password.
- `routers/admins.py` → `/api/admin`: router-level admin dependency. List users, get one, delete one (refuses admins).
- `image_utils.py` — profile pictures live in S3 under `profile_pics/`. Pillow and boto3 are sync, so routes call them through `run_in_threadpool`.
- `email_utils.py` — async SMTP (`aiosmtplib`) and the password reset email (Jinja template in `templates/email/`).

### Deleting users

`delete_user_account` in `routers/users.py` removes the row outright. There is no soft delete: it was removed on purpose to keep the code simple, so a deleted user's row is gone and their token stops working at the next request (`get_current_user` looks the user up every time).

**This is a decision to revisit when picks and chat messages exist.** Rows that other users can still see after an account is gone (a pick on a leaderboard, a message in an old game chat) cannot point at a missing user. Pick one of these then, rather than reintroducing `deleted_at` by reflex: cascade delete the user's picks and messages along with them, or make the author column nullable and render a missing author as "[deleted]".

## Conventions

- Handlers and dependencies are `async def`; inject the session with `Annotated[AsyncSession, Depends(get_db)]` and `await` `execute`/`commit`/`refresh`/`flush`/`delete` (`db.add` is not awaited).
- New resources get their own file under `routers/`, with the prefix and tag set in `main.py`.
- Async sessions can't lazy load: eager load what the response schema needs with `selectinload(...)`, or `await db.refresh(obj, attribute_names=[...])` after a commit.
- List endpoints take `?skip=` and `?limit=` and return `{<items key>, total, skip, limit, has_more}`. Each list query needs an `order_by`, and its count query must use the same filters.
- Sync or CPU-bound work (Pillow, boto3, and later `nba_api`, which uses `requests`) goes through `run_in_threadpool`.
- Never call `nba_api` from a request handler: stats.nba.com is slow, rate limited and blocks cloud provider IPs. NBA data is loaded into the database by scripts and background tasks, and endpoints read only from the database.
- Comments are lowercase, explain why rather than what, and sit at the end of the line or just above the code.

## Known issues

- `hash_password`/`verify_password` are CPU-bound and called directly from async routes. Fine at this scale; wrap in `run_in_threadpool` if it matters.
