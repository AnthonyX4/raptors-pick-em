# Handoff

Written 2026-11-12, updated 2026-11-14 at the end of step 14. Read this with `README.md` (the step plan) and `CLAUDE.md` (conventions and architecture). This file holds what those two don't: the decisions already made and why, the design agreed for steps not yet built, and what's still open.

## Where things stand

- Steps 1 to 12 are done: the backend is a complete Pick'em app that runs itself, with a chat room per game and reminder emails. Step 13 packaged it as a Docker image, step 14 moved it to Postgres with Alembic migrations. Accounts and auth; the real 2026-27 Raptors season; pick categories; picks, locked at tipoff and revealed once a game starts; scoring from box scores; leaderboards; the poller, which keeps games, box scores and scores current from the NBA's CDN; and game chat with likes and moderation.
- 298 tests pass on SQLite and on Postgres (`cd Backend && uv run pytest`, a few minutes; run it in halves if a tool times out).
- On GitHub at https://github.com/AnthonyX4/raptors-pick-em, `main` tracking `origin/main`.
- `nba_data.json` is committed: 30 teams, 80 games (11 played at harvest time), 523 players, 304 box score lines. Seeding from it needs no NBA access, which matters for Docker and CI.
- The admin scoring endpoint stays as the manual re-run, e.g. `?force=true` after the NBA corrects a stat.

## Decisions already made

**The project is Raptors Pick'em with a per-game chatroom.** Users predict the result and stat leaders before tipoff; each game also has its own chat. Earlier ideas considered and set aside: a Poeltl-style trivia game and a shot-chart match game (both too thin on CRUD to carry the project), and a salary-cap fantasy roster (needs league-wide stats, which the NBA blocks from cloud IPs).

**`nba_api` is never called from a request handler.** stats.nba.com is slow, rate limited, and silently drops connections from AWS, GCP and Azure IPs, so a live call would work locally and time out in production. NBA data reaches the database through scripts and a background poller; endpoints only ever read the database.

**`harvest.py` is for development and the first load only.** It uses stats.nba.com, so it runs on a laptop, and a laptop can't (and shouldn't be able to) write to a production database inside AWS. Once deployed, every update has to come from a source reachable from AWS: the step 11 poller, reading `cdn.nba.com`. The CDN has a cloud-friendly equivalent for everything except rosters: live scoreboard, per-game box scores, and the season schedule (`cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json`). Rosters are covered by updating a player's team from the box score of the last game they played.

**The CDN works from a datacenter IP, but only for a browser-like client.** Checked 2026-11-13 by `.github/workflows/nba-reachability.yml` (step 4.5) on a GitHub runner (Azure). From the same runner, `curl` got a 403 Akamai "Access Denied" page for all three feeds, while `nba_api`'s live endpoints got 200 for all three. So the protection keys on the client, not the IP. Consequences for step 11: fetch through `nba_api` (or `NBALiveHTTP.headers` for the schedule, which it doesn't wrap), never a bare HTTP client. And Akamai rules can change without notice: the poller should log refusals loudly, and the workflow is worth re-running if it ever starts failing. Azure isn't AWS, so this is strong evidence rather than proof for ECS. If AWS turns out to be refused, the fallback is a small feeder at home that fetches from the NBA and posts results to an admin-only ingest endpoint.

**No soft delete.** Removed deliberately in commit `c9a578b`; deleting a user removes the row. Picks cascade with it. Chat messages stay with a null author, shown as "[deleted]" (decided in step 9), so conversations still read; the user's likes and mute go. Do not reintroduce `deleted_at` by reflex.

**Picks rules (step 6), chosen by Anthony.** Six launch categories (winner, margin, Raptors' points, rebounds, assists and steals leaders). Stat-leader picks are Raptors players only, checked against the roster as last harvested. Picks on a postponed game are kept and reopen when it's rescheduled. A deleted account takes its picks with it.

**Picks rules that follow from those.**
- Open means `status == scheduled` and before `tipoff_utc`. The clock check matters on its own: until the poller exists, a game that has tipped off still says "scheduled".
- Revealed means the game has actually started (live, final, or scheduled with tipoff passed), not merely closed. A postponed game is closed but stays hidden, or picks could be copied before it reopens.
- The winner pick is required, enforced both ways: no bonus pick without it (409), and it can't be withdrawn while bonus picks exist (409, refused rather than cascaded so one withdrawal never silently removes others).
- Someone else's pick is a 404, not a 403: picks are secret until tipoff, so the response shouldn't confirm one exists.
- Categories are never deleted, only deactivated: existing picks still need their category to be scored. Their kind and stat can't be edited, for the same reason.
- `utcnow()` in `routers/picks.py` is the router's only clock read, so tests move time instead of waiting.

**Scoring rules (step 7), chosen by Anthony.** Margin of victory pays by closeness, in thirds of the category's points rounded down: exact = all, off by 1-5 = two thirds, off by 6-10 = one third, more = nothing (3 / 2 / 1 / 0 at the default weight; the tiers scale if reweighted). A margin pick only counts if the same user's winner pick was right: it reads as "TOR by 8".

**Scoring rules that follow from those.**
- Stat leaders are found among Raptors who appeared, by the team on the box score line. Every tied leader counts as correct. A player who didn't play leads nothing. If nobody recorded a stat (no Raptor had a steal), nobody leads it and those picks score 0.
- Picks in a category deactivated after they were made are still scored.
- Points are written onto each pick, never added. A forced rescore uses the categories' current weights; reweighting without rescoring leaves past results alone.
- The leaderboard counts scored picks only (`points_awarded` not null), so an unscored game shows nothing and can't leak picks. A user whose scored picks all earned 0 still appears, with 0.

**`sqlite_autoincrement` on `User`.** A token carries only `{"sub": "<user_id>"}` and stays valid until it expires, so a reused id would let a deleted user's token authenticate as a new account. SQLite reuses the largest freed id without `AUTOINCREMENT`. Postgres sequences already behave correctly, so this is a SQLite-stage fix; `tests/test_tokens.py` is what keeps it true after the migration.

**Alembic since step 14.** Before it, tables came from `create_all` and new columns (`games.final_at`, `users.email_reminders`, `games.reminder_sent_at`) were added to Anthony's SQLite database by hand with `ALTER TABLE`. Those one-offs are what Alembic replaced.

**Chat rules (steps 9 and 10), chosen by Anthony.** Rooms are open on game day only: 24h before tipoff until 3h after the game ends. Edit your own message within 5 minutes, delete it any time. A deleted account's messages stay as "[deleted]". Mutes are timed; the admin picks the length (up to 30 days).

**Chat rules that follow from those.**
- "Ends" is `Game.final_at`, when the poller saw the game go final on the live scoreboard, not `scored_at` (a forced rescore moves that and would reopen the room). A game that arrives already final (seeded, or caught up by the schedule refresh) has no `final_at`, so its room is closed. A postponed game's room is closed until it's rescheduled.
- Reading a room is always public, even when closed. Liking needs the room open; unliking doesn't.
- A muted user can still read and like, but can't post or edit (editing would be posting by another route).
- Cursor pagination by message id, so `messages` uses `AUTOINCREMENT`: without it, deleting the newest message hands its id to the next one and a client polling `?after=` misses or misorders it.
- Someone else's message is a 403 (messages are public, nothing to hide), unlike someone else's pick (404, picks are secret until tipoff).
- Likes are `PUT`/`DELETE` on `/messages/{id}/like`, idempotent: liking twice is liking once. Muting is `PUT` because a second mute replaces the first, which is how an admin shortens a mistaken one. Admins can't be muted, for the same reason they can't be deleted.
- Mutes are their own table rather than a `users` column: moderation data stays out of the user row, and it avoided altering `users`.
- Mute times and message timestamps come from the chat's clock (`routers.messages.utcnow`), not column defaults, so the edit window and mute expiry measure from the same clock tests move.

**Reminder emails (step 12), defaults Claude chose, easy to change in `config.py`.** The poller emails each user a couple of hours (`reminder_hours_before = 2`) before tipoff, listing the active categories they haven't picked yet. Nobody who has made every pick is emailed. Users opt out with `email_reminders` (on by default) through `PATCH /api/users/{id}`, no password needed since it's a setting, not a credential; only `/me` and the owner's own responses show it.

**Reminder rules that follow from those.**
- Sent at most once per game: `Game.reminder_sent_at` is committed *before* any email goes out. A crash mid-send means some people miss one reminder; the other order would mean everyone getting it twice after a restart.
- A late poller still sends while picks are open (window is `tipoff - 2h <= now < tipoff`); after tipoff a reminder is useless, so it doesn't. Postponed games aren't reminded. A tipoff the schedule refresh moves clears `reminder_sent_at`, so the new date gets its own reminder.
- One failed email (bad address, SMTP hiccup) is logged and skipped; it never stops the others or the poller.
- `next_interval` wakes the poller for a reminder window as well as a game's watch, so reminders aren't up to 15 minutes late.
- Times in emails are shown in `display_timezone` (America/Toronto); the API itself only speaks UTC. `tzdata` is a direct dependency because Windows and slim Docker images have no system time zone database.
- Emails link to `<FRONTEND_URL>/games/<game_id>`, a page the frontend will need.

**Small API additions (after step 12).** `GameResponse.picks_open` is filled in by the route with `routers.picks.picks_open`, the same function that enforces the lock, so a frontend never re-derives it. `GET /api/games?upcoming=true` lists games not over yet (scheduled, live or postponed) and `false` finished ones, by status rather than the clock so a game in progress counts as upcoming. `POST` and `PATCH /api/picks` have one Swagger example per category kind, since the auto-generated body filled in all three answers and was always refused.

**Docker (step 13), adapted from Corey Schafer's FastAPI deployment tutorial.** A two-stage uv build: the builder installs dependencies (cached on `pyproject.toml` + `uv.lock` alone, so code edits don't reinstall) and the final stage copies only `/app`, so uv and its download cache never reach the image. Python 3.14.6 and uv 0.11.32 are pinned exactly. Runs as a non-root `appuser`, one server process per container (scale by adding containers), `exec` so SIGTERM reaches the server.
- **One image, two programs.** The default command is the API; the poller is `python poller.py` on the same image. They can't drift apart, and Compose and ECS will run the image twice with different commands.
- **`DATABASE_URL` became a setting.** The default is still `Backend/raptors.db`, so nothing changes on a laptop. The image sets it to `/app/data/raptors.db`, a directory created owned by `appuser` so a fresh named volume mounted there inherits that owner. Step 14 only changes this value.
- **No `HEALTHCHECK` in the Dockerfile**, because the poller runs from the same image and serves no port. Each service defines its own check in Compose or ECS.
- **`GET /health` runs `SELECT 1`** (503 without a database), for deploys and Compose to wait on. A load balancer's routine check should stay on `GET /`: a database blip would fail every container's `/health` at once and restart them all, which doesn't help.
- **Security headers middleware** on every response (frame, sniffing, referrer, HSTS except on localhost), straight from the tutorial.
- `.dockerignore` keeps out `.env`, every `*.db`, `.venv`, `tests/`. No system packages needed: Pillow, argon2 and (step 14) asyncpg all ship wheels with their C libraries inside.
- The image is about 650 MB unpacked, 150 MB compressed. Most of it is pandas and numpy, pulled in by `nba_api`. The poller needs `nba_api`, so it stays for now.
- My workspace can't pull from Docker Hub, so `.github/workflows/backend-ci.yml` does the real check on every backend push: the test suite, then the image built, a volume seeded, the API curled, the poller run once against the live CDN, and a clean stop.

**Postgres and Alembic (step 14), adapted from the sneaker store's `postgres-alembic` branch.** Same shape: `DATABASE_URL` required with no default, an async `alembic/env.py` that takes the url from settings, the app no longer creates tables. Differences, and why:
- **`asyncpg`, not `psycopg`.** psycopg's async mode can't run on the ProactorEventLoop Windows uses by default, which forced `loop_factory=asyncio.SelectorEventLoop` into every script in the sneaker store and kept `fastapi run` from working on Windows. asyncpg has no such limit, so the poller, seed and alembic run unchanged on Anthony's machine. `psycopg[binary]` is only a dev dependency, as the sync driver for the test fixtures on Postgres.
- **Tests run on both databases.** The sneaker store's tests stay on SQLite. Here `TEST_DATABASE_URL` switches the same suite to Postgres, and CI always uses it, so a Postgres-only behaviour (string length limits, `LIKE` case-sensitivity, sequences) can't pass unnoticed. All 298 passed on Postgres first time; SQLite stays the zero-setup default locally.
- **`UTCDateTime` stays**, rendered into migrations as plain `sa.DateTime(timezone=True)` (`render_item` in `env.py`). On Postgres it's a `timestamptz` and the decorator does nothing; it keeps the SQLite test database honest. The sneaker store patched a single column in `conftest.py` instead, which doesn't scale to fifteen datetime columns.
- **The default pick categories stay in the lifespan**, not in a data migration: they're insert-only, an admin can edit them, and the tests (which use `create_all`) need them too.
- **Unmigrated databases fail early with the fix spelled out.** The api refuses to start, and the poller and seed exit, with "run alembic upgrade head" (`database.has_table`), instead of a "relation does not exist" mid-request.
- **Migrations aren't run by the api at startup.** Two api containers starting together would race. Locally it's a command; in Compose (step 15) a one-shot service the api waits on; on ECS a one-off task before a deploy.
- **Local Postgres on port 5433** (`raptors-db` container, `raptors-pgdata` volume), because the sneaker store's container already holds 5432. CI and the docs use `postgres:17`.
- `copy_sqlite_to_postgres.py` moved Anthony's `raptors.db` across (tested on a copy of it: 2 users, 2 picks, 80 games, 338 box score lines), then moves each id sequence past the largest copied id so the next signup doesn't collide.

## Design agreed for later steps

Worked out in discussion and should be followed unless there's a reason to change. Pick categories (step 5) are now built as described; the rest is not built yet.

**Pick categories are data, not code** (step 5). One `PickCategory` row per question (winner, margin, points leader, rebounds leader, assists leader, steals leader), each with an answer type and a `points` weight. Adding a question is an admin action, not a code change. Scoring is one generic function over all "leader" categories. Only winner is required; the rest are optional bonus points, so a user isn't filling in ten fields 82 times a season.

**Weights are inverse to predictability.** Winner is the easiest (~60-65% hit rate) and should be worth the least; steals and blocks leaders are near coin flips and worth the most. Rather than guessing, calibrate from the harvested box scores once step 3 is done: measure how often the obvious pick was right per category and set points ≈ 1 ÷ hit rate. Numeric categories (margin) award a fraction of their `points` by closeness; player and team categories are all-or-nothing. Treat `points` as the maximum.

**Each pick stores the points it earned**, the way `OrderItem.fixed_price` did in the sneaker store. A pick was judged against one box score and that verdict shouldn't silently change later. It also means retuning a weight mid-season doesn't rewrite past results.

**The leaderboard is derived, never stored.** `SUM(points_awarded) GROUP BY user_id`, computed per request. No running total to drift out of sync, and re-scoring a corrected game fixes the standings automatically. Cache in Redis later if it ever matters.

**Scoring must be idempotent** (step 7). Running it twice on the same game must not double anyone's points. A `scored_at` timestamp on `Game` that the job skips unless passed a `force` flag. Build the admin trigger endpoint first so the job is testable against a seeded finished game; step 11 then calls the same function from the poller, and the endpoint stays as a manual re-run.

**Chatrooms are scoped by game, not reset.** Each game has its own room keyed by `game_id`, so "tonight's chat" is just the frontend pointing at today's game and old rooms stay readable. Rooms follow game status: open before, open during, read-only a few hours after.

**Chat uses cursor pagination**, `?before=<message_id>&limit=50`, not `skip`/`limit`. New messages shift every offset, so offset paging repeats rows in a live feed. Games and leaderboards keep `skip`/`limit`.

**Polling before WebSockets.** Build chat and live scores on plain REST with the browser re-requesting on a timer; it is a complete, testable feature. Add WebSockets afterwards as an upgrade, keeping `POST` for sending. Once more than one backend container runs, a message posted to container A won't reach clients on container B, which is where Redis pub/sub earns its place.

**The poller is a separate process** (step 11, built). Not a task in the api's lifespan, so two api containers can't mean two pollers racing. On ECS it becomes its own service with a desired count of 1; in Docker Compose, a second service from the same image with `command: python poller.py`.

**The poller does four jobs** (built). A daily schedule refresh (new NBA Cup games, moved tipoffs, postponed games going back to scheduled, which reopens their picks, and final scores for any game it missed entirely); pick reminder emails before tipoff (step 12); live scores for games on or about to start; box scores and scoring for finished games. It moves `Player.team_id` to the team a player last appeared for, since there's no cloud-reachable roster feed. It scores immediately when a box score says final; if the NBA later corrects a stat, an admin rescores with `?force=true`.

**Statuses never move backwards** (`schemas.can_move_status`), except between scheduled and postponed. Three writers touch games (seed, scoreboard, schedule refresh) and they aren't equally fresh; without this, an old harvest re-seeded or a stale feed would turn a finished game back into a scheduled one, wipe its score and reopen its picks.

## Learned from the real data (step 3)

- **Ties are real and common.** In the season opener, Leonard, Barnes and Quickley all scored 23. The tie rule agreed above (picking any tied leader counts as correct) is not an edge case; step 7 must handle it from the start.
- **The schedule returned 80 games, not 82, and that's expected.** The NBA's 2026-27 calendar reserves December 6, 7 and 10 for regular-season games between teams eliminated from the NBA Cup, so two games per team don't have dates until group play ends. A harvest (or the poller's schedule refresh) after early December picks them up.
- **`Player.team_id` is a snapshot** from harvest time. A trade only shows after a re-harvest. Box score lines record the team the player actually played for, so history stays right.
- **`nba_api` pulls in pandas and numpy.** Fine for the harvest scripts, but it bloats the API's Docker image for code the API never runs. When containerizing, consider moving `nba-api` to a separate dependency group for the scripts, with only the step 11 poller needing it at runtime.

## Learned from scoring the real season (step 7)

Scored the 11 finished games on a copy of the database (no picks exist yet, so this checks the leaders, not points):

- **Ties are even more common than step 3 suggested.** The steals leader was tied in 5 of 11 games (once three ways), points and assists in 2 each. Ties make a category *easier* to hit, since any tied player counts.
- **Early hit rates for "pick the usual guy"**: assists, Quickley led or tied in 6 of 11 (55%); points, Barnes in 5 (45%); rebounds, Poeltl in 4 (36%); steals, Barnes in 4 (36%). Raptors are 5-6. Steals (5 points) and rebounds (3 points) are about equally predictable so far, so steals may be overpaying. Eleven games is too few to act on; recalibrate after 30 or so.

## Learned from the real CDN payloads (step 11)

Captured from a GitHub runner by `capture-nba-samples.yml`, trimmed copies in `Backend/tests/fixtures/nba/`.

- **The CDN box score is not the stats.nba.com one.** It leaves inactive players out entirely (28 lines for the opener, against 33 from stats.nba.com) and marks a benched player `played: "0"` with minutes `PT00M00.00S` rather than none. Both become `minutes = None` ("didn't appear"), or a benched player with zero minutes would count as having played.
- **The schedule shows a game in progress as 0-0.** Scores are only taken from it once a game is final; live scores come from the scoreboard.
- Clocks and minutes are ISO durations (`PT02M30.00S`), including a three-digit-seconds `PT12M000.00S` at the start of a quarter.
- `postponedStatus` was `"N"` on every game seen. Any other value is read as postponed, but that's unverified against a real postponement.
- The first end-to-end run (`poller-smoke.yml`) applied the schedule, picked up TOR @ PHI live in the 4th quarter, and scored the 11 finished games, all against the live CDN.

## Open

- Frontend is untouched. The sneaker store's React app was deliberately not copied.
- Not decided: whether private friend leagues (step 5-8 era) are worth building, and whether reactions (step 10) are needed at all.

## Next: a choice of direction

The backend is complete and runs itself. What's left:

- **Compose, then ECS** (steps 15 and 16). Docker and Postgres are done. Next: one `docker compose up` for Postgres (named volume, health check), a one-shot `migrate` service, then the api and poller once it has succeeded; then the api and poller as two ECS services, migrations as a one-off task, Postgres on RDS.
- **The frontend**, now that there's a complete API to build against. Chat polls `?after=<last id>` every few seconds; WebSockets are a later upgrade (and need Redis pub/sub once there's more than one api container).
