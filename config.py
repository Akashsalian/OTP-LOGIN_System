"""Application settings."""
from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OTP_LENGTH = 6
OTP_TTL_SECONDS = 300
RESEND_COOLDOWN_SECONDS = 60
MAX_OTP_ATTEMPTS = 3
SESSION_COOKIE_NAME = "otp_session"

class ConfigError(RuntimeError):
    pass

def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a whole number.") from exc

@dataclass(frozen=True)
class Settings:
    database_url: str | URL
    secret_key: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_from_name: str
    smtp_use_tls: bool
    cookie_secure: bool
    session_hours: int
    allowed_origins: tuple[str, ...]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password)

def _build_database_url() -> str | URL:
    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        return explicit
    user = os.getenv("DB_USER", "").strip()
    if not user:
        raise ConfigError("DB_USER is not set. Copy .env.example to .env and fill in your MySQL details.")
    return URL.create(
        "mysql+pymysql",
        username=user,
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "127.0.0.1").strip(),
        port=_get_int("DB_PORT", 3306),
        database=os.getenv("DB_NAME", "otp_login").strip(),
        query={"charset": "utf8mb4"},
    )

@lru_cache
def get_settings() -> Settings:
    secret = os.getenv("SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise ConfigError('SECRET_KEY is missing or shorter than 32 characters. Generate one with: python -c "import secrets; print(secrets.token_hex(32))"')
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    origins = tuple(o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip())
    return Settings(
        database_url=_build_database_url(), secret_key=secret,
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        smtp_port=_get_int("SMTP_PORT", 587),
        smtp_username=smtp_username,
        smtp_password=os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip(),
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL", "").strip() or smtp_username,
        smtp_from_name=os.getenv("SMTP_FROM_NAME", "Passcode").strip(),
        smtp_use_tls=_get_bool("SMTP_USE_TLS", True),
        cookie_secure=_get_bool("COOKIE_SECURE", False),
        session_hours=_get_int("SESSION_HOURS", 8),
        allowed_origins=origins,
    )
