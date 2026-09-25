from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.company import Company
from backend.app.models.company_ai_profile import CompanyAIProfile
from backend.app.schemas.company_ai_profile import (
    CompanyAIProfileCreate,
    CompanyAIProfileUpdate,
)


def get_company_ai_profile(
    db: Session,
    company_id: int,
) -> CompanyAIProfile | None:
    """
    Retrieve the CompanyAIProfile for a specific company_id.
    Returns None if no profile exists for the company.
    """
    return db.scalar(
        select(CompanyAIProfile).where(
            CompanyAIProfile.company_id == company_id
        )
    )


def create_or_update_company_ai_profile(
    db: Session,
    company_id: int,
    profile_in: CompanyAIProfileCreate | CompanyAIProfileUpdate | dict[str, Any],
) -> CompanyAIProfile:
    """
    Create a new CompanyAIProfile or update an existing one for the specified company.
    Strict tenant isolation: company_id is derived exclusively from the authenticated context.
    """
    company = db.scalar(
        select(Company).where(Company.id == company_id)
    )
    if company is None:
        raise ValueError("Company not found.")

    profile = db.scalar(
        select(CompanyAIProfile).where(
            CompanyAIProfile.company_id == company_id
        )
    )

    if hasattr(profile_in, "model_dump"):
        data = profile_in.model_dump(exclude_unset=True)
    else:
        data = dict(profile_in)

    allowed_fields = {
        "products_services",
        "target_audience",
        "preferred_writing_style",
        "brand_voice",
        "marketing_goals",
        "company_guidelines",
        "upcoming_projects",
        "partner_companies",
        "achievements",
    }

    filtered_data = {
        k: v for k, v in data.items() if k in allowed_fields
    }

    now = datetime.utcnow()

    try:
        if profile is not None:
            for field, value in filtered_data.items():
                setattr(profile, field, value)
            profile.updated_at = now
        else:
            profile = CompanyAIProfile(
                company_id=company_id,
                created_at=now,
                updated_at=now,
                **filtered_data,
            )
            db.add(profile)

        db.commit()
        db.refresh(profile)
        return profile

    except Exception:
        db.rollback()
        raise
