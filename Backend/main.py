# Fastapi
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

# Database
from database import engine, get_db, has_table, NOT_MIGRATED
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings

# Schemas
from schemas import HealthResponse, MessageResponse

# Cross Origin Resource Sharing (front and backend connection)
from fastapi.middleware.cors import CORSMiddleware

# Static files (serves the default profile picture etc. from the static folder)
from fastapi.staticfiles import StaticFiles

from starlette.exceptions import HTTPException as StarletteHTTPException

from routers import admins, games, leaderboard, messages, pick_categories, picks, players, users

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: tables are created and changed by alembic migrations (uv run alembic upgrade head), never here.
    # the app only checks they exist, and inserts the default pick categories if they're missing
    if not await has_table("pick_categories"):
        raise RuntimeError(NOT_MIGRATED)
    # a session on this module's engine, not database.AsyncSessionLocal: the tests swap the engine
    # before main is imported, and the session factory would still point at the real database
    async with AsyncSession(engine, expire_on_commit=False) as db:
        await pick_categories.ensure_default_categories(db)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

# CORS configuration
origins = [
    "http://localhost:5173",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# security headers on every response. cheap, and they close off browser-side tricks: being framed by
# another site (clickjacking), a browser guessing a json response is html (sniffing), full urls leaking
# to other sites in the Referer header, and a downgrade to plain http once the site has been seen on https
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if "Referrer-Policy" not in response.headers:
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # hsts tells a browser to only ever use https for this host, so never on a local dev server
    if request.url.hostname not in ("localhost", "127.0.0.1"):
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(games.router, prefix="/api/games", tags=["games"])
app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(pick_categories.router, prefix="/api/pick-categories", tags=["picks"])
app.include_router(picks.router, prefix="/api/picks", tags=["picks"])
app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["leaderboard"])
app.include_router(messages.router, prefix="/api", tags=["chat"])
app.include_router(admins.router, prefix="/api/admin", tags=["admin"])

# GET, a quick "is the api up" check. kept deliberately cheap: it touches no database and is what a
# container health check will hit. the frontend reads its home feed from /api/games?status=scheduled
@app.get(
    "/",
    response_model=MessageResponse,
    tags=["home"],
)
async def home():
    return MessageResponse(message=f"{settings.app_name} API is running")

# GET, "can this container actually serve requests": unlike GET / it runs a query, so a lost or
# misconfigured database shows up as a 503. what a deploy or docker compose waits on before sending traffic.
# a load balancer's routine check should stay on GET /: if the database blips, every container would fail
# this at once and be restarted, which doesn't bring the database back
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["home"],
    responses={503: {"description": "The database is unreachable"}},
)
async def health(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable") from exc
    return HealthResponse(status="healthy")

# Static files: GET /static/<path> returns the file at static/<path> (public, no auth)
# "static" is relative to the directory the server is started from, so run it from Backend/
# uploaded profile pictures aren't served from here, they live in S3 (see image_utils.py)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Handle General HTTP Errors
@app.exception_handler(StarletteHTTPException)
async def handle_general_http_errors(request: Request, exception: StarletteHTTPException):
    return await http_exception_handler(request, exception) # {"detail": ...} with the exception's status code (and headers, e.g. WWW-Authenticate)

# Handle Validation Errors
@app.exception_handler(RequestValidationError)
async def handle_validation_errors(request: Request, exception: RequestValidationError):
    return await request_validation_exception_handler(request, exception) # 422 with {"detail": [errors]}
