
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    CHAR,
    Integer,
    text,
)
from sqlalchemy.dialects.mysql import INTEGER, BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        String(254), unique=True, nullable=False, index=False
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("0")
    )
    created_at: Mapped[object] = mapped_column(
        DateTime, nullable=False, server_default=text("UTC_TIMESTAMP()")
    )
    last_login: Mapped[object | None] = mapped_column(DateTime, nullable=True)

    otps: Mapped[list["EmailOtp"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class EmailOtp(Base):
    __tablename__ = "email_otps"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    otp_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    purpose: Mapped[str] = mapped_column(
        Enum("registration", "login"),
        nullable=False,
    )
    expires_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    is_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("0")
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[object] = mapped_column(
        DateTime, nullable=False, server_default=text("UTC_TIMESTAMP()")
    )

    user: Mapped[User] = relationship(back_populates="otps")

    __table_args__ = (
        Index(
            "idx_email_otps_lookup",
            "user_id",
            "purpose",
            "is_used",
            "created_at",
        ),
        Index("idx_email_otps_expires", "expires_at"),
    )


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    token_hash: Mapped[str] = mapped_column(
        CHAR(64), unique=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[object] = mapped_column(
        DateTime, nullable=False, server_default=text("UTC_TIMESTAMP()")
    )
    expires_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_expires", "expires_at"),
    )
