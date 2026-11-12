# Handoff

Written 2026-11-12, at the end of step 1. Read this with `README.md` (the step plan) and `CLAUDE.md` (conventions and architecture). This file holds what those two don't: the decisions already made and why, the design agreed for steps not yet built, and what's still open.

## Where things stand

- Step 1 is done: accounts, JWT auth, password reset emails, profile pictures on S3, admin user routes.
- 75 tests pass (`cd Backend && uv run pytest`).
- Three commits on `main`, local only. No remote is configured yet.
- Steps 2 to 12 are not started. Nothing NBA-related exists: the database has `users` and `password_reset_tokens` and nothing else.

## Decisions already made

**The project is Raptors Pick'em with a per-game chatroom.** Users predict the result and stat leaders before tipoff; each game also has its own chat. Earlier ideas considered and set aside: a Poeltl-style trivia game and a shot-chart match game (both too thin on CRUD to carry the project), and a salary-cap fantasy roster (needs league-wide stats, which the NBA blocks from cloud IPs).

**`nba_api` is never called from a request handler.** stats.nba.com is slow, rate limited, and silently drops connections from AWS, GCP and Azure IPs, so a live call would work locally and time out in production. NBA data reaches the database through scripts and a background poller; endpoints only ever read the database. The live endpoints on `cdn.nba.com` (scoreboard, box scores) have no such blocking and do work from AWS, which is what the step 11 poller will use. Schedule and roster harvesting runs from a laptop.

**No soft delete.** Removed deliberately in commit `c9a578b`; deleting a user removes the row. When picks and chat messages exist, rows that others can still see cannot point at a missing user. Decide then between cascading the user's picks and messages, or making the author column nullable and rendering "[deleted]". Do not reintroduce `deleted_at` by reflex.

**`sqlite_autoincrement` on `User`.** A token carries only `{"sub": "<user_id>"}` and stays valid until it expires, so a reused id would let a deleted user's token authenticate as a new account. SQLite reuses the largest freed id without `AUTOINCREMENT`. Postgres sequences already behave correctly, so this is a SQLite-stage fix; `tests/test_tokens.py` is what keeps it true after the migration.

**No Alembic.** Tables are created from the models at startup, so a model change means deleting `Backend/raptors.db`. Revisit when moving to Postgres.

## Design agreed for later steps

Not built yet. These were worked out in discussion and should be followed unless there's a reason to change.

**Pick categories are data, not code** (step 5). One `PickCategory` row per question (winner, margin, points leader, rebounds leader, assists leader, steals leader), each with an answer type and a `points` weight. Adding a question is an admin action, not a code change. Scoring is one generic function over all "leader" categories. Only winner is required; the rest are optional bonus points, so a user isn't filling in ten fields 82 times a season.

**Weights are inverse to predictability.** Winner is the easiest (~60-65% hit rate) and should be worth the least; steals and blocks leaders are near coin flips and worth the most. Rather than guessing, calibrate from the harvested box scores once step 3 is done: measure how often the obvious pick was right per category and set points ≈ 1 ÷ hit rate. Numeric categories (margin) award a fraction of their `points` by closeness; player and team categories are all-or-nothing. Treat `points` as the maximum.

**Each pick stores the points it earned**, the way `OrderItem.fixed_price` did in the sneaker store. A pick was judged against one box score and that verdict shouldn't silently change later. It also means retuning a weight mid-season doesn't rewrite past results.

**The leaderboard is derived, never stored.** `SUM(points_awarded) GROUP BY user_id`, computed per request. No running total to drift out of sync, and re-scoring a corrected game fixes the standings automatically. Cache in Redis later if it ever matters.

**Scoring must be idempotent** (step 7). Running it twice on the same game must not double anyone's points. A `scored_at` timestamp on `Game` that the job skips unless passed a `force` flag. Build the admin trigger endpoint first so the job is testable against a seeded finished game; step 11 then calls the same function from the poller, and the endpoint stays as a manual re-run.

**Chatrooms are scoped by game, not reset.** Each game has its own room keyed by `game_id`, so "tonight's chat" is just the frontend pointing at today's game and old rooms stay readable. Rooms follow game status: open before, open during, read-only a few hours after.

**Chat uses cursor pagination**, `?before=<message_id>&limit=50`, not `skip`/`limit`. New messages shift every offset, so offset paging repeats rows in a live feed. Games and leaderboards keep `skip`/`limit`.

**Polling before WebSockets.** Build chat and live scores on plain REST with the browser re-requesting on a timer; it is a complete, testable feature. Add WebSockets afterwards as an upgrade, keeping `POST` for sending. Once more than one backend container runs, a message posted to container A won't reach clients on container B, which is where Redis pub/sub earns its place.

**One poller, not one per container** (step 11). A loop started in `main.py`'s `lifespan` runs once per container, so two containers on ECS would double-poll and race. Either run it as a separate single-task service or take a lock in Redis. Note it in the code even while running a single container.

## Open

- **Delete `Backend/raptors.db` before running the server again.** Its `users` table predates both the soft-delete removal and `AUTOINCREMENT`, and `create_all` never alters an existing table.
- No GitHub remote yet. Commits are local; `git remote add origin ...` and push whenever.
- Frontend is untouched. The sneaker store's React app was deliberately not copied.
- Not decided: whether private friend leagues (step 5-8 era) are worth building, and whether reactions (step 10) are needed at all.

## Next: step 2

NBA data models: `Team`, `Player`, `Game`, and a per-game player stat table, plus their Pydantic schemas.

Before writing the columns, check what `nba_api` actually returns for a Raptors schedule and a box score, so the fields match the real payloads rather than a guess. A model change later means deleting the database.

Things the models need to support, decided above: a `Game` carries live state (score, period, clock, status) written by the poller and a `scored_at` timestamp; the box score table is per player per game and is what scoring reads.
