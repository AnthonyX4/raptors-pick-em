from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Pagination
class PaginatedResponse(BaseModel):
    # shared by every paginated list below, each subclass adds that page's items under its own key
    total: int # matching rows across every page, not just this one
    skip: int
    limit: int
    has_more: bool # true when another page exists after this one

# letters, digits, _ and - only: usernames end up in frontend urls
USERNAME_PATTERN = r"^[A-Za-z0-9_-]+$"

class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    image_file: str | None
    image_path: str # read from the User.image_path property

class UserPrivate(UserPublic):
    email: EmailStr

class UserUpdate(BaseModel):
    # password isn't here, it's changed through PATCH /me/password (ChangePasswordRequest)
    username: str | None = Field(default=None, min_length=1, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr | None = Field(default=None)
    current_password: str | None = Field(default=None) # required to change email

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8) # same rule as UserCreate.password

class Token(BaseModel):
    access_token: str
    token_type: str

# Password reset
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str # the token from the emailed link's ?token= query param
    new_password: str = Field(min_length=8) # same rule as UserCreate.password

class MessageResponse(BaseModel):
    message: str

# Admin
class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: EmailStr
    is_admin: bool

class PaginatedAdminUsersResponse(PaginatedResponse):
    users: list[AdminUserResponse]


# --- NBA data ---------------------------------------------------------------

class GameStatus(StrEnum):
    # stored as a plain string in Game.status. the nba sends an integer (1, 2, 3) and its own
    # labels, which the harvest and the poller translate into these at the boundary, so nothing
    # past the ingest layer has to know what a "gameStatus of 2" means
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINAL = "final"
    POSTPONED = "postponed"


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    tricode: str
    city: str
    nickname: str
    full_name: str


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    full_name: str
    first_name: str
    last_name: str
    jersey_number: str | None
    position: str | None
    team: TeamResponse | None # needs selectinload(Player.team), async sessions can't lazy load it


class PaginatedPlayersResponse(PaginatedResponse):
    players: list[PlayerResponse]


class PlayerGameStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player: PlayerResponse
    team_id: int
    minutes: str | None
    comment: str | None
    points: int
    rebounds_offensive: int
    rebounds_defensive: int
    rebounds_total: int
    assists: int
    steals: int
    blocks: int
    turnovers: int
    three_pointers_made: int


class GameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game_id: str
    season: str
    tipoff_utc: datetime # picks for this game lock at this moment
    status: GameStatus
    status_text: str
    home_team: TeamResponse
    away_team: TeamResponse
    home_score: int | None # None until the game starts
    away_score: int | None
    arena_name: str | None
    period: int | None # only set while a game is live
    game_clock: str | None


class PaginatedGamesResponse(PaginatedResponse):
    games: list[GameResponse]


class GameDetail(GameResponse):
    # the box score, empty until a finished game has been ingested (step 7)
    player_stats: list[PlayerGameStatResponse]
