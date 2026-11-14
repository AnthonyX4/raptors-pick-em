from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore", # .env may hold keys for the harvest scripts too, so skip keys not declared here
    ) # automatically load the below values from our .env file

    app_name: str = "Raptors Pick'em" # shown in the api docs and in emails

    # where the data lives. the default is raptors.db next to this file, so running from a laptop needs
    # nothing set. the docker image points it into /app/data, where a volume keeps it, and step 14
    # swaps it for a postgres url without touching any code
    database_url: str = f"sqlite+aiosqlite:///{BACKEND_DIR / 'raptors.db'}"

    secret_key: SecretStr # this type displays *** instead of actual value when printing or logging
    algorithm: str = "HS256" # default value
    access_token_expire_minutes: int = 30 # default value

    max_upload_size_bytes: int = 5 * 1024 * 1024 # 5MB, profile picture uploads larger than this are rejected

    # S3 (profile pictures are stored in the bucket, not on the server's disk)
    s3_bucket_name: str # required, the app won't start without it
    s3_region: str = "us-east-1"
    s3_access_key_id: SecretStr | None = None # None lets boto3 fall back to its own credential lookup (~/.aws, an IAM role...)
    s3_secret_access_key: SecretStr | None = None
    s3_endpoint_url: str | None = None # only for S3 compatible services (MinIO, Cloudflare R2), None means real AWS

    # the team this app follows, as its nba tricode. the harvest keeps only this team's games,
    # and ?opponent= is matched against whichever side of a game isn't this one
    team_tricode: str = "TOR"

    # pagination: the page size used when a request doesn't pass ?limit=
    items_per_page: int = 10 # the admin lists
    games_per_page: int = 20 # a month of games fits on one page
    messages_per_page: int = 50 # a screen or two of chat

    # chat rules (decided): a game's room is open on game day, 24h before tipoff until 3h after it ends,
    # and a message can be edited for 5 minutes. settings rather than constants so tests and deploys can read them
    chat_opens_hours_before: int = 24
    chat_closes_hours_after: int = 3
    message_edit_minutes: int = 5
    message_max_length: int = 500
    mute_max_hours: int = 24 * 30
    max_page_size: int = 100 # the largest ?limit= a request may ask for

    reset_token_expire_minutes: int = 60 # how long a password reset link works for

    # step 12: the poller emails users who haven't finished their picks this long before tipoff
    reminder_hours_before: int = 2
    # the time zone tipoffs are shown in, in emails. the api itself only ever speaks utc
    display_timezone: str = "America/Toronto"

    # email (smtp), the defaults are placeholders, the real values come from .env
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True # upgrades the connection with STARTTLS, not implicit TLS (port 465)

    # the react app, password reset emails link to <frontend_url>/reset-password?token=...
    frontend_url: str = "http://localhost:5173"


settings = Settings()
