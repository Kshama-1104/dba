from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class WordPressConnectionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class WordPressPublicationStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED_TERMINAL = "FAILED_TERMINAL"


class WordPressConnection(Base):
    __tablename__ = "wordpress_connections"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    site_url = Column(String(500), nullable=False)
    username = Column(String(255), nullable=False)
    encrypted_credential = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default=WordPressConnectionStatus.ACTIVE.value)
    default_post_status = Column(String(32), nullable=False, default="publish")
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    publication_records = relationship(
        "WordPressPublicationRecord",
        back_populates="connection",
    )

    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_wordpress_connection"),
    )


class WordPressPublicationRecord(Base):
    __tablename__ = "wordpress_publication_records"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey("wordpress_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schedule_id = Column(
        Integer,
        ForeignKey("blog_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_job_id = Column(
        Integer,
        ForeignKey("blog_publication_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    blog_id = Column(
        Integer,
        ForeignKey("blogs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_id = Column(
        Integer,
        ForeignKey("blog_revisions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    publication_idempotency_key = Column(String(128), nullable=False, index=True)
    status = Column(
        String(32),
        nullable=False,
        default=WordPressPublicationStatus.IN_PROGRESS.value,
        index=True,
    )
    claim_worker_id = Column(String(128), nullable=True)
    claim_lease_until = Column(DateTime(timezone=True), nullable=True, index=True)
    external_post_id = Column(String(64), nullable=True)
    external_url = Column(String(1000), nullable=True)
    post_status = Column(String(32), nullable=False, default="publish")
    target_site_url = Column(String(500), nullable=False)
    target_username = Column(String(255), nullable=False)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company")
    connection = relationship("WordPressConnection", back_populates="publication_records")
    schedule = relationship("BlogSchedule")
    last_job = relationship("BlogPublicationJob")
    blog = relationship("Blog")
    revision = relationship("BlogRevision")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "publication_idempotency_key",
            name="uq_wp_pub_records_company_key",
        ),
        Index("ix_wp_pub_records_company_key", "company_id", "publication_idempotency_key"),
        Index("ix_wp_pub_records_blog_id", "blog_id"),
    )
