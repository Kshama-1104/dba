import enum
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class MemoryType(str, enum.Enum):
    SEMANTIC = "SEMANTIC"       # Stable facts (positioning, target market, products, terminology)
    EPISODIC = "EPISODIC"       # Historical interactions/events (topic selections, editor decisions)
    PROCEDURAL = "PROCEDURAL"   # Persistent operational preferences (tone, framing, CTA style)


class MemorySource(str, enum.Enum):
    COMPANY_PROFILE = "COMPANY_PROFILE"
    EDITOR_CHAT = "EDITOR_CHAT"
    REVIEWER_FEEDBACK = "REVIEWER_FEEDBACK"
    EXPLICIT_USER = "EXPLICIT_USER"
    SYSTEM_CONFIRMED = "SYSTEM_CONFIRMED"


class MemoryConfidence(str, enum.Enum):
    HIGH = "HIGH"       # Explicitly stated/confirmed by user or admin
    MEDIUM = "MEDIUM"   # Repeated consistent preference
    LOW = "LOW"         # Inferred from conversation / candidate


class MemoryStatus(str, enum.Enum):
    CANDIDATE = "CANDIDATE"     # AI proposed, awaiting explicit confirmation
    ACTIVE = "ACTIVE"           # Verified, active memory participating in retrieval
    SUPERSEDED = "SUPERSEDED"   # Replaced by newer memory, preserved for audit
    ARCHIVED = "ARCHIVED"       # Retired/deactivated memory


class CompanyMemory(Base):
    __tablename__ = "company_memories"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type = Column(
        Enum(MemoryType, name="memorytype", native_enum=False),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    source = Column(
        Enum(MemorySource, name="memorysource", native_enum=False),
        nullable=False,
        default=MemorySource.EXPLICIT_USER,
    )
    confidence = Column(
        Enum(MemoryConfidence, name="memoryconfidence", native_enum=False),
        nullable=False,
        default=MemoryConfidence.HIGH,
    )
    importance = Column(Integer, nullable=False, default=3)  # Scale 1 (low) to 5 (critical)
    status = Column(
        Enum(MemoryStatus, name="memorystatus", native_enum=False),
        nullable=False,
        default=MemoryStatus.ACTIVE,
        index=True,
    )
    superseded_by_id = Column(
        Integer,
        ForeignKey("company_memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    embedding = Column(Vector(384), nullable=True)
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_payload = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)

    # Relationships
    company = relationship("Company")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    superseded_by = relationship(
        "CompanyMemory",
        remote_side=[id],
        foreign_keys=[superseded_by_id],
    )

    __table_args__ = (
        Index("ix_company_memories_tenant_status", "company_id", "status"),
        Index("ix_company_memories_tenant_type", "company_id", "memory_type"),
    )
