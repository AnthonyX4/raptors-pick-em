# Frontend spec (step 16)

Agreed 2026-11-17. This is the design for the frontend before it's built: what was decided, why, and the order to build it in. `CLAUDE.md` in this folder says how the code that exists works; this file says what it should become. Read both before starting a sub-step, and the backend's `HANDOFF.md` for the rules the API enforces.

When a sub-step is finished: tick it in the root `README.md` table, and move anything that's now true about the code (where things live, patterns used) into `frontend/CLAUDE.md`. Keep this file as the record of the decisions.

## Decisions

**A Vite single-page app, not Next.js.** The FastAPI backend already owns auth, data and business rules, so Next's server features (API routes, server actions, middleware) would duplicate it. Almost every page that matters sits behind a login or changes every few seconds, so server rendering and SEO buy little. A Vite build is static files that nginx serves, which fits the existing Docker Compose setup. Revisit only if public, indexable game pages become a goal.

**Stack.**

| Concern | Choice |
|---|---|
| Build | Vite + React + TypeScript |
| Routing | React Router (`createBrowserRouter`, library mode, not framework mode) |
| Server data | TanStack Query (caching, polling, refetch, infinite scroll) |
| Client state | React context for auth only. No Redux or Zustand |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite` plugin, no `tailwind.config.js`) |
| Components | shadcn/ui |
| Forms | react-hook-form + zod (what shadcn's `Form` is built on) |
| API types | Generated from FastAPI's `/openapi.json` with `openapi-typescript` |

**Desktop-first.** Design for wide screens first, then make sure it still works on a phone. Tailwind's breakpoints are min-width, so write the desktop styles unprefixed and adjust smaller screens with `max-lg:` / `max-md:`. The game page is two columns on desktop (game + picks on the left, chat on the right) and stacks below `lg`.

**TypeScript** throughout, `strict` on.

**Same origin everywhere.** The browser only ever talks to the frontend's own origin. Vite's dev server (dev) and nginx (production) forward `/api` and `/static` to FastAPI. So the API client uses relative URLs, there is no `VITE_API_URL`, and CORS never comes into play. `/static` matters because the default avatar's `image_path` is `/static/profile_pics/default.jpg`, served by the API.

**Admin UI is chat moderation only.** An admin sees "Delete" and "Mute author" on every chat message. Everything else admins do (users list, pick categories, rescoring, list of mutes) stays in Swagger at `/docs`. No admin pages or routes.

**Profiles by id**: `/users/:userId`. It works with the API as it is, and usernames can be changed (`PATCH /api/users/{id}`), which would break username links.

**Never re-derive what the API decides.** `picks_open` (on every game), `room_open` / `opens_at` / `closes_at` (on a chat page), `editable_until` (on a message) come from the backend, which enforces the same rules. The UI reads them; it doesn't recompute them from the clock and status. It still handles the 409 if a window closes while someone is typing.

**Times.** The API speaks UTC only. Show times in the browser's own time zone with `Intl.DateTimeFormat`.

**Look: after insider.raptors.com** (changed 2026-11-17, after 16.1). A dark app: `#171717` page, a black navbar with the Raptors claw logo (`public/raptors-logo.svg`, taken from that site), grey `#a1a1a1` secondary text, the logo's red `#BD1B21` for emphasis, small 4px corners. Nav links are plain uppercase text with no hover pill. Content tiles are `MediaCard`s: a border, a dark overlay over the background that deepens on hover, and a condensed uppercase title. Fonts are Inter (body) and Barlow Condensed (display), self-hosted through `@fontsource`; the site's own fonts are licensed and not used. This replaces the earlier rule of no Raptors logos: it's the team's trademark, fine for a personal project, worth revisiting before the app is made public. Still no NBA logos, team logos for opponents or player photos: teams appear as text (tricode, name).

## Backend changes first (16.0)

Three small changes the frontend depends on. Each needs its tests updated (`uv run pytest`).

1. **Token lifetime 7 days.** `access_token_expire_minutes = 60 * 24 * 7` in `config.py` (and in `.env` if it's set there). There's no refresh token, and 30 minutes logged people out mid-game.
2. **`is_admin: bool` on `UserPrivate`** in `schemas.py`, so the frontend knows to show moderation controls. Only `/me` and the owner's own responses use `UserPrivate`, so nobody learns who else is an admin.
3. **`editable_until: datetime` on `ChatMessageResponse`**, filled in `to_responses()` as `m.created_at + EDIT_WINDOW`. Same idea as `picks_open`: the backend owns the 5-minute rule.

No new dependencies, no migration (none of these is a column).

## Routes

```
/                          HomePage           next or live Raptors game, CTA to pick
/games                     GamesPage          the season: upcoming and finished
/games/:gameId             GameDetailPage     picks, score / box score, chat   ← reminder emails link here
/leaderboard               LeaderboardPage    season standings
/users/:userId             ProfilePage        public profile
/settings                  SettingsPage       (protected) account, password, avatar, reminders, delete account
/login                     LoginPage
/register                  RegisterPage
/forgot-password           ForgotPasswordPage
/reset-password?token=…    ResetPasswordPage                      ← password reset emails link here
*                          NotFoundPage
```

`/games/:gameId` and `/reset-password` are fixed: the backend's emails link to `<FRONTEND_URL>/games/<game_id>` and `<FRONTEND_URL>/reset-password?token=...`.

Only `/settings` needs a login. Every other page works logged out and shows more when logged in.

| Public | Needs a login |
|---|---|
| Games list and detail (box score), players, pick categories | Making, editing, withdrawing picks; `GET /api/picks/me` |
| Leaderboards (season and per game) | Posting, editing, deleting, liking messages |
| Reading any chat room | Settings: username, email, password, avatar, reminders, delete account |
| Everyone's picks for a game once it has started | Admin: delete any message, mute an author |
| A user's public profile | |

## Folder structure

```
frontend/
├── src/
│   ├── main.tsx                 # QueryClientProvider, AuthProvider, RouterProvider
│   ├── router.tsx               # the route table above
│   ├── index.css                # @import "tailwindcss"; shadcn theme variables
│   ├── components/
│   │   ├── ui/                  # shadcn-generated, edited only through the shadcn cli where possible
│   │   └── layout/              # AppShell (navbar + <Outlet />), ProtectedRoute
│   ├── features/                # one folder per backend router
│   │   ├── auth/                # api.ts, hooks.ts, AuthProvider.tsx, components/
│   │   ├── games/               # api.ts, hooks.ts, components/ (GameCard, GameHeader, BoxScore, StatusBadge, Countdown)
│   │   ├── picks/               # api.ts, hooks.ts (useSavePicks), schema.ts, components/ (PickForm, PickField, RevealedPicks)
│   │   ├── chat/                # api.ts, useGameChat.ts, components/ (ChatRoom, MessageList, MessageItem, MessageInput)
│   │   ├── leaderboard/
│   │   └── users/               # profile and settings
│   ├── pages/                   # one per route, thin: compose features, no fetching logic of their own
│   ├── lib/
│   │   ├── api-client.ts        # fetch wrapper: token, errors, the 401 retry
│   │   ├── query-client.ts
│   │   ├── format.ts            # dates, times, scores
│   │   └── utils.ts             # shadcn's cn()
│   ├── hooks/                   # generic hooks (useInterval, useNow)
│   └── types/
│       └── api.d.ts             # generated, never edited by hand
├── components.json              # shadcn config
├── vite.config.ts               # dev proxy for /api and /static, @ alias for src/
├── Dockerfile                   # node build stage → nginx
├── nginx.conf
├── CLAUDE.md
└── SPEC.md
```

How it maps to the backend: `features/*/api.ts` ≈ a router, `types/api.d.ts` ≈ `schemas.py`, `lib/api-client.ts` ≈ the `CurrentUser` dependency, `pages/` ≈ thin route handlers.

## How each part works

### API client and auth

- **Login** is `POST /api/users/token` as `application/x-www-form-urlencoded` (`URLSearchParams`), field `username` holding the **email**, plus `password`. It returns `{access_token, token_type: "bearer"}`.
- The token lives in `localStorage` and goes out as `Authorization: Bearer <token>` on every request. On startup, if there's a token, `GET /api/users/me` loads the user (`UserPrivate`: includes `email`, `email_reminders`, `is_admin`).
- **The 401 retry.** Public endpoints that show more to a logged-in reader (chat's `liked_by_me`) use the backend's `OptionalUser`, which still returns 401 for an expired or invalid token rather than treating the reader as anonymous. So on any 401 the client clears the token, resets the auth state, and **retries the request once without a token**. If that still fails, it's a real error. This is what keeps a public page working for someone whose token expired.
- **Errors.** FastAPI sends `{"detail": "message"}`, or for a 422 `{"detail": [{loc, msg, ...}]}`. The client turns both into one `ApiError { status, message }` so components show `error.message`.
- `ProtectedRoute` waits for the startup `/me` call, then renders `<Outlet />` or `<Navigate to="/login" replace />` (remember where the user was going and return there after login).
- Register is `POST /api/users` (JSON: `username`, `email`, `password` ≥ 8). Usernames are letters, digits, `_` and `-`, up to 50. Then log in automatically.
- Forgot password is `POST /api/users/forgot-password` (always a 202, whether or not the email exists; say "if that address has an account, we've sent a link"). Reset is `POST /api/users/reset-password` with `token` from the URL and `new_password`.

### Games

- `GET /api/games` is paginated and **oldest first**, with `?season=2026-27`, `?upcoming=true|false`, `?status=`, `?opponent=<tricode>`. A whole season fits in one request (`limit=100`, the maximum), so `GamesPage` fetches it in one go and shows upcoming and finished as two tabs, finished newest first (reverse on the client).
- The home page's next game is `GET /api/games?upcoming=true&limit=1`: the oldest game that isn't final, which is the live one if a game is on.
- `GET /api/games/{id}` is `GameDetail`: the game plus `player_stats` (box score, highest scorer first, empty until ingested).
- `status` is `scheduled | live | final | postponed`. Live games have `period`, `game_clock`, scores. `status_text` is the NBA's own label, fine to show as is.
- **Live refresh**: while `status === "live"`, refetch the game every 30 seconds (the poller's cadence while a game is on). Stop when it isn't live.

| From the API | UI |
|---|---|
| `scheduled`, `picks_open` true | countdown to `tipoff_utc`, pick form editable |
| `scheduled`, `picks_open` false | tipoff has passed, poller hasn't caught up: "starting", picks read-only |
| `live` | live score, period and clock, refetching |
| `final` | final score and box score |
| `postponed` | banner; picks kept and hidden, form read-only until it's rescheduled |

### Picks

- Categories: `GET /api/pick-categories`, active ones in form order (`sort_order`). Each has `kind`, `stat`, `name`, `points`, `is_required`. The form is built from this list, never hardcoded, so an admin adding a category adds a field.
- Field per `kind`:
  - `winner` → choose one of the game's two teams (`team_id`). Required.
  - `margin` → number 1 to 99 (`margin`), "by how many".
  - `stat_leader` → choose a Raptor (`player_id`), from `GET /api/players?team=TOR&limit=100`. The label comes from `stat`.
- Show each category's `points` next to its field so people see what a bonus pick is worth.
- The user's current picks: `GET /api/picks/me?game_id=<id>`.
- **Saving is several requests**, one pick row per category. `useSavePicks` compares the form with the saved picks and sends, in this order:
  1. the winner pick (`POST` or `PATCH`), because bonus picks are refused (409) without one;
  2. new bonus picks (`POST /api/picks`) and changed ones (`PATCH /api/picks/{pick_id}`);
  3. cleared bonus picks (`DELETE /api/picks/{pick_id}`);
  4. the winner last, if it's being withdrawn, because it can't go while bonus picks exist (409).

  Then invalidate the `picks/me` query. If one request fails, stop, refetch, and show the error: the server state is the truth.
- A pick body fills in exactly one answer field, the one its category's `kind` asks for. Anything else is a 400.
- **Everyone's picks** (`GET /api/picks?game_id=<id>`, paginated, grouped by user) only once the game has started. Before that it's a 403, so don't request it while `picks_open` is true or the game is postponed.
- `points_awarded` is null until the game is scored: show "pending", then the points.

### Chat

- `GET /api/games/{id}/messages` returns `ChatMessagePage`: `messages` (oldest first), `has_older`, `has_newer`, `room_open`, `opens_at`, `closes_at`. Cursor pagination by message id, not skip/limit.
- `useGameChat(gameId)` keeps one list of messages keyed by `message_id` and does three things:
  1. **Load**: the newest page (no cursor).
  2. **Poll for new messages** every 3 seconds with `?after=<newest id>`, only while `room_open` and the tab is visible. Append.
  3. **Refresh recent messages** every 30 seconds by refetching the newest page and merging it in: replace `body`, `edited_at`, `like_count`, `liked_by_me`, and drop any id inside that page's id range that's no longer there (deleted). `?after=` alone only ever returns new ids, so this is what makes other people's edits, deletes and likes show up. Edits only happen in the first 5 minutes, so recent messages are where they happen. Like counts on old messages can drift until a reload; WebSockets fix that later.
- Scrolling back: `?before=<oldest id>` while `has_older`. Keep the scroll position when older messages are added above, and only auto-scroll to the bottom if the reader was already at the bottom.
- Posting: `POST /api/games/{id}/messages` `{body}` (1 to 500 characters after trimming). Own edits, deletes and likes return the updated message, so apply the response straight away.
- `author: null` means the author deleted their account: show "[deleted]".
- Edit (`PATCH /api/messages/{id}`) only for your own message and while `now < editable_until`. Delete (`DELETE /api/messages/{id}`) your own any time.
- Likes: `PUT` / `DELETE /api/messages/{id}/like` (idempotent). Liking needs the room open; unliking doesn't.
- Closed room: show "Chat opens <opens_at>" before, "Chat closed" after, and no input. Reading is always allowed.
- Muted: posting or editing returns 403 with a message saying so. Show it.
- Admins (`user.is_admin`): "Delete" on any message (`DELETE /api/admin/messages/{id}`) and "Mute author" (`PUT /api/admin/users/{user_id}/mute` with `{hours, reason?}`, 1 to 720 hours). Admins can't be muted.

### Leaderboard

- `GET /api/leaderboard?season=2026-27` (skip/limit) and, on a finished game's page, `GET /api/leaderboard/games/{id}`. Entries have `rank` (ties share a rank), `user`, `total_points`, `picks_scored`, `correct_picks`, `games_played`.
- Highlight the logged-in user's row. Each user links to `/users/:userId`.

### Profile and settings

- `ProfilePage`: `GET /api/users/{id}` (`UserPublic`: `username`, `image_path`). That's all the API exposes about another user; per-user history would need a new endpoint and is out of scope.
- `SettingsPage`, all on the logged-in user's own id:
  - username, email: `PATCH /api/users/{id}` (changing email needs `current_password`)
  - reminder emails toggle: `PATCH /api/users/{id}` `{email_reminders}` (no password)
  - password: `PATCH /api/users/me/password` `{current_password, new_password}`
  - avatar: `PATCH /api/users/{id}/picture` (multipart, up to 5 MB), remove with `DELETE`
  - delete account: `DELETE /api/users/{id}`, behind a confirmation dialog, then log out. Their chat messages stay as "[deleted]".

### TanStack Query keys

Keep them in one place per feature so invalidation can't miss: `["games", filters]`, `["game", gameId]`, `["picks", "me", gameId]`, `["picks", "game", gameId]`, `["chat", gameId]`, `["leaderboard", season]`, `["leaderboard", "game", gameId]`, `["user", userId]`, `["me"]`.

### Deployment

- Dev: `npm run dev` on port 5173, with the backend on 8000 (`uv run fastapi dev main.py`, or `docker compose up` for the whole backend).
- `frontend/Dockerfile`: a node stage runs `npm ci && npm run build`, an nginx stage serves `dist/`.
- `nginx.conf`: `location /api/` and `location /static/` → `proxy_pass http://api:8000`; `location /` → `try_files $uri /index.html` (without this, refreshing `/games/123` is a 404).
- A `frontend` service in the root `docker-compose.yml`, depending on `api` being healthy, published on a port (e.g. 8080). The backend's `FRONTEND_URL` must match where the frontend is served, since emails link there.

## Build order

Each sub-step ends working and committed, the same way the backend was built.

| Step | What |
|---|---|
| 16.0 | Backend prep: 7-day tokens, `is_admin` on `UserPrivate`, `editable_until` on messages, tests updated |
| 16.1 | Scaffold: Vite + TS, Tailwind v4, shadcn init, React Router with placeholder pages, TanStack Query, dev proxy, `@` alias, `gen:api` script, `api-client.ts`, `AppShell`, `NotFoundPage` |
| 16.2 | Auth: login, register, forgot and reset password, `AuthProvider`, `ProtectedRoute`, the 401 retry |
| 16.3 | Games: games page, game header with live refresh, box score, home page's next game |
| 16.4 | Picks: `PickForm` built from categories, `useSavePicks`, locked and pending states, everyone's picks after tipoff |
| 16.5 | Chat: `useGameChat` (load, poll, refresh, scroll back), post, edit, delete, like, closed and muted states, admin moderation |
| 16.6 | Leaderboard: season standings, per-game standings on the game page |
| 16.7 | Profile and settings |
| 16.8 | Docker: frontend image, nginx, Compose service, `FRONTEND_URL` |
| 16.9 | Polish: loading, empty and error states everywhere, keyboard and screen reader pass, README |

## Later

- WebSockets for the chat: now step 17, designed in the root `HANDOFF.md` ("WebSockets for the chat"). Posting stays `POST`; the socket only delivers. Redis pub/sub once there's more than one api process.
- Per-user pick history on profiles (needs an endpoint).
- Private friend leagues, if ever.
