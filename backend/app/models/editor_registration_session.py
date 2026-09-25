from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class EditorRegistrationSession(Base):
    __tablename__ = "editor_registration_sessions"

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

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )

    id_card_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    captcha_code_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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

    selected_reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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

    company = relationship("Company")

    selected_reviewer = relationship(
        "User",
        foreign_keys=[selected_reviewer_id],
    )