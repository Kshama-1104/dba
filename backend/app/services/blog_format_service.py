import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.models.blog_format import BlogFormat
from backend.app.models.company import Company
from backend.app.schemas.blog_format import (
    BlogFormatCreate,
    BlogFormatDefinition,
    BlogFormatUpdate,
)


def get_active_blog_format(
    db: Session,
    company_id: int,
) -> BlogFormat | None:
    """
    Retrieve the currently active Company Global Blog Format for a company.
    Returns None if no active format has been defined.
    """
    return db.scalar(
        select(BlogFormat)
        .where(
            BlogFormat.company_id == company_id,
            BlogFormat.is_active == True,  # noqa: E712
        )
        .order_by(BlogFormat.version.desc())
    )


def get_blog_format_by_version(
    db: Session,
    company_id: int,
    version: int,
) -> BlogFormat | None:
    """
    Retrieve a specific version of the Company Global Blog Format.
    """
    return db.scalar(
        select(BlogFormat).where(
            BlogFormat.company_id == company_id,
            BlogFormat.version == version,
        )
    )


def list_blog_format_versions(
    db: Session,
    company_id: int,
) -> list[BlogFormat]:
    """
    List all historical and current format versions for a company, ordered descending by version.
    """
    return list(
        db.scalars(
            select(BlogFormat)
            .where(BlogFormat.company_id == company_id)
            .order_by(BlogFormat.version.desc())
        ).all()
    )


def create_or_update_blog_format(
    db: Session,
    company_id: int,
    format_in: BlogFormatCreate | BlogFormatUpdate | BlogFormatDefinition | dict[str, Any],
    user_id: int | None = None,
    activate: bool = True,
) -> BlogFormat:
    """
    Create a new version of the Company Global Blog Format.
    Preserves historical versions in the database.
    If activate=True, marks preceding active formats as inactive and sets this version active.
    """
    company = db.scalar(
        select(Company).where(Company.id == company_id)
    )
    if company is None:
        raise ValueError("Company not found.")

    if isinstance(format_in, BlogFormatDefinition):
        definition = format_in
    elif isinstance(format_in, (BlogFormatCreate, BlogFormatUpdate)) and format_in.format_definition is not None:
        definition = format_in.format_definition
    else:
        raw_data = (
            format_in.model_dump(exclude_unset=True)
            if hasattr(format_in, "model_dump")
            else dict(format_in)
        )
        current_active = get_active_blog_format(db, company_id)
        base_data: dict[str, Any] = {}
        if current_active and current_active.format_definition:
            try:
                base_data = json.loads(current_active.format_definition)
            except Exception:
                base_data = {}

        for k, v in raw_data.items():
            if v is not None and k != "format_definition":
                base_data[k] = v

        definition = BlogFormatDefinition.model_validate(base_data)

    max_version = db.scalar(
        select(func.max(BlogFormat.version)).where(
            BlogFormat.company_id == company_id
        )
    )
    next_version = (max_version or 0) + 1
    now = datetime.utcnow()

    try:
        if activate:
            db.execute(
                update(BlogFormat)
                .where(
                    BlogFormat.company_id == company_id,
                    BlogFormat.is_active == True,  # noqa: E712
                )
                .values(
                    is_active=False,
                    updated_at=now,
                )
            )

        new_format = BlogFormat(
            company_id=company_id,
            version=next_version,
            format_definition=definition.model_dump_json(),
            is_active=activate,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(new_format)
        db.commit()
        db.refresh(new_format)
        return new_format

    except Exception:
        db.rollback()
        raise


def activate_blog_format_version(
    db: Session,
    company_id: int,
    version: int,
) -> BlogFormat:
    """
    Approve/activate a specific historical format version as the company's active format.
    Deactivates any currently active format for the company.
    """
    target = db.scalar(
        select(BlogFormat).where(
            BlogFormat.company_id == company_id,
            BlogFormat.version == version,
        )
    )
    if target is None:
        raise ValueError(
            f"Format version {version} not found for this company."
        )

    now = datetime.utcnow()
    try:
        db.execute(
            update(BlogFormat)
            .where(
                BlogFormat.company_id == company_id,
                BlogFormat.is_active == True,  # noqa: E712
            )
            .values(
                is_active=False,
                updated_at=now,
            )
        )

        target.is_active = True
        target.updated_at = now
        db.commit()
        db.refresh(target)
        return target

    except Exception:
        db.rollback()
        raise
