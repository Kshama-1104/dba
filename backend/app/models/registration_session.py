from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class RegistrationSession(Base):
    __tablename__ = "registration_sessions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    registration_token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    company_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    logo_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    company_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    industry: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    country_region: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    company_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )

    notification_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    otp_code_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    otp_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    otp_resend_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    captcha_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    captcha_refresh_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    captcha_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    captcha_code_hash: Mapped[str | None] = mapped_column(
    String(255),
    nullable=True,
)

    current_step: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )