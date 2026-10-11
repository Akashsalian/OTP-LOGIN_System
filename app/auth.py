import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from config import OTP_TTL_SECONDS, MAX_OTP_ATTEMPTS, RESEND_COOLDOWN_SECONDS, SESSION_COOKIE_NAME, get_settings
from .models import User, EmailOtp, UserSession
from .errors import AppError, EmailDeliveryError
from .email_service import send_otp_email

def utcnow():
    # Naive UTC matches MySQL DATETIME columns in schema.sql.
    return datetime.utcnow()

def normalise_email(email: str) -> str:
    return email.strip().lower()

def otp_digest(otp: str) -> str:
    return hashlib.sha256(otp.encode("ascii")).hexdigest()

def _send_code(db: Session, user: User, purpose: str):
    now = utcnow()
    latest = db.scalar(select(EmailOtp).where(
        EmailOtp.user_id == user.id, EmailOtp.purpose == purpose
    ).order_by(EmailOtp.created_at.desc(), EmailOtp.id.desc()).limit(1))
    if latest and (now - latest.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
        retry = max(1, RESEND_COOLDOWN_SECONDS - int((now - latest.created_at).total_seconds()))
        raise AppError(429, "resend_cooldown", "Please wait before requesting another OTP.", retry)
    db.execute(update(EmailOtp).where(
        EmailOtp.user_id == user.id, EmailOtp.purpose == purpose, EmailOtp.is_used.is_(False)
    ).values(is_used=True))
    otp = f"{secrets.randbelow(1_000_000):06d}"
    record = EmailOtp(user_id=user.id, otp_hash=otp_digest(otp), purpose=purpose,
                      expires_at=now + timedelta(seconds=OTP_TTL_SECONDS), is_used=False, attempts=0)
    db.add(record)
    db.flush()
    try:
        send_otp_email(user.email, user.name, otp, purpose)
    except EmailDeliveryError:
        db.delete(record)
        db.commit()
        raise
    db.commit()
    return {"success": True, "message": "OTP sent to your email.", "expires_in": OTP_TTL_SECONDS,
            "resend_after": RESEND_COOLDOWN_SECONDS}

def register(db: Session, name: str, email: str):
    email = normalise_email(email)
    existing = db.scalar(select(User).where(User.email == email))
    if existing and existing.is_verified:
        raise AppError(409, "email_already_registered", "This email is already registered.")
    if existing:
        existing.name = " ".join(name.split())
    else:
        existing = User(name=" ".join(name.split()), email=email, is_verified=False)
        db.add(existing)
        db.flush()
    db.commit()
    return {"success": True, "message": "Registration started. Verify your email to finish registration."}

def send_registration_otp(db: Session, email: str):
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    if not user:
        raise AppError(404, "registration_not_found", "No pending registration found. Please register first.")
    if user.is_verified:
        raise AppError(409, "email_already_registered", "This email is already registered.")
    return _send_code(db, user, "registration")

def verify_registration_otp(db: Session, email: str, otp: str):
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    record = _latest_otp(db, user, "registration")
    _verify_record(db, record, otp)
    user.is_verified = True
    db.commit()
    return {"success": True, "message": "Email verified successfully. You can now log in."}


def send_login_otp(db: Session, email: str):
    email = normalise_email(email)

    user = db.scalar(
        select(User).where(
            User.email == email,
            User.is_verified.is_(True),
        )
    )

    if not user:
        return {
            "success": True,
            "registered": False,
            "message": "This email is not registered. Please register first.",
        }

    result = _send_code(db, user, "login")
    result["registered"] = True
    return result


def verify_login_otp(db: Session, email: str, otp: str, ip: str | None, user_agent: str | None):
    user = db.scalar(select(User).where(User.email == normalise_email(email), User.is_verified.is_(True)))
    record = _latest_otp(db, user, "login")
    _verify_record(db, record, otp)
    now = utcnow()
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    db.add(UserSession(
        token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
        expires_at=now + timedelta(hours=settings.session_hours),
        ip_address=ip, user_agent=(user_agent or "")[:255] or None,
    ))
    user.last_login = now
    db.commit()
    return {"success": True, "message": "Login successful.", "redirect": "/dashboard",
            "user": {"name": user.name, "email": user.email, "last_login": now.isoformat() + "Z"},
            "session_token": token, "session_hours": settings.session_hours}

def _latest_otp(db: Session, user: User | None, purpose: str):
    if not user:
        raise AppError(400, "otp_not_found", "Incorrect OTP. Please try again.")
    record = db.scalar(select(EmailOtp).where(
        EmailOtp.user_id == user.id, EmailOtp.purpose == purpose, EmailOtp.is_used.is_(False)
    ).order_by(EmailOtp.created_at.desc(), EmailOtp.id.desc()).limit(1))
    if not record:
        raise AppError(400, "otp_not_found", "Incorrect OTP. Please try again.")
    return record

def _verify_record(db: Session, record: EmailOtp, otp: str):
    now = utcnow()
    if record.expires_at <= now:
        record.is_used = True
        db.commit()
        raise AppError(410, "otp_expired", "OTP has expired. Request a new code.")
    if record.attempts >= MAX_OTP_ATTEMPTS:
        record.is_used = True
        db.commit()
        raise AppError(429, "too_many_attempts", "Too many attempts. Please request a new OTP.")
    if not hmac.compare_digest(record.otp_hash, otp_digest(otp)):
        record.attempts += 1
        if record.attempts >= MAX_OTP_ATTEMPTS:
            record.is_used = True
            db.commit()
            raise AppError(429, "too_many_attempts", "Too many attempts. Please request a new OTP.")
        db.commit()
        raise AppError(400, "incorrect_otp", "Incorrect OTP. Please try again.")
    record.is_used = True
    db.flush()

def get_current_user(db: Session, token: str | None):
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash, UserSession.expires_at > utcnow()))
    return row.user if row else None

def logout(db: Session, token: str | None):
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        db.query(UserSession).filter(UserSession.token_hash == token_hash).delete(synchronize_session=False)
        db.commit()
