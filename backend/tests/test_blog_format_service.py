import pytest
from sqlalchemy.orm import Session

from backend.app.schemas.blog_format import (
    BlogFormatCreate,
    BlogFormatDefinition,
)
from backend.app.services.blog_format_service import (
    activate_blog_format_version,
    create_or_update_blog_format,
    get_active_blog_format,
    get_blog_format_by_version,
    list_blog_format_versions,
)


def test_get_nonexistent_blog_format_returns_none(
    db_session: Session,
    create_company,
):
    """
    Querying the active format for a company with no configured format returns None.
    """
    company = create_company()
    active_format = get_active_blog_format(db_session, company.id)
    assert active_format is None


def test_create_initial_blog_format_version_1(
    db_session: Session,
    create_company,
    create_user,
):
    """
    Initial creation of a Global Blog Format sets version 1 and marks it active.
    """
    company = create_company()
    user = create_user(company_id=company.id)

    payload = BlogFormatCreate(
        title_structure="H1 with primary keyword under 60 chars",
        introduction_structure="Hook, problem articulation, thesis statement",
        heading_structure="H2 core arguments, H3 supporting sub-points",
        main_content_structure="In-depth analysis, bullet points, data callouts",
        conclusion_structure="Key takeaways, forward outlook, brand CTA",
        call_to_action="Schedule an enterprise consultation",
        preferred_writing_style="Authoritative and practical",
    )

    format_v1 = create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in=payload,
        user_id=user.id,
        activate=True,
    )

    assert format_v1.id is not None
    assert format_v1.company_id == company.id
    assert format_v1.version == 1
    assert format_v1.is_active is True
    assert format_v1.created_by == user.id

    active = get_active_blog_format(db_session, company.id)
    assert active is not None
    assert active.id == format_v1.id
    assert active.version == 1


def test_versioning_preserves_historical_format(
    db_session: Session,
    create_company,
    create_user,
):
    """
    Creating a new format version deactivates version 1, assigns version 2,
    and preserves both versions in the historical audit trail.
    """
    company = create_company()
    user = create_user(company_id=company.id)

    v1 = create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in=BlogFormatCreate(title_structure="Title V1"),
        user_id=user.id,
    )
    assert v1.version == 1
    assert v1.is_active is True

    v2 = create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in=BlogFormatCreate(title_structure="Title V2 Updated"),
        user_id=user.id,
    )
    assert v2.version == 2
    assert v2.is_active is True

    # Re-fetch V1 from DB to verify it was preserved and deactivated
    db_session.refresh(v1)
    assert v1.version == 1
    assert v1.is_active is False

    # List all versions
    all_versions = list_blog_format_versions(db_session, company.id)
    assert len(all_versions) == 2
    assert all_versions[0].version == 2
    assert all_versions[0].is_active is True
    assert all_versions[1].version == 1
    assert all_versions[1].is_active is False


def test_activate_historical_format_version(
    db_session: Session,
    create_company,
    create_user,
):
    """
    Activating a historical format version (e.g. rollback from V2 to V1)
    makes V1 active and sets V2 inactive.
    """
    company = create_company()
    user = create_user(company_id=company.id)

    v1 = create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in=BlogFormatCreate(title_structure="Title V1"),
        user_id=user.id,
    )
    v2 = create_or_update_blog_format(
        db=db_session,
        company_id=company.id,
        format_in=BlogFormatCreate(title_structure="Title V2"),
        user_id=user.id,
    )

    # Currently V2 is active
    current_active = get_active_blog_format(db_session, company.id)
    assert current_active.version == 2

    # Activate V1
    activated = activate_blog_format_version(
        db=db_session,
        company_id=company.id,
        version=1,
    )
    assert activated.version == 1
    assert activated.is_active is True

    db_session.refresh(v2)
    assert v2.is_active is False

    current_active_now = get_active_blog_format(db_session, company.id)
    assert current_active_now.version == 1


def test_activate_nonexistent_version_raises_value_error(
    db_session: Session,
    create_company,
):
    """
    Attempting to activate a version number that does not exist raises ValueError.
    """
    company = create_company()
    with pytest.raises(ValueError, match="Format version 99 not found"):
        activate_blog_format_version(db_session, company.id, 99)


def test_mandatory_baseline_sections_enforced():
    """
    Attempting to remove mandatory Level 1 system baseline sections
    (Title, Introduction, Headings, Main Content, Conclusion) raises ValueError.
    """
    # Valid with all baseline sections
    valid_def = BlogFormatDefinition(
        required_sections=[
            "Title",
            "Introduction",
            "Headings",
            "Main Content",
            "Conclusion",
            "Key Takeaways",
        ]
    )
    assert "Key Takeaways" in valid_def.required_sections

    # Invalid: missing "Conclusion"
    with pytest.raises(ValueError, match="Mandatory system baseline section 'Conclusion'"):
        BlogFormatDefinition(
            required_sections=["Title", "Introduction", "Headings", "Main Content"]
        )


def test_tenant_isolation_in_service(
    db_session: Session,
    create_company,
    create_user,
):
    """
    Formats of Company A and Company B are completely isolated.
    Versions increment independently per company.
    """
    company_a = create_company(name="Company A")
    company_b = create_company(name="Company B")
    user_a = create_user(company_id=company_a.id)
    user_b = create_user(company_id=company_b.id)

    a_v1 = create_or_update_blog_format(
        db=db_session,
        company_id=company_a.id,
        format_in=BlogFormatCreate(title_structure="Format A"),
        user_id=user_a.id,
    )
    b_v1 = create_or_update_blog_format(
        db=db_session,
        company_id=company_b.id,
        format_in=BlogFormatCreate(title_structure="Format B"),
        user_id=user_b.id,
    )

    assert a_v1.company_id == company_a.id
    assert b_v1.company_id == company_b.id
    assert a_v1.version == 1
    assert b_v1.version == 1

    # Company A cannot see Company B's version by querying
    res_b_for_a = get_blog_format_by_version(db_session, company_a.id, b_v1.version)
    assert res_b_for_a.company_id == company_a.id  # Returns A's version 1, NOT B's
    assert "Format A" in res_b_for_a.format_definition
