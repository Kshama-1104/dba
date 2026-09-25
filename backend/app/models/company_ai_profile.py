from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class CompanyAIProfile(Base):
    __tablename__ = "company_ai_profiles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    products_services: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    target_audience: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    preferred_writing_style: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    brand_voice: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    marketing_goals: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    company_guidelines: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    upcoming_projects: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    partner_companies: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    achievements: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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