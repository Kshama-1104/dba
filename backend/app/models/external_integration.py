from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class ExternalIntegration(Base):
    __tablename__ = "external_integrations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")
    credentials_encrypted = Column(Text, nullable=False)
    sync_status = Column(String(50), nullable=False, default="IDLE")
    last_synced_at = Column(DateTime, nullable=True)
    sync_error = Column(Text, nullable=True)
    metadata_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company")
    insights = relationship("CompanySocialInsight", back_populates="integration", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "platform", name="uq_company_platform"),
        Index("ix_external_integrations_tenant_status", "company_id", "status"),
    )


class CompanySocialInsight(Base):
    __tablename__ = "company_social_insights"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(Integer, ForeignKey("external_integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    source_url = Column(String(1000), nullable=True)
    author = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    freshness_score = Column(Float, default=1.0, nullable=False)
    embedding = Column(Vector(384), nullable=True)
    metadata_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    integration = relationship("ExternalIntegration", back_populates="insights")

    __table_args__ = (
        UniqueConstraint("company_id", "platform", "external_id", name="uq_tenant_platform_external_id"),
        Index("ix_company_social_insights_tenant_date", "company_id", "published_at"),
        Index("ix_company_social_insights_tenant_hash", "company_id", "content_hash"),
    )
