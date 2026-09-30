"""
Phase 7 — SEO + Format Validation Test Suite

Covers all 45 validation, security, persistence, and regression test scenarios:

FORMAT:
 1. valid baseline format
 2. missing title
 3. missing introduction
 4. missing conclusion
 5. missing body section
 6. empty section
 7. orphan H3
 8. invalid heading hierarchy
 9. duplicate heading
10. missing company required section
11. valid company-specific format
12. different company format
13. company format tenant isolation

SEO:
14. valid SEO title
15. short SEO title
16. long SEO title
17. missing SEO title
18. keyword missing from SEO title
19. valid meta description
20. short meta description
21. long meta description
22. missing meta description
23. keyword missing from intro
24. keyword missing from H2
25. keyword present in title/intro/H2
26. missing primary keyword
27. slug validation
28. keyword stuffing warning behavior
29. Unicode content

SECURITY:
30. unauthenticated validation
31. reviewer cannot trigger validation
32. editor can validate
33. admin can validate
34. reviewer can read validation
35. cross-tenant POST validation
36. cross-tenant GET validation
37. client company_id tampering
38. nonexistent blog

PERSISTENCE:
39. validation result persisted
40. GET returns persisted validation
41. repeated validation updates latest result
42. existing generation_metadata is preserved

API:
43. successful POST response
44. successful GET response
45. validation-not-yet-run behavior
"""

import json
from typing import Any, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.blog import Blog, BlogStatus
from backend.app.models.blog_format import BlogFormat
from backend.app.models.company import Company
from backend.app.models.topic_candidate import TopicCandidate, TopicStatus
from backend.app.models.user import User, UserRole
from backend.app.services.blog_format_service import create_or_update_blog_format
from backend.app.services.blog_validation_service import BlogValidationService



# ── Helpers & Fixtures ──────────────────────────────────────────────

def create_valid_draft_dict(
    primary_keyword: str = "cloud observability",
    extra_sections: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return a completely valid structured draft dict conforming to SEO targets."""
    # 57 characters:
    seo_title = f"{primary_keyword.title()}: Complete Architecture Guide for 2026"
    if len(seo_title) < 55:
        seo_title = seo_title.ljust(58, "!")
    elif len(seo_title) > 60:
        seo_title = seo_title[:58]

    # Exactly 150 characters meta description with CTA "Discover":
    meta_desc = (
        f"Discover the complete guide to {primary_keyword} for modern distributed systems. "
        "Learn key architectural patterns, telemetry tools, and metrics today."
    )
    if len(meta_desc) < 140:
        meta_desc = meta_desc.ljust(145, ".")
    elif len(meta_desc) > 160:
        meta_desc = meta_desc[:150]

    sections = [
        {
            "heading": f"Fundamental Pillars of {primary_keyword.title()}",
            "level": 2,
            "content": (
                "Observability requires detailed traces, structured metrics, and enriched log aggregation. "
                "Each service must produce correlation IDs across distributed transaction boundaries."
            ),
        },
        {
            "heading": "Implementing Distributed Telemetry Pipelines",
            "level": 2,
            "content": (
                "Telemetry collectors batch spans and forward structured data downstream to reliable storage backends. "
                "Sampling rules ensure high volume traces do not saturate networking buffers."
            ),
        },
        {
            "heading": "Sampling and High-Cardinality Metrics",
            "level": 3,
            "content": (
                "High cardinality dimensions enable engineering teams to isolate specific tenant failures instantly. "
                "Dynamic downsampling controls retention storage costs effectively over time."
            ),
        },
    ]
    if extra_sections:
        sections.extend(extra_sections)

    return {
        "seo_title": seo_title,
        "meta_description": meta_desc,
        "primary_keyword": primary_keyword,
        "h1_title": f"The Comprehensive Guide to {primary_keyword.title()}",
        "introduction": (
            f"Mastering modern {primary_keyword} has become essential for high-velocity software delivery teams. "
            "In this detailed architectural overview, we examine how resilient organizations build scalable observability systems."
        ),
        "sections": sections,
        "conclusion": (
            "Robust observability transforms chaotic incidents into systematic diagnostic workflows. "
            "Invest in uniform tracing protocols to empower your engineering squads."
        ),
        "call_to_action": "Schedule an architecture review with our observability experts.",
    }


def make_test_blog(
    db: Session,
    company: Company,
    user: User,
    draft_dict: Optional[Dict[str, Any]] = None,
    slug: str = "comprehensive-guide-to-cloud-observability",
    primary_keyword: str = "cloud observability",
    seo_title: Optional[str] = None,
    meta_description: Optional[str] = None,
    generation_metadata: Optional[Dict[str, Any]] = None,
) -> Blog:
    """Helper to persist a test blog with topic candidate and initial metadata."""
    topic = TopicCandidate(
        company_id=company.id,
        created_by=user.id,
        title="Comprehensive Guide to Cloud Observability",
        angle="Engineering best practices",
        rationale="High developer demand",
        target_audience="DevOps and SREs",
        primary_keyword=primary_keyword,
        status=TopicStatus.USED,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)

    draft = dict(draft_dict) if draft_dict else create_valid_draft_dict(primary_keyword=primary_keyword)
    actual_seo_title = seo_title if seo_title is not None else draft.get("seo_title", "")
    actual_meta_desc = meta_description if meta_description is not None else draft.get("meta_description", "")
    if seo_title is not None:
        draft["seo_title"] = seo_title
    if meta_description is not None:
        draft["meta_description"] = meta_description


    blog = Blog(
        company_id=company.id,
        topic_candidate_id=topic.id,
        created_by_user_id=user.id,
        title=draft.get("h1_title", "Comprehensive Guide to Cloud Observability"),
        slug=slug,
        primary_keyword=primary_keyword,
        seo_title=actual_seo_title,
        meta_description=actual_meta_desc,
        content_json=draft,
        content_markdown="# Markdown content for test blog",
        status=BlogStatus.DRAFT,
        format_version=1,
        generation_metadata=generation_metadata or {
            "attempts": 1,
            "provider": "external",
            "model": "deepseek-chat",
            "quality_passed": True,
        },
    )
    db.add(blog)
    db.commit()
    db.refresh(blog)
    return blog


@pytest.fixture
def phase7_setup(db_session: Session, create_company, create_user):
    """Setup company A & B with full suite of users."""
    comp_a = create_company(name="Company A Tech")
    admin_a = create_user(company_id=comp_a.id, role=UserRole.COMPANY_ADMIN, email="admin@companya.com")
    editor_a = create_user(company_id=comp_a.id, role=UserRole.EDITOR, email="editor@companya.com")
    reviewer_a = create_user(company_id=comp_a.id, role=UserRole.REVIEWER, email="reviewer@companya.com")

    comp_b = create_company(name="Company B Cloud")
    admin_b = create_user(company_id=comp_b.id, role=UserRole.COMPANY_ADMIN, email="admin@companyb.com")
    editor_b = create_user(company_id=comp_b.id, role=UserRole.EDITOR, email="editor@companyb.com")
    reviewer_b = create_user(company_id=comp_b.id, role=UserRole.REVIEWER, email="reviewer@companyb.com")

    return {
        "comp_a": comp_a,
        "admin_a": admin_a,
        "editor_a": editor_a,
        "reviewer_a": reviewer_a,
        "comp_b": comp_b,
        "admin_b": admin_b,
        "editor_b": editor_b,
        "reviewer_b": reviewer_b,
    }


# ── FORMAT VALIDATION TESTS ──────────────────────────────────────────

def test_01_valid_baseline_format(db_session: Session, phase7_setup):
    """1. Valid baseline draft passes all format requirements with 0 errors."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert report.baseline_sections_valid is True
    assert report.h1_title_valid is True
    assert report.introduction_valid is True
    assert report.conclusion_valid is True
    assert report.sections_valid is True
    assert report.heading_hierarchy_valid is True
    errors = [f for f in report.findings if f.severity == "error"]
    assert len(errors) == 0


def test_02_missing_title(db_session: Session, phase7_setup):
    """2. Missing or empty title produces a blocking format error."""
    draft = create_valid_draft_dict()
    draft["h1_title"] = ""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)
    blog.title = ""
    db_session.commit()

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert report.h1_title_valid is False
    assert report.baseline_sections_valid is False
    title_errors = [f for f in report.findings if f.rule in ("title_required", "title_meaningful")]
    assert len(title_errors) >= 1
    assert title_errors[0].severity == "error"


def test_03_missing_introduction(db_session: Session, phase7_setup):
    """3. Missing introduction produces a blocking format error."""
    draft = create_valid_draft_dict()
    draft["introduction"] = ""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert report.introduction_valid is False
    assert report.baseline_sections_valid is False
    intro_errors = [f for f in report.findings if f.rule == "introduction_required"]
    assert len(intro_errors) == 1
    assert intro_errors[0].severity == "error"


def test_04_missing_conclusion(db_session: Session, phase7_setup):
    """4. Missing conclusion produces a blocking format error."""
    draft = create_valid_draft_dict()
    draft["conclusion"] = ""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert report.conclusion_valid is False
    assert report.baseline_sections_valid is False
    conc_errors = [f for f in report.findings if f.rule == "conclusion_required"]
    assert len(conc_errors) == 1


def test_05_missing_body_section(db_session: Session, phase7_setup):
    """5. Draft with zero body sections produces a blocking format error."""
    draft = create_valid_draft_dict()
    draft["sections"] = []
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert report.sections_valid is False
    sec_errors = [f for f in report.findings if f.rule == "sections_required"]
    assert len(sec_errors) == 1


def test_06_empty_section(db_session: Session, phase7_setup):
    """6. Section with empty heading or empty content produces an error."""
    draft = create_valid_draft_dict()
    draft["sections"][0]["heading"] = ""
    draft["sections"][1]["content"] = "Too short"
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert report.sections_valid is False
    empty_heading_errs = [f for f in report.findings if f.rule == "section_heading_required"]
    assert len(empty_heading_errs) == 1
    short_content_errs = [f for f in report.findings if f.rule == "section_content_length"]
    assert len(short_content_errs) == 1


def test_07_orphan_h3(db_session: Session, phase7_setup):
    """7. An H3 section preceding any H2 produces an orphan_h3 error."""
    draft = create_valid_draft_dict()
    # Put H3 first
    draft["sections"][0]["level"] = 3
    draft["sections"][1]["level"] = 2
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert report.heading_hierarchy_valid is False
    orphan_errors = [f for f in report.findings if f.rule == "orphan_h3"]
    assert len(orphan_errors) == 1


def test_08_invalid_heading_hierarchy(db_session: Session, phase7_setup):
    """8. Invalid heading levels (level 1 in body or level 4) produce hierarchy errors."""
    draft = create_valid_draft_dict()
    draft["sections"][0]["level"] = 1  # Unexpected H1 in body
    draft["sections"][1]["level"] = 4  # Invalid level
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert report.heading_hierarchy_valid is False
    h1_body_errs = [f for f in report.findings if f.rule == "unexpected_h1_in_body"]
    assert len(h1_body_errs) == 1
    invalid_level_errs = [f for f in report.findings if f.rule == "invalid_heading_level"]
    assert len(invalid_level_errs) == 1


def test_09_duplicate_heading(db_session: Session, phase7_setup):
    """9. Duplicate section headings produce a warning, not a blocking error."""
    draft = create_valid_draft_dict()
    draft["sections"][1]["heading"] = draft["sections"][0]["heading"]
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog)

    assert len(report.duplicate_headings) == 1
    dup_warnings = [f for f in report.findings if f.rule == "duplicate_heading"]
    assert len(dup_warnings) == 1
    assert dup_warnings[0].severity == "warning"


def test_10_missing_company_required_section(db_session: Session, phase7_setup):
    """10. Missing company-specific required section produces a blocking error."""
    comp = phase7_setup["comp_a"]
    # Save active format requiring "Implementation Architecture"
    create_or_update_blog_format(
        db=db_session,
        company_id=comp.id,
        user_id=phase7_setup["admin_a"].id,
        format_in={
            "required_sections": ["Title", "Introduction", "Headings", "Main Content", "Conclusion", "Architecture Deep Dive"],
        },
    )

    blog = make_test_blog(db_session, comp, phase7_setup["editor_a"])
    active_format = db_session.query(BlogFormat).filter(BlogFormat.company_id == comp.id, BlogFormat.is_active == True).first()

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog, active_format=active_format)

    assert report.company_format_checked is True
    assert report.company_sections_valid is False
    assert "Architecture Deep Dive" in report.missing_company_sections
    missing_errs = [f for f in report.findings if f.rule == "missing_company_required_section"]
    assert len(missing_errs) == 1


def test_11_valid_company_specific_format(db_session: Session, phase7_setup):
    """11. When company required section is present in headings, company check passes."""
    comp = phase7_setup["comp_a"]
    create_or_update_blog_format(
        db=db_session,
        company_id=comp.id,
        user_id=phase7_setup["admin_a"].id,
        format_in={
            "required_sections": ["Title", "Introduction", "Headings", "Main Content", "Conclusion", "Case Study Analysis"],
        },
    )

    extra_sec = [{
        "heading": "Case Study Analysis in Production",
        "level": 2,
        "content": (
            "In our enterprise banking deployment, adopting distributed tracing reduced "
            "mean time to resolution by over sixty-five percent across global Kubernetes clusters."
        ),
    }]

    draft = create_valid_draft_dict(extra_sections=extra_sec)
    blog = make_test_blog(db_session, comp, phase7_setup["editor_a"], draft_dict=draft)
    active_format = db_session.query(BlogFormat).filter(BlogFormat.company_id == comp.id, BlogFormat.is_active == True).first()

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog, active_format=active_format)

    assert report.company_format_checked is True
    assert report.company_sections_valid is True
    assert len(report.missing_company_sections) == 0


def test_12_different_company_format(db_session: Session, phase7_setup):
    """12. Company B format requirements do not evaluate against Company A."""
    comp_a = phase7_setup["comp_a"]
    comp_b = phase7_setup["comp_b"]

    # Company B requires "Security Review"
    create_or_update_blog_format(
        db=db_session,
        company_id=comp_b.id,
        user_id=phase7_setup["admin_b"].id,
        format_in={
            "required_sections": ["Title", "Introduction", "Headings", "Main Content", "Conclusion", "Security Review"],
        },
    )

    # Blog belongs to Company A with no active format
    blog_a = make_test_blog(db_session, comp_a, phase7_setup["editor_a"])
    format_a = db_session.query(BlogFormat).filter(BlogFormat.company_id == comp_a.id, BlogFormat.is_active == True).first()

    validator = BlogValidationService(db=db_session)
    report = validator.validate_format(blog_a, active_format=format_a)

    assert report.company_format_checked is False
    assert report.company_sections_valid is True
    assert len(report.missing_company_sections) == 0


def test_13_company_format_tenant_isolation(db_session: Session, phase7_setup):
    """13. Active format lookup is strictly scoped to the blog's company."""
    comp_a = phase7_setup["comp_a"]
    comp_b = phase7_setup["comp_b"]

    create_or_update_blog_format(
        db=db_session,
        company_id=comp_a.id,
        user_id=phase7_setup["admin_a"].id,
        format_in={"required_sections": ["Title", "Introduction", "Headings", "Main Content", "Conclusion", "CompA Section"]},
    )
    create_or_update_blog_format(
        db=db_session,
        company_id=comp_b.id,
        user_id=phase7_setup["admin_b"].id,
        format_in={"required_sections": ["Title", "Introduction", "Headings", "Main Content", "Conclusion", "CompB Section"]},
    )

    format_a = db_session.query(BlogFormat).filter(BlogFormat.company_id == comp_a.id, BlogFormat.is_active == True).first()
    format_b = db_session.query(BlogFormat).filter(BlogFormat.company_id == comp_b.id, BlogFormat.is_active == True).first()

    assert format_a.company_id == comp_a.id
    assert format_b.company_id == comp_b.id
    assert "CompA Section" in format_a.format_definition
    assert "CompB Section" in format_b.format_definition


# ── SEO VALIDATION TESTS ─────────────────────────────────────────────

def test_14_valid_seo_title(db_session: Session, phase7_setup):
    """14. SEO title within 55–60 characters containing keyword passes."""
    title_58 = "Cloud Observability: Complete Modern Architecture Guide!!"
    assert len(title_58) == 57
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        primary_keyword="cloud observability",
        seo_title=title_58,
    )

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.seo_title_valid is True
    assert report.keyword_in_seo_title is True
    assert report.seo_title_length == 57
    title_findings = [f for f in report.findings if f.field == "seo_title"]
    assert len(title_findings) == 0


def test_15_short_seo_title(db_session: Session, phase7_setup):
    """15. SEO title shorter than 55 chars produces warning but does not block keyword validity."""
    short_title = "Cloud Observability Guide"  # 25 chars
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        primary_keyword="cloud observability",
        seo_title=short_title,
    )

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.keyword_in_seo_title is True
    len_warnings = [f for f in report.findings if f.rule == "seo_title_length"]
    assert len(len_warnings) == 1
    assert len_warnings[0].severity == "warning"
    assert len_warnings[0].details["actual_length"] == 25


def test_16_long_seo_title(db_session: Session, phase7_setup):
    """16. SEO title longer than 60 chars produces warning."""
    long_title = "The Definitive Cloud Observability Guide For Distributed Microservices Architecture"  # 83 chars
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        primary_keyword="cloud observability",
        seo_title=long_title,
    )

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    len_warnings = [f for f in report.findings if f.rule == "seo_title_length"]
    assert len(len_warnings) == 1
    assert len_warnings[0].severity == "warning"


def test_17_missing_seo_title(db_session: Session, phase7_setup):
    """17. Missing SEO title produces a blocking error."""
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        seo_title="",
    )
    blog.content_json["seo_title"] = ""
    db_session.commit()

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.seo_title_valid is False
    title_errs = [f for f in report.findings if f.rule == "seo_title_required"]
    assert len(title_errs) == 1
    assert title_errs[0].severity == "error"


def test_18_keyword_missing_from_seo_title(db_session: Session, phase7_setup):
    """18. Primary keyword absent from SEO title produces a blocking error."""
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        primary_keyword="cloud observability",
        seo_title="Complete Distributed Microservices Monitoring and Tracing Guide",
    )

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.keyword_in_seo_title is False
    assert report.seo_title_valid is False
    kw_title_errs = [f for f in report.findings if f.rule == "keyword_in_seo_title"]
    assert len(kw_title_errs) == 1


def test_19_valid_meta_description(db_session: Session, phase7_setup):
    """19. Valid meta description (140–160 chars with CTA) passes without warnings."""
    meta = (
        "Discover the complete guide to cloud observability for modern distributed systems. "
        "Learn key architectural patterns, telemetry tools, and metrics today."
    )
    assert 140 <= len(meta) <= 160
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        meta_description=meta,
    )

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.meta_description_valid is True
    assert report.meta_description_length == len(meta)
    meta_findings = [f for f in report.findings if f.field == "meta_description"]
    assert len(meta_findings) == 0


def test_20_short_meta_description(db_session: Session, phase7_setup):
    """20. Meta description under 140 chars produces a warning."""
    short_meta = "Discover cloud observability patterns in this concise engineering overview."
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        meta_description=short_meta,
    )

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    len_warnings = [f for f in report.findings if f.rule == "meta_description_length"]
    assert len(len_warnings) == 1
    assert len_warnings[0].severity == "warning"


def test_21_long_meta_description(db_session: Session, phase7_setup):
    """21. Meta description exceeding 160 chars produces a warning."""
    long_meta = (
        "Discover cloud observability patterns in this comprehensive engineering overview. "
        "We discuss distributed traces, OpenTelemetry collectors, high-cardinality metrics, and alert thresholds in detail."
    )
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        meta_description=long_meta,
    )

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    len_warnings = [f for f in report.findings if f.rule == "meta_description_length"]
    assert len(len_warnings) == 1
    assert len_warnings[0].severity == "warning"


def test_22_missing_meta_description(db_session: Session, phase7_setup):
    """22. Missing meta description produces a blocking error."""
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        meta_description="",
    )
    blog.content_json["meta_description"] = ""
    db_session.commit()

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.meta_description_valid is False
    meta_errs = [f for f in report.findings if f.rule == "meta_description_required"]
    assert len(meta_errs) == 1


def test_23_keyword_missing_from_intro(db_session: Session, phase7_setup):
    """23. Keyword absent from introduction produces a blocking error."""
    draft = create_valid_draft_dict(primary_keyword="cloud observability")
    draft["introduction"] = (
        "Mastering distributed systems telemetry has become critical for engineering teams. "
        "In this overview we evaluate modern microservices monitoring workflows."
    )
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.keyword_in_introduction is False
    kw_intro_errs = [f for f in report.findings if f.rule == "keyword_in_introduction"]
    assert len(kw_intro_errs) == 1


def test_24_keyword_missing_from_h2(db_session: Session, phase7_setup):
    """24. Keyword absent from all H2 headings produces a blocking error."""
    draft = create_valid_draft_dict(primary_keyword="cloud observability")
    # Remove keyword from H2 headings (only put in H3)
    draft["sections"][0]["heading"] = "Core Architectural Concepts"
    draft["sections"][1]["heading"] = "Telemetry Pipelines and Logs"
    draft["sections"][2]["heading"] = "Deep Cloud Observability Tracing"  # This is H3!
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft)

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.keyword_in_h2 is False
    kw_h2_errs = [f for f in report.findings if f.rule == "keyword_in_h2"]
    assert len(kw_h2_errs) == 1


def test_25_keyword_present_in_title_intro_h2(db_session: Session, phase7_setup):
    """25. When keyword appears in SEO Title, Intro, and H2, all 3 checks pass."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.keyword_in_seo_title is True
    assert report.keyword_in_introduction is True
    assert report.keyword_in_h2 is True
    assert report.primary_keyword == "cloud observability"


def test_26_missing_primary_keyword(db_session: Session, phase7_setup):
    """26. Missing primary keyword produces a blocking error."""
    draft = create_valid_draft_dict()
    draft["primary_keyword"] = ""
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        draft_dict=draft,
        primary_keyword="",
    )

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    kw_errs = [f for f in report.findings if f.rule == "primary_keyword_required"]
    assert len(kw_errs) == 1


def test_27_slug_validation(db_session: Session, phase7_setup):
    """27. Valid slug passes; malformed slugs with spaces or uppercase fail."""
    # Valid
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], slug="cloud-observability-guide")
    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)
    assert report.slug_valid is True

    # Malformed (spaces and uppercase)
    blog.slug = "Invalid Slug With Spaces"
    report_bad = validator.validate_seo(blog)
    assert report_bad.slug_valid is False
    slug_errs = [f for f in report_bad.findings if f.rule == "slug_format"]
    assert len(slug_errs) == 1


def test_28_keyword_stuffing_warning_behavior(db_session: Session, phase7_setup):
    """28. Excessive keyword density triggers a warning, NOT a blocking error."""
    draft = create_valid_draft_dict(primary_keyword="observability")
    # Repeatedly stuff keyword into content
    stuffed_content = ("observability " * 40) + "is very important for cloud applications."
    draft["sections"][0]["content"] = stuffed_content
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"], draft_dict=draft, primary_keyword="observability")

    validator = BlogValidationService(db=db_session)
    report = validator.validate_seo(blog)

    assert report.keyword_stuffing_warning is True
    assert report.keyword_density is not None
    assert report.keyword_density > 3.5

    # Synthesize overall result: warnings do not block passing
    format_rep = validator.validate_format(blog)
    result = validator.synthesize_validation_result(blog, format_rep, report)
    # The warning should be present
    assert any(w.rule == "keyword_stuffing_heuristic" for w in result.warnings)


def test_29_unicode_content(db_session: Session, phase7_setup):
    """29. Multi-lingual and Unicode characters process safely without encoding errors."""
    draft = create_valid_draft_dict(primary_keyword="observabilité cloud")
    draft["h1_title"] = "Guide Avancé sur l'Observabilité Cloud 🚀 — Édition 2026"
    draft["introduction"] = (
        "L'observabilité cloud moderne transforme les architectures logicielles avec des métriques précises et détaillées. "
        "Découvrez comment maîtriser les systèmes distribués de manière continue et proactive."
    )
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        draft_dict=draft,
        primary_keyword="observabilité cloud",
        slug="guide-avance-observabilite-cloud",
    )

    validator = BlogValidationService(db=db_session)
    result = validator.validate_blog(blog, persist=False)
    assert isinstance(result.passed, bool)
    assert result.seo_report.primary_keyword == "observabilité cloud"


# ── SECURITY & RBAC TESTS ────────────────────────────────────────────

def test_30_unauthenticated_validation(client: TestClient, db_session: Session, phase7_setup):
    """30. Unauthenticated POST/GET validation requests return 401 Unauthorized."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])

    res_post = client.post(f"/api/v1/blogs/{blog.id}/validate")
    assert res_post.status_code == 401

    res_get = client.get(f"/api/v1/blogs/{blog.id}/validation")
    assert res_get.status_code == 401


def test_31_reviewer_cannot_trigger_validation(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """31. Reviewer role receives 403 Forbidden when attempting POST validation."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    reviewer = phase7_setup["reviewer_a"]

    res = client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(reviewer))
    assert res.status_code == 403


def test_32_editor_can_validate(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """32. Editor role can trigger validation → 200 OK."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor = phase7_setup["editor_a"]

    res = client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(editor))
    assert res.status_code == 200
    data = res.json()
    assert data["blog_id"] == blog.id
    assert data["company_id"] == phase7_setup["comp_a"].id
    assert data["passed"] is True


def test_33_admin_can_validate(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """33. Company Admin can trigger validation → 200 OK."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    admin = phase7_setup["admin_a"]

    res = client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(admin))
    assert res.status_code == 200
    assert res.json()["blog_id"] == blog.id


def test_34_reviewer_can_read_validation(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """34. Reviewer role can read validation report once generated → 200 OK."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor = phase7_setup["editor_a"]
    reviewer = phase7_setup["reviewer_a"]

    # Trigger as editor first
    res_validate = client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(editor))
    assert res_validate.status_code == 200

    # Read as reviewer
    res_get = client.get(f"/api/v1/blogs/{blog.id}/validation", headers=auth_headers(reviewer))
    assert res_get.status_code == 200
    assert res_get.json()["blog_id"] == blog.id


def test_35_cross_tenant_post_validation(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """35. Company B user cannot trigger validation on Company A blog → 404 Not Found."""
    blog_a = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor_b = phase7_setup["editor_b"]

    res = client.post(f"/api/v1/blogs/{blog_a.id}/validate", headers=auth_headers(editor_b))
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_36_cross_tenant_get_validation(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """36. Company B user cannot read validation report for Company A blog → 404 Not Found."""
    blog_a = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor_a = phase7_setup["editor_a"]
    editor_b = phase7_setup["editor_b"]

    # Run validation for Company A
    client.post(f"/api/v1/blogs/{blog_a.id}/validate", headers=auth_headers(editor_a))

    # Read as Company B editor
    res = client.get(f"/api/v1/blogs/{blog_a.id}/validation", headers=auth_headers(editor_b))
    assert res.status_code == 404


def test_37_client_company_id_tampering(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """37. Passing body params attempting to override tenant company_id is completely ignored."""
    blog_a = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor_a = phase7_setup["editor_a"]

    # Attempt to tamper with company_id in POST body or query
    res = client.post(
        f"/api/v1/blogs/{blog_a.id}/validate?company_id=9999",
        json={"company_id": 9999},
        headers=auth_headers(editor_a),
    )
    assert res.status_code == 200
    assert res.json()["company_id"] == phase7_setup["comp_a"].id


def test_38_nonexistent_blog(client: TestClient, auth_headers, phase7_setup):
    """38. Validation request for non-existent blog ID returns 404 Not Found."""
    editor = phase7_setup["editor_a"]
    res_post = client.post("/api/v1/blogs/99999999/validate", headers=auth_headers(editor))
    assert res_post.status_code == 404

    res_get = client.get("/api/v1/blogs/99999999/validation", headers=auth_headers(editor))
    assert res_get.status_code == 404


# ── PERSISTENCE TESTS ────────────────────────────────────────────────

def test_39_validation_result_persisted(db_session: Session, phase7_setup):
    """39. Validation result is persisted in Blog.generation_metadata['validation']."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    validator = BlogValidationService(db=db_session)
    result = validator.validate_blog(blog, persist=True)

    db_session.refresh(blog)
    assert blog.generation_metadata is not None
    assert "validation" in blog.generation_metadata
    val_meta = blog.generation_metadata["validation"]
    assert val_meta["blog_id"] == blog.id
    assert val_meta["passed"] == result.passed


def test_40_get_returns_persisted_validation(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """40. GET /api/v1/blogs/{id}/validation returns the exact persisted report."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor = phase7_setup["editor_a"]

    res_post = client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(editor))
    assert res_post.status_code == 200
    post_data = res_post.json()

    res_get = client.get(f"/api/v1/blogs/{blog.id}/validation", headers=auth_headers(editor))
    assert res_get.status_code == 200
    get_data = res_get.json()

    assert get_data["blog_id"] == post_data["blog_id"]
    assert get_data["passed"] == post_data["passed"]
    assert get_data["validated_at"] == post_data["validated_at"]


def test_41_repeated_validation_updates_latest_result(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """41. Running validation a second time updates the latest report."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor = phase7_setup["editor_a"]

    res1 = client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(editor))
    assert res1.status_code == 200
    time1 = res1.json()["validated_at"]

    res2 = client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(editor))
    assert res2.status_code == 200
    time2 = res2.json()["validated_at"]

    assert time2 >= time1


def test_42_existing_generation_metadata_is_preserved(db_session: Session, phase7_setup):
    """42. Validation persistence preserves Phase 6 metadata (provider, model, attempts)."""
    initial_meta = {
        "attempts": 2,
        "provider": "external",
        "model": "deepseek-chat",
        "quality_passed": True,
        "token_usage": {"prompt": 1200, "completion": 800},
    }
    blog = make_test_blog(
        db_session,
        phase7_setup["comp_a"],
        phase7_setup["editor_a"],
        generation_metadata=initial_meta,
    )

    validator = BlogValidationService(db=db_session)
    validator.validate_blog(blog, persist=True)

    db_session.refresh(blog)
    meta = blog.generation_metadata
    assert meta["attempts"] == 2
    assert meta["provider"] == "external"
    assert meta["model"] == "deepseek-chat"
    assert meta["quality_passed"] is True
    assert meta["token_usage"] == {"prompt": 1200, "completion": 800}
    assert "validation" in meta


# ── API ENDPOINT TESTS ───────────────────────────────────────────────

def test_43_successful_post_response(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """43. Successful POST response matches BlogValidationResponse schema contract."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor = phase7_setup["editor_a"]

    res = client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(editor))
    assert res.status_code == 200
    data = res.json()

    assert "blog_id" in data
    assert "company_id" in data
    assert "passed" in data
    assert "errors" in data
    assert "warnings" in data
    assert "recommendations" in data
    assert "seo_report" in data
    assert "format_report" in data
    assert "validated_at" in data


def test_44_successful_get_response(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """44. Successful GET response matches BlogValidationResponse schema contract."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    admin = phase7_setup["admin_a"]

    # Validate first
    client.post(f"/api/v1/blogs/{blog.id}/validate", headers=auth_headers(admin))

    # Retrieve
    res = client.get(f"/api/v1/blogs/{blog.id}/validation", headers=auth_headers(admin))
    assert res.status_code == 200
    data = res.json()
    assert data["blog_id"] == blog.id
    assert "seo_report" in data
    assert "format_report" in data


def test_45_validation_not_yet_run_behavior(client: TestClient, auth_headers, db_session: Session, phase7_setup):
    """45. GET on a draft before validation has executed returns 404 with descriptive detail."""
    blog = make_test_blog(db_session, phase7_setup["comp_a"], phase7_setup["editor_a"])
    editor = phase7_setup["editor_a"]

    res = client.get(f"/api/v1/blogs/{blog.id}/validation", headers=auth_headers(editor))
    assert res.status_code == 404
    assert "not been executed" in res.json()["detail"].lower()
