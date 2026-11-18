# Raptors Pick'em

A fan site built around each Toronto Raptors game: predict the result and stat leaders before tipoff, then talk about the game in its own chatroom.

The backend is a FastAPI + SQLAlchemy (async) API. It started from the account system of my [sneaker store project](https://github.com/9JB9/ecommercePlatformFASTAPI) and is being built one step at a time.

## Status

| Step | What | State |
|---|---|---|
| 1 | Project skeleton: accounts, JWT auth, password reset emails, profile pictures on S3, admin users | Done |
| 2 | NBA data models (teams, players, games, box scores) | Done |
| 3 | Harvest and seed scripts (nba_api) | Done |
| 4 | Games and players routers | Done |
| 4.5 | Check the NBA's CDN is reachable from a datacenter IP | Done: reachable with `nba_api`'s client, `curl` is refused |
| 5 | Pick categories | Done |
| 6 | Picks (locked at tipoff) | Done |
| 7 | Results and scoring | Done |
| 8 | Leaderboard | Done |
| 9 | Game chat messages | Done |
| 10 | Reactions and moderation | Done |
| 11 | Game-night score polling | Done (built before 9 and 10) |
| 12 | Reminder emails | Done: sent by the poller 2h before tipoff to users missing picks |
| 13 | Docker image | Done: one image runs both the API and the poller, built and smoke-tested in CI |
| 14 | Postgres and Alembic | Done: asyncpg, migrations checked in CI, tests run on Postgres |
| 15 | Docker Compose (api, poller, Postgres) | Done: `docker compose up` runs db, migrations, api and poller; tested in CI |
| 16 | React frontend (design and build order in `frontend/SPEC.md`) | Done |
| 16.0 | Backend prep: 7-day tokens, `is_admin` on `/me`, `editable_until` on chat messages | Done |
| 16.1 | Scaffold: Vite + TypeScript, Tailwind, shadcn, React Router, TanStack Query, dev proxy, generated API types | Done |
| 16.2 | Auth: login, register, forgot and reset password, protected routes | Done |
| 16.3 | Games: schedule, game page with live score, box score, home page | Done |
| 16.4 | Picks: form built from the categories, locked and scored states, everyone's picks after tipoff | Done |
| 16.5 | Chat: polling, scroll back, post, edit, delete, like, admin moderation | Done |
| 16.6 | Leaderboards | Done |
| 16.7 | Profile and settings | Done |
| 16.8 | Frontend in Docker (nginx) and Compose | Done |
| 16.9 | Polish: loading, empty and error states, accessibility, code splitting, README | Done |
| 17 | Deploy (host to be chosen) | |

Later: WebSockets for the chat.

## What it looks like

A React single-page app (Vite, TypeScript, Tailwind, shadcn/ui) over the API. Everything below is on the site, in a dark Raptors-red theme:

- **Home**: the live game, or the next one with a countdown to tipoff.
- **Games**: the season's schedule, upcoming and finished.
- **A game**: the score and clock (live), your picks (open until tipoff, then everyone's), the box score once it's played, the game's own standings once it's scored, and its chat room beside it.
- **Leaderboard**: season standings, with ties sharing a rank.
- **Account**: sign up, log in, reset a password by email, a profile, and settings (username, email, password, picture, reminder emails, delete account).

The frontend never decides a rule the API already decides (whether picks are open, whether the chat room is open, how long a message can be edited): it reads those from the API's responses. `frontend/CLAUDE.md` describes the code and `frontend/SPEC.md` the design it was built from.

## Running the frontend

Needs [Node](https://nodejs.org/) 22 and the backend running on port 8000 (see below). From `frontend/`:

```
npm install
npm run dev        # http://localhost:5173, forwards /api and /static to the backend on port 8000
npm test           # the logic tests (Vitest), no browser needed
npm run build      # type check, then the production build into dist/
npm run lint
npm run gen:api    # regenerate src/types/api.d.ts from the running backend, after a backend schema change
```

Or without Node at all, the whole app from the repo root: `docker compose up -d --build` serves it on http://localhost:8080 (see "Everything in Docker" below).

## Running the backend

All commands run from `Backend/`. You need [uv](https://docs.astral.sh/uv/) and [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Postgres).

Postgres runs in Docker, defined in `docker-compose.yml` at the repo root. Its data lives on the `raptors-pgdata` volume, so it survives the container being stopped or removed. It listens on port 5433 on your machine, so it can sit next to another Postgres on 5432. From the repo root:

```
docker compose up -d db      # just the database, for running the app with uv (below)
docker compose stop db       # stop it, the data stays
```

Then, from `Backend/`:

```
uv sync
cp .env.example .env                       # then fill in the values, DATABASE_URL already matches the container
uv run alembic upgrade head                # creates the tables
uv run python harvest_scripts/seed.py      # loads nba_data.json
uv run fastapi dev main.py                 # http://localhost:8000, docs at /docs
uv run pytest                              # needs no .env, S3 and email are faked
```

To keep the database in step with real games (live scores, box scores and scoring when a game ends, the daily schedule refresh, pick reminder emails), run the poller in a second terminal. Run exactly one:

```
uv run python poller.py           # until Ctrl+C
uv run python poller.py --once    # a single pass
```

### Changing the schema

Tables are created and changed only by Alembic migrations in `alembic/versions/`, never by the app. After changing a model:

```
uv run alembic revision --autogenerate -m "add x to games"   # writes the next migration, read it before applying
uv run alembic upgrade head                                  # applies it
uv run alembic downgrade -1                                  # undoes the last one
uv run alembic check                                         # fails if the models and the migrations disagree
```

### Tests on Postgres

`uv run pytest` uses a throwaway SQLite file by default. CI runs the same suite on Postgres, and so can you, against a database made only for tests (every test drops all its tables):

```
docker compose exec db createdb -U raptors raptors_test
TEST_DATABASE_URL=postgresql+asyncpg://raptors:raptors@localhost:5433/raptors_test uv run pytest
```

(In PowerShell: `$env:TEST_DATABASE_URL="postgresql+asyncpg://..."; uv run pytest`.)

### Moving an old SQLite database across

Before step 14 the data lived in `Backend/raptors.db`. To bring its accounts, picks and chat into Postgres with their ids unchanged, migrate an empty database and copy (no seeding needed, the games come too):

```
uv run alembic upgrade head
uv run python harvest_scripts/copy_sqlite_to_postgres.py raptors.db
```

### Everything in Docker (Compose)

`docker-compose.yml` runs the whole app: Postgres, a one-shot `migrate` service that runs `alembic upgrade head`, then the API and the poller (one image), which only start once the migration succeeded, and the `frontend` (its own image: the built React app behind nginx), which starts once the API is healthy. Secrets come from `Backend/.env` at run time (never built into the image); Compose swaps its `DATABASE_URL` for the `db` service's address and `FRONTEND_URL` for `http://localhost:8080`, so emails link to the frontend service. From the repo root:

```
docker compose up -d --build     # build the images and start everything: the app on http://localhost:8080, the API docs on http://localhost:8000/docs
docker compose ps                # db, api and frontend should say (healthy), migrate "Exited (0)"
docker compose logs -f poller    # follow a service's output
docker compose down              # stop and remove the containers, the data stays on the volume
```

On a brand new volume, seed once the API is up (the poller retries until there's data):

```
docker compose run --rm --no-deps api python harvest_scripts/seed.py
```

The frontend on port 8080 is the same app as `npm run dev` on 5173 (the dev server proxies `/api` and `/static` to port 8000, nginx proxies them to the `api` service), so the browser is on one origin either way. Run the backend either with Compose or with `uv run`, not both at once: they'd both want port 8000, and there must only ever be one poller. `docker compose up -d db` alone gives `uv run` its database.

To refresh the season's data from scratch (rosters included), harvest again and re-seed. Seeding updates rows in place, so it never needs the database wiped:

```
uv run python harvest_scripts/harvest.py   # must run on a normal machine, nba.com blocks cloud IPs
uv run python harvest_scripts/seed.py
```

Make an existing user an admin (there is no endpoint for this on purpose):

```
uv run python harvest_scripts/make_admin.py <email>
```
