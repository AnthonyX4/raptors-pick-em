# Handoff

Written 2026-11-12, updated at the end of step 6. Read this with `README.md` (the step plan) and `CLAUDE.md` (conventions and architecture). This file holds what those two don't: the decisions already made and why, the design agreed for steps not yet built, and what's still open.

## Where things stand

- Steps 1 to 6 are done: accounts and auth; the real 2026-27 Raptors season at `/api/games` and `/api/players`; pick categories; and picks, which can be made, edited and withdrawn until tipoff and are revealed once a game starts.
- 164 tests pass (`cd Backend && uv run pytest`).
- Commits on `main`, local only. No remote is configured yet.
- `nba_data.json` is committed: 30 teams, 80 games (11 played at harvest time), 523 players, 304 box score lines. Seeding from it needs no NBA access, which matters for Docker and CI.
- Steps 7 to 12 are not started. Picks are never scored yet: `points_awarded` stays `None` until step 7.

## Decisions already made

**The project is Raptors Pick'em with a per-game chatroom.** Users predict the result and stat leaders before tipoff; each game also has its own chat. Earlier ideas considered and set aside: a Poeltl-style trivia game and a shot-chart match game (both too thin on CRUD to carry the project), and a salary-cap fantasy roster (needs league-wide stats, which the NBA blocks from cloud IPs).

**`nba_api` is never called from a request handler.** stats.nba.com is slow, rate limited, and silently drops connections from AWS, GCP and Azure IPs, so a live call would work locally and time out in production. NBA data reaches the database through scripts and a background poller; endpoints only ever read the database.

**`harvest.py` is for development and the first load only.** It uses stats.nba.com, so it runs on a laptop, and a laptop can't (and shouldn't be able to) write to a production database inside AWS. Once deployed, every update has to come from a source reachable from AWS: the step 11 poller, reading `cdn.nba.com`. The CDN has a cloud-friendly equivalent for everything except rosters: live scoreboard, per-game box scores, and the season schedule (`cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json`). Rosters are covered by updating a player's team from the box score of the last game they played.

**That the CDN works from AWS is reported, not yet verified.** `.github/workflows/nba-reachability.yml` (step 4.5) fetches the three CDN feeds from a GitHub runner (Azure, a datacenter IP) and fails if any is blocked. Run it once the repo is on GitHub, before building step 11. If it fails, the fallback is a small feeder running at home that fetches from the NBA and posts results to an admin-only ingest endpoint.

**No soft delete.** Removed deliberately in commit `c9a578b`; deleting a user removes the row. For picks this is settled: they cascade with the account (`User.picks`, delete-orphan). For chat messages (step 9) it is still open: cascade them too, or make the author nullable and show "[deleted]". Do not reintroduce `deleted_at` by reflex.

**Picks rules (step 6), chosen by Anthony.** Six launch categories (winner, margin, Raptors' points, rebounds, assists and steals leaders). Stat-leader picks are Raptors players only, checked against the roster as last harvested. Picks on a postponed game are kept and reopen when it's rescheduled. A deleted account takes its picks with it.

**Picks rules that follow from those.**
- Open means `status == scheduled` and before `tipoff_utc`. The clock check matters on its own: until the poller exists, a game that has tipped off still says "scheduled".
- Revealed means the game has actually started (live, final, or scheduled with tipoff passed), not merely closed. A postponed game is closed but stays hidden, or picks could be copied before it reopens.
- The winner pick is required, enforced both ways: no bonus pick without it (409), and it can't be withdrawn while bonus picks exist (409, refused rather than cascaded so one withdrawal never silently removes others).
- Someone else's pick is a 404, not a 403: picks are secret until tipoff, so the response shouldn't confirm one exists.
- Categories are never deleted, only deactivated: existing picks still need their category to be scored. Their kind and stat can't be edited, for the same reason.
- `utcnow()` in `routers/picks.py` is the router's only clock read, so tests move time instead of waiting.

**`sqlite_autoincrement` on `User`.** A token carries only `{"sub": "<user_id>"}` and stays valid until it expires, so a reused id would let a deleted user's token authenticate as a new account. SQLite reuses the largest freed id without `AUTOINCREMENT`. Postgres sequences already behave correctly, so this is a SQLite-stage fix; `tests/test_tokens.py` is what keeps it true after the migration.

**No Alembic.** Tables are created from the models at startup, so a model change means deleting `Backend/raptors.db`. Revisit when moving to Postgres.

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

**One poller, not one per container** (step 11). A loop started in `main.py`'s `lifespan` runs once per container, so two containers on ECS would double-poll and race. Either run it as a separate single-task service or take a lock in Redis. Note it in the code even while running a single container.

**The poller does three jobs, not one** (step 11). Live scores and statuses on game nights; box scores and scoring when a game goes final; and a daily schedule refresh from the CDN, which is what moves a postponed game back to scheduled (reopening its picks) and adds the NBA Cup games that only get dates in December. It also updates `Player.team_id` from each new box score, since there's no cloud-reachable roster feed.

## Learned from the real data (step 3)

- **Ties are real and common.** In the season opener, Leonard, Barnes and Quickley all scored 23. The tie rule agreed above (picking any tied leader counts as correct) is not an edge case; step 7 must handle it from the start.
- **The schedule returned 80 games, not 82, and that's expected.** The NBA's 2026-27 calendar reserves December 6, 7 and 10 for regular-season games between teams eliminated from the NBA Cup, so two games per team don't have dates until group play ends. A harvest (or the poller's schedule refresh) after early December picks them up.
- **`Player.team_id` is a snapshot** from harvest time. A trade only shows after a re-harvest. Box score lines record the team the player actually played for, so history stays right.
- **`nba_api` pulls in pandas and numpy.** Fine for the harvest scripts, but it bloats the API's Docker image for code the API never runs. When containerizing, consider moving `nba-api` to a separate dependency group for the scripts, with only the step 11 poller needing it at runtime.

## Open

- No GitHub remote yet. Commits are local; `git remote add origin ...` and push whenever. Then run the NBA reachability workflow once from the Actions tab.
- Frontend is untouched. The sneaker store's React app was deliberately not copied.
- Not decided: whether private friend leagues (step 5-8 era) are worth building, and whether reactions (step 10) are needed at all.

## Next: steps 7 and 8

Scoring (step 7) and the leaderboard (step 8), as one batch. After this the backend is a complete Pick'em app.

- An admin endpoint, `POST /api/admin/games/{game_id}/score`, that scores every pick for a final game from its stored box score and sets `scored_at`. Skips an already-scored game unless forced, so re-running never doubles points.
- Winner: correct team gets the category's points. Stat leaders: correct if the picked player is among the tied leaders for that stat among Raptors players (ties are common, see above). Margin: partial credit by closeness; the exact curve is a decision to settle with Anthony.
- A player who didn't play (DNP) can't lead anything; a pick of them simply scores zero.
- Leaderboard: `SUM(points_awarded)` per user, season-wide and per game, paginated, derived per request.
- The 11 finished games already have box scores in the database, so scoring can be tested on real data immediately.
