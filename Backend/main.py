# Fastapi
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

# Database
from database import engine, Base

from config import settings

# Schemas
from schemas import MessageResponse

# Cross Origin Resource Sharing (front and backend connection)
from fastapi.middleware.cors import CORSMiddleware

# Static files (serves the default profile picture etc. from the static folder)
from fastapi.staticfiles import StaticFiles

from starlette.exceptions import HTTPException as StarletteHTTPException

from routers import admins, games, players, users

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: table creation in database (create_all is sync, run_sync runs it on the async connection)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(games.router, prefix="/api/games", tags=["games"])
app.include_router(players.router, prefix="/api/players", tags=["players"])
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
