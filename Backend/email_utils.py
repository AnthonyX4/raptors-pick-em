from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

import aiosmtplib
from fastapi.templating import Jinja2Templates

from config import settings

# only used to render email bodies to strings, the pages themselves (forgot/reset password) live in the react app
# anchored to Backend/ like the database, so it resolves the same regardless of cwd
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)


async def send_email(
    to_email: str,
    subject: str,
    plain_text: str,
    html_content: str | None = None,
) -> None:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to_email
    message["Subject"] = subject

    message.set_content(plain_text)

    # multipart/alternative: clients that render html show it, the rest fall back to the plain text
    if html_content:
        message.add_alternative(html_content, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.mail_server,
        port=settings.mail_port,
        username=settings.mail_username or None, # None skips login, for local smtp servers without auth
        password=settings.mail_password.get_secret_value() or None,
        start_tls=settings.mail_use_tls,
    )


async def send_password_reset_email(to_email: str, username: str, token: str) -> None:
    # the link opens the react app's /reset-password page, which reads ?token= and posts it to /api/users/reset-password
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    expire_minutes = settings.reset_token_expire_minutes

    template = templates.env.get_template("email/password_reset.html")
    html_content = template.render(
        app_name=settings.app_name, username=username, reset_url=reset_url, expire_minutes=expire_minutes,
    )

    plain_text = f"""Hi {username},

You requested to reset your {settings.app_name} password. Open the link below to set a new password:

{reset_url}

This link will expire in {expire_minutes} minutes.

If you didn't request this, you can safely ignore this email. Your password will stay the same.

- The {settings.app_name} Team
"""

    await send_email(
        to_email=to_email,
        subject=f"Reset your password - {settings.app_name}",
        plain_text=plain_text,
        html_content=html_content,
    )


def format_tipoff(tipoff_utc: datetime) -> str:
    """"Sun Nov 15, 6:00 pm EST", in settings.display_timezone. built by hand because strftime's
    unpadded day and hour codes (%-d, %-I) don't exist on windows"""
    local = tipoff_utc.astimezone(ZoneInfo(settings.display_timezone))
    hour = local.hour % 12 or 12
    meridiem = "am" if local.hour < 12 else "pm"
    return f"{local:%a %b} {local.day}, {hour}:{local:%M} {meridiem} {local.tzname()}"


async def send_pick_reminder_email(
    to_email: str, username: str, matchup: str, tipoff_utc: datetime, game_id: str, missing: list[str],
) -> None:
    # links to the react app's game page, where the pick form will live
    game_url = f"{settings.frontend_url}/games/{game_id}"
    tipoff = format_tipoff(tipoff_utc)

    template = templates.env.get_template("email/pick_reminder.html")
    html_content = template.render(
        app_name=settings.app_name, username=username, matchup=matchup, tipoff=tipoff,
        missing=missing, game_url=game_url,
    )

    missing_lines = "\n".join(f"- {name}" for name in missing)
    plain_text = f"""Hi {username},

{matchup} tips off at {tipoff}, and picks lock the moment it starts. You haven't made these yet:

{missing_lines}

Make your picks: {game_url}

You get this because pick reminders are on in your {settings.app_name} account settings. Turn them off there any time.

- The {settings.app_name} Team
"""

    await send_email(
        to_email=to_email,
        subject=f"Picks lock soon: {matchup} - {settings.app_name}",
        plain_text=plain_text,
        html_content=html_content,
    )
