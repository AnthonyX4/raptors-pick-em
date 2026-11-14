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
| 15 | Docker Compose (api, poller, Postgres) | |
| 16 | AWS ECS (two services, RDS) | |

Later: the React frontend, WebSockets.

## Running the backend

All commands run from `Backend/`. You need [uv](https://docs.astral.sh/uv/) and [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Postgres).

Start Postgres in a container. The data lives on the `raptors-pgdata` volume, so it survives the container being stopped or removed. It listens on port 5433 on your machine, so it can sit next to another Postgres on 5432:

```
docker run -d --name raptors-db -p 5433:5432 -v raptors-pgdata:/var/lib/postgresql/data -e POSTGRES_USER=raptors -e POSTGRES_PASSWORD=raptors -e POSTGRES_DB=raptors postgres:17
```

After that, `docker start raptors-db` / `docker stop raptors-db` is all it needs. Then:

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
docker exec raptors-db createdb -U raptors raptors_test
TEST_DATABASE_URL=postgresql+asyncpg://raptors:raptors@localhost:5433/raptors_test uv run pytest
```

(In PowerShell: `$env:TEST_DATABASE_URL="postgresql+asyncpg://..."; uv run pytest`.)

### Moving an old SQLite database across

Before step 14 the data lived in `Backend/raptors.db`. To bring its accounts, picks and chat into Postgres with their ids unchanged, migrate an empty database and copy (no seeding needed, the games come too):

```
uv run alembic upgrade head
uv run python harvest_scripts/copy_sqlite_to_postgres.py raptors.db
```

### With Docker

The same image runs the API, the poller and the migrations. Build it from the repo root:

```
docker build -t raptors-pick-em Backend
```

Containers reach each other by name on a shared Docker network, so inside it Postgres is `raptors-db:5432`, not `localhost:5433`. Secrets come from your `.env` at run time and are never built into the image; `-e` overrides its `DATABASE_URL` for the network:

```
docker network create raptors
docker network connect raptors raptors-db
docker run --rm --network raptors --env-file Backend/.env -e DATABASE_URL=postgresql+asyncpg://raptors:raptors@raptors-db:5432/raptors raptors-pick-em alembic upgrade head
docker run -d --name api --network raptors --env-file Backend/.env -e DATABASE_URL=postgresql+asyncpg://raptors:raptors@raptors-db:5432/raptors -p 8000:8000 raptors-pick-em
docker run -d --name poller --network raptors --env-file Backend/.env -e DATABASE_URL=postgresql+asyncpg://raptors:raptors@raptors-db:5432/raptors raptors-pick-em python poller.py
```

`docker logs -f api` follows a container's output, `docker stop api poller` stops them (cleanly, on SIGTERM), and `docker rm api poller` removes them; the data stays in Postgres. `GET /health` reports whether the API can reach its database. Step 15 replaces these commands with one `docker compose up`.

To refresh the season's data from scratch (rosters included), harvest again and re-seed. Seeding updates rows in place, so it never needs the database wiped:

```
uv run python harvest_scripts/harvest.py   # must run on a normal machine, nba.com blocks cloud IPs
uv run python harvest_scripts/seed.py
```

Make an existing user an admin (there is no endpoint for this on purpose):

```
uv run python harvest_scripts/make_admin.py <email>
```
