# CLAUDE.md (frontend)

Guidance for Claude Code when working in `frontend/`. The root `CLAUDE.md` covers the backend.

## Status

Step 16, done through 16.1 (the scaffold). Every route in `SPEC.md` exists as a placeholder page (`PlaceholderPage`) except `NotFoundPage`, which is real; the navbar's Log in / Sign up buttons are static until 16.2. `SPEC.md` has the agreed design, the API contract notes and the build order (16.0 to 16.9). Read it before starting a sub-step, and do one sub-step at a time.

When a sub-step is finished: tick it in the root `README.md` table, and add here whatever is now true about the code (commands that work, where things live, patterns in use). This file describes the code as it is; plans stay in `SPEC.md`.

## Stack

Vite + React + TypeScript (strict), React Router (`createBrowserRouter`, library mode), TanStack Query, Tailwind CSS v4, shadcn/ui, react-hook-form + zod. No Next.js, no Redux or Zustand, no axios unless there's a reason. `SPEC.md` says why.

## Commands (run from `frontend/`)

- Install: `npm install`
- Dev server: `npm run dev` (http://localhost:5173). Needs the backend on port 8000: `uv run fastapi dev main.py` from `Backend/` with `docker compose up -d db`, or `docker compose up -d` for the whole backend.
- API types: `npm run gen:api` regenerates `src/types/api.d.ts` from `http://localhost:8000/openapi.json` (backend must be running). Run it after any backend schema change. Without a running backend, export the schema from the app (`json.dump(main.app.openapi(), ...)` with dummy `SECRET_KEY`, `S3_BUCKET_NAME`, `DATABASE_URL` set) and point `npx openapi-typescript <file> -o src/types/api.d.ts` at the file.
- Type check and lint: `npm run build` (runs `tsc -b` then `vite build`), `npm run lint` (oxlint, which the Vite template ships instead of ESLint). The one existing warning is in shadcn's generated `button.tsx`.
- Add a shadcn component: `npx shadcn@latest add <name>`

## Where things live

- `src/main.tsx` mounts `QueryClientProvider` and `RouterProvider` (an `AuthProvider` joins them in 16.2); `src/router.tsx` is the route table; `components/layout/AppShell.tsx` is the navbar plus `<Outlet />` and the toaster.
- `lib/api-client.ts`: `request()` and the `api.get/post/put/patch/delete/login/upload` helpers, `ApiError`, the token in `localStorage` (`getToken`/`setToken`/`clearToken`), and `setAuthResetHandler` for the `AuthProvider` to register on. `lib/query-client.ts` doesn't retry 4xx errors. `lib/format.ts` has the time and score helpers.
- Generated types are read as `components["schemas"]["GameResponse"]` from `@/types/api`. The `@` alias is set in `vite.config.ts` and both tsconfigs.
- Tooling: TypeScript is pinned to 5.9 because `openapi-typescript` crashes on TypeScript 7 (it needs the JS compiler API, which 7 no longer has). Don't bump it until `openapi-typescript` supports 7.
- Two deliberate edits to shadcn's generated code: `lib/utils.ts` is the standard `clsx` + `tailwind-merge` `cn` (this shadcn version generated an import from an obscure `cn` npm package), and `ui/sonner.tsx` fixes `theme="dark"` instead of importing `next-themes`. Re-adding a component through the cli may bring the `cn` import back: change it to `@/lib/utils`.
- Theme: `index.css` defines one dark palette on `:root` (no `.dark` class, no light mode). The logo red `#BD1B21` is `--primary` and `--ring`. Fonts are `@fontsource-variable/inter` (`font-sans`) and `@fontsource/barlow-condensed` (`font-display`).
- `components/MediaCard.tsx` is the tile (link, optional image, dark overlay, hover cta). `HomePage` is a stand-in of three of them until 16.3.

## Conventions

- **Relative API urls only** (`/api/...`, `/static/...`). Vite's dev proxy and nginx forward them to FastAPI, so the app is same-origin everywhere: no `VITE_API_URL`, no CORS.
- **Types come from the backend.** Use the generated types in `src/types/api.d.ts`; never hand-write a type for an API response and never edit that file.
- **Never re-derive what the API decides**: `picks_open`, `room_open`, `opens_at`, `closes_at`, `editable_until`. Read them; still handle the 409 when a window closes mid-action.
- **All requests go through `lib/api-client.ts`**: it adds the token, turns FastAPI's `{"detail": ...}` into one `ApiError`, and on a 401 clears the token and retries once without it (public endpoints still 401 a stale token).
- **Server data lives in TanStack Query**, not in component state or context. Context holds auth only. Query keys are defined once per feature (see `SPEC.md`).
- **Features mirror the backend routers** (`features/games`, `features/picks`, `features/chat`, ...): each has `api.ts` (plain request functions), hooks, and its components. Pages in `pages/` stay thin and compose features.
- `components/ui/` is shadcn's generated code: change it through the shadcn cli where possible, and build project components on top of it in `features/*/components`.
- **Desktop-first.** Write desktop styles unprefixed and adjust smaller screens with `max-lg:` / `max-md:`.
- Times: the API sends UTC; display with `Intl.DateTimeFormat` in the browser's time zone (helpers in `lib/format.ts`).
- Login is form-encoded (`URLSearchParams`), with the email in the `username` field. Everything else is JSON, except the avatar upload (multipart).
- The routes `/games/:gameId` and `/reset-password?token=` are linked from the backend's emails: don't rename them.
- The Raptors claw logo (`public/raptors-logo.svg`) is used in the navbar and as the favicon. No NBA logos, opponent logos or player photos: teams appear as text.
- Look and feel is after insider.raptors.com (see `SPEC.md`): dark only, no hover pills on nav links, `MediaCard` for tiles, `font-display` (Barlow Condensed) for big uppercase titles.
- Comments follow the backend's style: lowercase, say why rather than what, at the end of the line or just above.
