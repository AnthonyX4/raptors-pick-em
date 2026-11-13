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
| 4.5 | Check the NBA's CDN is reachable from a datacenter IP | Done: run the workflow once the repo is on GitHub |
| 5 | Pick categories | Done |
| 6 | Picks (locked at tipoff) | Done |
| 7 | Results and scoring | Next |
| 8 | Leaderboard | |
| 9 | Game chat messages | |
| 10 | Reactions and moderation | |
| 11 | Game-night score polling | |
| 12 | Reminder emails | |

Later: Docker, Postgres, Docker Compose, AWS ECS, WebSockets.

## Running the backend

All commands run from `Backend/`. You need [uv](https://docs.astral.sh/uv/).

```
uv sync
cp .env.example .env                       # then fill in the values
uv run python harvest_scripts/seed.py      # loads nba_data.json into raptors.db
uv run fastapi dev main.py                 # http://localhost:8000, docs at /docs
uv run pytest                              # needs no .env, S3 and email are faked
```

To refresh the season's data (scores, rosters, new box scores), harvest again and re-seed. Seeding updates rows in place, so it never needs the database wiped:

```
uv run python harvest_scripts/harvest.py   # must run on a normal machine, nba.com blocks cloud IPs
uv run python harvest_scripts/seed.py
```

Make an existing user an admin (there is no endpoint for this on purpose):

```
uv run python harvest_scripts/make_admin.py <email>
```
