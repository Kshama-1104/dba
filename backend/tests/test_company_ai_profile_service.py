import pytest
from sqlalchemy.orm import Session

from backend.app.models.company import Company
from backend.app.schemas.company_ai_profile import (
    CompanyAIProfileCreate,
    CompanyAIProfileUpdate,
)
from backend.app.services.company_ai_profile_service import (
    create_or_update_company_ai_profile,
    get_company_ai_profile,
)


def test_get_nonexistent_profile_returns_none(
    db_session: Session,
    create_company,
):
    """
    Retrieving a profile for a company that has not configured one should return None.
    """
    company = create_company()
    profile = get_company_ai_profile(db_session, company.id)
    assert profile is None


def test_create_company_ai_profile_success(
    db_session: Session,
    create_company,
):
    """
    Creating an AI profile with initial brand guidelines succeeds and sets all fields.
    """
    company = create_company()
    create_payload = CompanyAIProfileCreate(
        products_services="Cloud AI Analytics",
        target_audience="Enterprise CTOs and VP of Engineering",
        preferred_writing_style="Authoritative yet accessible",
        brand_voice="Technical, confident, innovative",
        marketing_goals="Drive B2B demo signups",
        company_guidelines="Avoid buzzwords; cite benchmarks",
        upcoming_projects="Q4 Vector Engine Release",
        partner_companies="AWS, Snowflake",
        achievements="SOC2 Type II Certified, Fast50 Winner",
    )

    profile = create_or_update_company_ai_profile(
        db=db_session,
        company_id=company.id,
        profile_in=create_payload,
    )

    assert profile is not None
    assert profile.id is not None
    assert profile.company_id == company.id
    assert profile.products_services == "Cloud AI Analytics"
    assert profile.brand_voice == "Technical, confident, innovative"
    assert profile.target_audience == "Enterprise CTOs and VP of Engineering"
    assert profile.achievements == "SOC2 Type II Certified, Fast50 Winner"
    assert profile.created_at is not None
    assert profile.updated_at is not None


def test_update_existing_company_ai_profile(
    db_session: Session,
    create_company,
):
    """
    Updating an existing profile modifies target fields, preserves unchanged fields, and updates updated_at.
    """
    company = create_company()
    initial_payload = CompanyAIProfileCreate(
        brand_voice="Informative",
        target_audience="Small Businesses",
    )
    profile = create_or_update_company_ai_profile(
        db=db_session,
        company_id=company.id,
        profile_in=initial_payload,
    )
    initial_id = profile.id
    initial_created_at = profile.created_at

    update_payload = CompanyAIProfileUpdate(
        brand_voice="Bold, visionary, conversational",
    )
    updated_profile = create_or_update_company_ai_profile(
        db=db_session,
        company_id=company.id,
        profile_in=update_payload,
    )

    assert updated_profile.id == initial_id
    assert updated_profile.brand_voice == "Bold, visionary, conversational"
    assert updated_profile.target_audience == "Small Businesses"  # Preserved
    assert updated_profile.created_at == initial_created_at


def test_create_or_update_with_dict_payload(
    db_session: Session,
    create_company,
):
    """
    Service should accept plain dictionary payloads as well as Pydantic schemas.
    """
    company = create_company()
    payload = {
        "brand_voice": "Friendly",
        "products_services": "CRM Platform",
        "arbitrary_unsupported_key": "should_be_ignored",
    }
    profile = create_or_update_company_ai_profile(
        db=db_session,
        company_id=company.id,
        profile_in=payload,
    )
    assert profile.brand_voice == "Friendly"
    assert profile.products_services == "CRM Platform"
    assert not hasattr(profile, "arbitrary_unsupported_key")


def test_create_profile_nonexistent_company_raises_value_error(
    db_session: Session,
):
    """
    Attempting to create a profile for a non-existent company_id must fail with ValueError.
    """
    with pytest.raises(ValueError, match="Company not found"):
        create_or_update_company_ai_profile(
            db=db_session,
            company_id=999999,
            profile_in=CompanyAIProfileCreate(brand_voice="Friendly"),
        )


def test_service_tenant_isolation(
    db_session: Session,
    create_company,
):
    """
    Profiles for different companies are isolated and independent.
    """
    company_a = create_company(name="Company A")
    company_b = create_company(name="Company B")

    profile_a = create_or_update_company_ai_profile(
        db=db_session,
        company_id=company_a.id,
        profile_in=CompanyAIProfileCreate(brand_voice="Voice A"),
    )
    profile_b = create_or_update_company_ai_profile(
        db=db_session,
        company_id=company_b.id,
        profile_in=CompanyAIProfileCreate(brand_voice="Voice B"),
    )

    assert profile_a.company_id == company_a.id
    assert profile_b.company_id == company_b.id
    assert profile_a.brand_voice == "Voice A"
    assert profile_b.brand_voice == "Voice B"

    # Querying A does not affect B
    fetched_a = get_company_ai_profile(db_session, company_a.id)
    fetched_b = get_company_ai_profile(db_session, company_b.id)
    assert fetched_a.id != fetched_b.id
    assert fetched_a.brand_voice == "Voice A"
    assert fetched_b.brand_voice == "Voice B"
