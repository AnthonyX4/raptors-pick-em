# CLAUDE.md

Guidance for Claude Code when working in this repository. This file covers the whole project; each side has its own file with its commands, architecture and conventions.

## Project overview

Raptors Pick'em: users predict each Toronto Raptors game (winner, margin, stat leaders) before tipoff and chat in a per-game chat room. The backend (steps 1 to 15), the React frontend (step 16) and WebSockets for the chat (step 17) are done; step 18 is deploying.

- `Backend/` — FastAPI + SQLAlchemy (async) on PostgreSQL with Alembic, run with `uv`. Read `Backend/CLAUDE.md` when working there.
- `frontend/` — React (Vite + TypeScript) single-page app. Read `frontend/CLAUDE.md` when working there.

## Where things are written down

- `README.md` — what the project is, how to run it, and the step table (the plan and its state). Keep the table up to date when a step is finished.
- `HANDOFF.md` — decisions already made and why, the design agreed for steps not yet built, what's open. Follow it unless there's a reason to change, and record new decisions there with their reason.
- `Backend/CLAUDE.md`, `frontend/CLAUDE.md` — how the code on each side works now: commands, where things live, conventions. Update them with what's true once a step is done.
- `frontend/SPEC.md` — the design the frontend was built from (step 16), kept as the record of those decisions.

## How to work

- One step or sub-step from the README table per session. Plan first for anything bigger than a one-line diff, and wait for approval before writing code.
- Follow the explainable-code skill for every code change: Anthony needs to be able to explain all of it in an interview.
- Start from the repo root, so the root docs and both sides are in reach.

## Whole-project commands (run from the repo root)

- `.github/workflows/nba-reachability.yml` — manual GitHub Action checking the cdn.nba.com feeds are reachable from a datacenter IP, which the production poller depends on.
- Docker: `docker compose up -d --build` from the repo root runs `db`, a one-shot `migrate` (`alembic upgrade head`), then `api` (health check on `/health`) and `poller`, all from one image (`Backend/Dockerfile`: the api by default, other commands for the rest), then `frontend` (step 16.8: its own image from `frontend/Dockerfile`, nginx serving the built app on port 8080 and forwarding `/api` and `/static` to `api`, started once the api is healthy). No data in the image: secrets from `Backend/.env` via `env_file`, and Compose overrides `DATABASE_URL` to `db:5432` and `FRONTEND_URL` to `http://localhost:8080` (where the emails' links must land). Seed a fresh volume with `docker compose run --rm --no-deps api python harvest_scripts/seed.py`. Don't run the Compose api/poller and `uv run` ones at the same time (one port 8000, exactly one poller). `.github/workflows/backend-ci.yml` checks the migrations, runs the tests on Postgres and brings the Compose file up, frontend included, on every backend push.
- `.github/workflows/capture-nba-samples.yml` saves real cdn payloads (also printed into the job log, since artifact downloads may be unreachable); `poller-smoke.yml` runs the real poller once against the live cdn on a fresh seeded database. Both manual.
