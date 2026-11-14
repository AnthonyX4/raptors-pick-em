from datetime import datetime
from enum import StrEnum

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

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
    email_reminders: bool # only the user themselves sees their settings

class UserUpdate(BaseModel):
    # password isn't here, it's changed through PATCH /me/password (ChangePasswordRequest)
    username: str | None = Field(default=None, min_length=1, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr | None = Field(default=None)
    current_password: str | None = Field(default=None) # required to change email
    email_reminders: bool | None = None # a setting, not a credential, so no current_password needed

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


# how far along a game is. scheduled and postponed are level, because a postponed game going back
# to scheduled is exactly how it gets its new date
STATUS_RANK = {GameStatus.SCHEDULED: 0, GameStatus.POSTPONED: 0, GameStatus.LIVE: 1, GameStatus.FINAL: 2}


def can_move_status(current: str, new: str) -> bool:
    """A game's status never moves backwards.

    Several things write games (the seed script, the poller's live scoreboard, its daily schedule
    refresh) and they're not equally fresh. A stale one must never turn a finished game back into
    a live or scheduled one, which would wipe its score and, for a scheduled game, reopen its picks.
    """
    return STATUS_RANK[GameStatus(new)] >= STATUS_RANK[GameStatus(current)]


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
    # whether picks can be made right now. filled in by the route with the same function that enforces
    # the lock, so a frontend never has to redo (and possibly disagree with) the clock and status logic
    picks_open: bool = False


class PaginatedGamesResponse(PaginatedResponse):
    games: list[GameResponse]


class GameDetail(GameResponse):
    # the box score, empty until a finished game has been ingested (step 7)
    player_stats: list[PlayerGameStatResponse]



# --- Pick'em ----------------------------------------------------------------

class CategoryKind(StrEnum):
    # what a category asks, which decides the answer field a pick must fill in
    WINNER = "winner" # team_id: one of the two teams in the game
    MARGIN = "margin" # margin: the winning margin in points, whoever wins
    STAT_LEADER = "stat_leader" # player_id: the Raptor who leads the game in `stat`


class LeaderStat(StrEnum):
    # the PlayerGameStat columns a stat leader category may be about. a closed list, so an admin
    # can't create a category scoring couldn't evaluate
    POINTS = "points"
    REBOUNDS_TOTAL = "rebounds_total"
    REBOUNDS_OFFENSIVE = "rebounds_offensive"
    REBOUNDS_DEFENSIVE = "rebounds_defensive"
    ASSISTS = "assists"
    STEALS = "steals"
    BLOCKS = "blocks"
    THREE_POINTERS_MADE = "three_pointers_made"


class PickCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pick_category_id: int
    key: str
    kind: CategoryKind
    stat: LeaderStat | None
    name: str
    points: int
    is_required: bool
    is_active: bool
    sort_order: int


class PickCategoryCreate(BaseModel):
    kind: CategoryKind
    stat: LeaderStat | None = None # required for a stat leader, must be empty otherwise (checked in the route)
    name: str = Field(min_length=1, max_length=100)
    points: int = Field(ge=1, le=100)
    is_required: bool = False
    is_active: bool = True
    sort_order: int = 0


class PickCategoryUpdate(BaseModel):
    # kind and stat can't change: existing picks were answers to the question as it was asked
    name: str | None = Field(default=None, min_length=1, max_length=100)
    points: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None
    sort_order: int | None = None



class PickCreate(BaseModel):
    game_id: str
    pick_category_id: int
    # fill in the one field the category's kind asks for: team_id for a winner,
    # margin for the margin of victory, player_id for a stat leader
    team_id: int | None = None
    player_id: int | None = None
    margin: int | None = Field(default=None, ge=1, le=99)


class PickUpdate(BaseModel):
    # same rule as PickCreate, the game and category stay as they were
    team_id: int | None = None
    player_id: int | None = None
    margin: int | None = Field(default=None, ge=1, le=99)


class PickResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pick_id: int
    game_id: str
    category: PickCategoryResponse
    team: TeamResponse | None
    player: PlayerResponse | None
    margin: int | None
    points_awarded: int | None # None until the game is scored
    created_at: datetime
    updated_at: datetime


class PickWithUser(PickResponse):
    user: UserPublic # who made it, for the revealed list of everyone's picks


class PaginatedPicksResponse(PaginatedResponse):
    picks: list[PickResponse]


class PaginatedGamePicksResponse(PaginatedResponse):
    picks: list[PickWithUser]



# --- Scoring and leaderboard ---------------------------------------------------

class GameScoreResponse(BaseModel):
    game_id: str
    scored: bool # False when the game was already scored and force wasn't passed: nothing changed
    scored_at: datetime
    winner: str # tricode of the team that won
    margin: int # the winning margin in points
    leaders: dict[str, list[str]] # stat leader category key -> the Raptors tied for the lead, empty if nobody recorded one
    picks_scored: int # how many picks were (re)scored, 0 when skipped


class LeaderboardEntry(BaseModel):
    rank: int # tied totals share a rank: 1, 2, 2, 4
    user: UserPublic
    total_points: int
    picks_scored: int
    correct_picks: int # picks that earned any points, partial margin credit included
    games_played: int


class LeaderboardResponse(PaginatedResponse):
    entries: list[LeaderboardEntry]



# --- Chat -------------------------------------------------------------------

# whitespace is stripped before the length check, so "   " is refused as empty rather than posted.
# 500 is settings.message_max_length; a literal here because schemas can't import config without a cycle
MessageBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ChatMessageCreate(BaseModel):
    body: MessageBody


class ChatMessageUpdate(BaseModel):
    body: MessageBody


class ChatMessageResponse(BaseModel):
    message_id: int
    game_id: str
    author: UserPublic | None # None when the author deleted their account: the frontend shows "[deleted]"
    body: str
    created_at: datetime
    edited_at: datetime | None
    like_count: int
    liked_by_me: bool # always False for a reader who isn't logged in


class ChatMessagePage(BaseModel):
    # cursor pagination, deliberately not the skip/limit shape every other list uses: in a live room new
    # messages shift every offset, so page 2 by offset would repeat rows. paging by message id doesn't
    messages: list[ChatMessageResponse] # oldest first, the order a chat is read in
    has_older: bool # ask again with ?before=<first message_id> to scroll back
    has_newer: bool # ask again with ?after=<last message_id>; polling does this every few seconds
    room_open: bool # whether posting is allowed right now, so the frontend knows to show the input box
    opens_at: datetime
    closes_at: datetime | None # None until the game has gone final


class MuteCreate(BaseModel):
    hours: int = Field(ge=1, le=24 * 30) # settings.mute_max_hours, a literal for the same reason as above
    reason: str | None = Field(default=None, max_length=200)


class MuteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserPublic
    muted_until: datetime
    reason: str | None


class PaginatedMutesResponse(PaginatedResponse):
    mutes: list[MuteResponse]
