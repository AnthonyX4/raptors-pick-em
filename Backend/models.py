from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, UTC
from database import Base
from config import settings


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False) # stored as typed, uniqueness is checked case-insensitively in the routes
    email: Mapped[str] = mapped_column(String)

    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False) # only set with harvest_scripts/make_admin.py, never through the api
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None) # set when a user with history is "deleted", see delete_user_account
    image_file: Mapped[str | None] = mapped_column(String(200), default=None) # filename under profile_pics/ in the S3 bucket, None means the default picture
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
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
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship(back_populates="reset_tokens")
