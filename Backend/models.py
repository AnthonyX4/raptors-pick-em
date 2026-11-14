from sqlalchemy import ForeignKey, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator
from datetime import datetime, UTC
from database import Base
from config import settings


class UTCDateTime(TypeDecorator):
    """A datetime column that is stored in utc and always comes back timezone-aware.

    sqlite has no timezone type, so a plain DateTime(timezone=True) reads back naive.
    the api would then send "2026-11-13T00:00:00" with no offset, a browser in toronto
    would read it as local time (five hours off), and comparing it with datetime.now(UTC),
    which the tipoff lock does, raises a TypeError. postgres keeps the offset, so once
    migrated this is a no-op rather than something to remove.
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        # convert to utc before saving, sqlite would otherwise store a non-utc wall clock time as if it were utc
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class User(Base):
    __tablename__ = "users"
    # AUTOINCREMENT, so sqlite keeps a high-water mark instead of reusing the largest free id.
    # without it, deleting the newest user hands their id to the next signup, and the deleted
    # user's token (which carries only that id and stays valid until it expires) would
    # authenticate as the new account. postgres sequences already behave this way.
    __table_args__ = {"sqlite_autoincrement": True}

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False) # stored as typed, uniqueness is checked case-insensitively in the routes
    email: Mapped[str] = mapped_column(String)

    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False) # only set with harvest_scripts/make_admin.py, never through the api
    image_file: Mapped[str | None] = mapped_column(String(200), default=None) # filename under profile_pics/ in the S3 bucket, None means the default picture
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # deleting an account takes its picks with it (decided: no "[deleted]" rows on the leaderboard)
    picks: Mapped[list["Pick"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def image_path(self) -> str:
        # url the frontend can use as an <img> src
        # uploads: a full S3 url (public read comes from the bucket policy), the default: relative, served by this app's /static mount
        if self.image_file:
            return f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/profile_pics/{self.image_file}"
        return "/static/profile_pics/default.jpg"


class PasswordResetToken(Base):
    # one row per emailed reset link, deleted once it's used or a newer one is requested
    __tablename__ = "password_reset_tokens"

    reset_token_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False) # sha256 hex of the emailed token, the raw token is never stored
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship(back_populates="reset_tokens")


# --- NBA data ---------------------------------------------------------------
# every id below is the NBA's own, not one we generate: the harvest scripts and the live
# feeds both identify rows by these, so reusing them is what makes re-running a harvest
# an update instead of a duplicate


class Team(Base):
    __tablename__ = "teams"

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True) # nba's team id, e.g. 1610612761 for Toronto
    tricode: Mapped[str] = mapped_column(String(3), unique=True, nullable=False) # "TOR", what the ?opponent= filter matches on
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False) # "Raptors"
    full_name: Mapped[str] = mapped_column(String(100), nullable=False) # "Toronto Raptors"

    players: Mapped[list["Player"]] = relationship(back_populates="team")


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True) # nba's personId
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # the roster a player was on when we last harvested, so a trade needs a re-harvest to show up.
    # picks validate against this, which is why it is nullable: a player in an old box score may have left the league
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.team_id"), default=None, index=True)
    jersey_number: Mapped[str | None] = mapped_column(String(3), default=None) # a string: "00" and "0" are different players
    position: Mapped[str | None] = mapped_column(String(10), default=None) # "G", "F-C", sometimes empty from the api

    team: Mapped["Team | None"] = relationship(back_populates="players")


class Game(Base):
    __tablename__ = "games"

    game_id: Mapped[str] = mapped_column(String(20), primary_key=True, index=True) # nba's gameId, a zero-padded string like "0022600123"
    season: Mapped[str] = mapped_column(String(7), nullable=False, index=True) # "2026-27"
    tipoff_utc: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True) # picks lock at this moment

    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True) # a GameStatus value, see schemas.py
    status_text: Mapped[str] = mapped_column(String(50), default="") # whatever the nba shows: "7:30 pm ET", "Q3 4:12", "Final"

    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), nullable=False, index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), nullable=False, index=True)
    home_score: Mapped[int | None] = mapped_column(Integer, default=None) # None until the game starts
    away_score: Mapped[int | None] = mapped_column(Integer, default=None)

    arena_name: Mapped[str | None] = mapped_column(String(100), default=None)

    # written by the step 11 poller while a game is in progress, left alone otherwise
    period: Mapped[int | None] = mapped_column(Integer, default=None) # 1-4, higher for overtime
    game_clock: Mapped[str | None] = mapped_column(String(20), default=None)

    # set when step 7 scores the picks for this game, so re-running scoring can skip a game it already did
    scored_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    # when the poller saw the game go final on the live scoreboard. the game's chat room closes a few
    # hours after this. stays None for a game that was already over when it arrived (seeded, or caught
    # up by the schedule refresh), whose room is simply closed. not scored_at: an admin's forced
    # rescore moves that, and must not reopen a room
    final_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    # two foreign keys point at the same table, so each relationship has to say which one it follows
    home_team: Mapped["Team"] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped["Team"] = relationship(foreign_keys=[away_team_id])
    player_stats: Mapped[list["PlayerGameStat"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class PlayerGameStat(Base):
    # one row per player per game, written when a finished game's box score is ingested.
    # this is what scoring reads to decide who led each category
    __tablename__ = "player_game_stats"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_player_game_stat"), # re-ingesting a box score updates rows instead of adding them
    )

    player_game_stat_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.player_id"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), nullable=False) # which side they played for in this game, trades make this differ from Player.team_id

    minutes: Mapped[str | None] = mapped_column(String(10), default=None) # "32:14", None when the player did not appear
    comment: Mapped[str | None] = mapped_column(String(100), default=None) # the nba's reason for a dnp, empty for players who appeared

    points: Mapped[int] = mapped_column(Integer, default=0)
    rebounds_offensive: Mapped[int] = mapped_column(Integer, default=0)
    rebounds_defensive: Mapped[int] = mapped_column(Integer, default=0)
    rebounds_total: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    steals: Mapped[int] = mapped_column(Integer, default=0)
    blocks: Mapped[int] = mapped_column(Integer, default=0)
    turnovers: Mapped[int] = mapped_column(Integer, default=0)
    three_pointers_made: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped["Game"] = relationship(back_populates="player_stats")
    player: Mapped["Player"] = relationship()



# --- Pick'em ----------------------------------------------------------------

class PickCategory(Base):
    # one row per question a user can answer about a game. categories are data, not code: an admin
    # adds "blocks leader" by creating a row, and scoring (step 7) handles it with no new code,
    # because every stat leader is scored the same way, by the column named in stat
    __tablename__ = "pick_categories"

    pick_category_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # derived by the server from kind and stat ("winner", "margin", "leader:points"), never sent by a client.
    # unique, so there's one winner category and one per stat. a unique (kind, stat) pair wouldn't do
    # it: sql treats NULL stats as distinct, so it would allow two winner rows
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False) # a CategoryKind value, see schemas.py
    stat: Mapped[str | None] = mapped_column(String(30), default=None) # a PlayerGameStat column, only for stat leaders

    name: Mapped[str] = mapped_column(String(100), nullable=False) # what the form shows: "Raptors' top scorer"
    points: Mapped[int] = mapped_column(Integer, nullable=False) # the most a correct answer earns, easier questions are worth less
    # a user has to make every required pick before any optional one (the winner, by default)
    is_required: Mapped[bool] = mapped_column(default=False)
    # deactivating stops new picks but keeps existing ones scored, which is why there's no delete
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0) # order on the pick form


class Pick(Base):
    # one user's answer to one category for one game. editable until tipoff, then frozen and revealed
    __tablename__ = "picks"
    __table_args__ = (
        UniqueConstraint("user_id", "game_id", "pick_category_id", name="uq_pick"), # one answer per question per game
    )

    pick_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), nullable=False, index=True)
    pick_category_id: Mapped[int] = mapped_column(ForeignKey("pick_categories.pick_category_id"), nullable=False)

    # the answer: exactly one of these is set, which one depends on the category's kind.
    # typed columns rather than one text field, so a picked team or player is a real foreign key
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.team_id"), default=None) # winner
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.player_id"), default=None) # stat leader
    margin: Mapped[int | None] = mapped_column(Integer, default=None) # margin of victory

    # None until step 7 scores the game. stored rather than recomputed, like OrderItem.fixed_price:
    # the pick was judged against one box score, and changing a category's weight later shouldn't rewrite it
    points_awarded: Mapped[int | None] = mapped_column(Integer, default=None)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship(back_populates="picks")
    game: Mapped["Game"] = relationship()
    category: Mapped["PickCategory"] = relationship()
    team: Mapped["Team | None"] = relationship()
    player: Mapped["Player | None"] = relationship()



# --- Chat -------------------------------------------------------------------

class Message(Base):
    # one post in a game's chat room
    __tablename__ = "messages"
    # AUTOINCREMENT matters here for a second reason beyond tokens: the chat pages by message id
    # (?before= / ?after=), which only works if ids only ever grow. without it, deleting the newest
    # message hands its id to the next one, and a client polling ?after= would miss or misorder it
    __table_args__ = {"sqlite_autoincrement": True}

    message_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), nullable=False, index=True)
    # None once the author deletes their account (decided: messages stay, shown as "[deleted]",
    # so a conversation still makes sense). set in delete_user_account
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), default=None, index=True)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))
    edited_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None) # shown as "edited"

    author: Mapped["User | None"] = relationship()
    likes: Mapped[list["MessageLike"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class MessageLike(Base):
    # the composite key is the "one like per user per message" rule, enforced by the database itself
    __tablename__ = "message_likes"

    message_id: Mapped[int] = mapped_column(ForeignKey("messages.message_id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))

    message: Mapped["Message"] = relationship(back_populates="likes")


class Mute(Base):
    # an admin's ban on posting, until a time (decided: timed, the admin picks how long). one row per
    # user, a new mute replaces the old one. a separate table rather than a column on users, so
    # moderation history doesn't widen every user row, and adding it didn't mean rebuilding that table
    __tablename__ = "mutes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    muted_until: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))

    user: Mapped["User"] = relationship()
