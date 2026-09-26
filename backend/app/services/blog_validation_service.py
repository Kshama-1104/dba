"""
Deterministic SEO + Format Validation Service — Phase 7

Provides deterministic, rule-based evaluation of generated blog drafts.
Verifies format structure, heading hierarchies, company-specific format requirements,
and SEO metrics (title length, meta description length, keyword placements, slug).

NO LLM or AI provider is invoked. Validation is purely deterministic Python logic.
"""

from datetime import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from backend.app.models.blog import Blog
from backend.app.models.blog_format import BlogFormat
from backend.app.schemas.blog import (
    BlogValidationResponse,
    FormatValidationReport,
    SeoValidationReport,
    ValidationFinding,
)

logger = logging.getLogger(__name__)

# Mandatory baseline sections as established by system architecture
MANDATORY_BASELINE_SECTIONS: List[str] = [
    "Title",
    "Introduction",
    "Headings",
    "Main Content",
    "Conclusion",
]

# Actionable Call-To-Action verbs for meta description inspection
CTA_ACTION_VERBS: List[str] = [
    "discover",
    "learn",
    "explore",
    "read",
    "find out",
    "see how",
    "get started",
    "join",
    "try",
    "check out",
    "unlock",
    "master",
]


class BlogValidationService:
    """
    Deterministic SEO and Format Validation Engine for Phase 7.
    """

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db

    @staticmethod
    def _extract_draft_data(blog: Blog) -> Dict[str, Any]:
        """Safely extract structured draft dictionary from blog."""
        content_json = blog.content_json
        if isinstance(content_json, dict):
            return dict(content_json)
        if isinstance(content_json, str):
            try:
                parsed = json.loads(content_json)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    @classmethod
    def validate_format(
        cls,
        blog: Blog,
        active_format: Optional[BlogFormat] = None,
    ) -> FormatValidationReport:
        """
        Evaluate structural and formatting integrity deterministically.
        
        Checks:
        1. Mandatory baseline components (Title, Intro, Headings, Main Content, Conclusion)
        2. H1 Title validity and absence of H1 inside body sections
        3. Introduction completeness and word count (>= 15 words)
        4. Conclusion completeness and word count (>= 10 words)
        5. Section completeness (headings non-empty, content >= 15 words)
        6. Heading hierarchy (H1 -> H2 -> H3, no orphan H3 before H2, valid levels)
        7. Duplicate headings (non-blocking warning)
        8. Company-specific format requirements (blocking error if required sections absent)
        """
        findings: List[ValidationFinding] = []
        raw_draft = cls._extract_draft_data(blog)

        # ── 1. H1 Title Validation ──
        h1 = (raw_draft.get("h1_title") or blog.title or "").strip()
        h1_title_valid = True
        if not h1:
            h1_title_valid = False
            findings.append(
                ValidationFinding(
                    rule="title_required",
                    message="H1 title is missing or empty.",
                    field="h1_title",
                    severity="error",
                )
            )
        elif len(h1) < 5:
            h1_title_valid = False
            findings.append(
                ValidationFinding(
                    rule="title_meaningful",
                    message=f"H1 title is too short ({len(h1)} characters; minimum 5 required).",
                    field="h1_title",
                    severity="error",
                    details={"actual_length": len(h1), "min_length": 5},
                )
            )

        # ── 2. Introduction Validation ──
        intro = (raw_draft.get("introduction") or "").strip()
        intro_words = re.findall(r"\b\w+\b", intro, re.UNICODE)
        introduction_valid = True
        if not intro:
            introduction_valid = False
            findings.append(
                ValidationFinding(
                    rule="introduction_required",
                    message="Introduction is missing or empty.",
                    field="introduction",
                    severity="error",
                )
            )
        elif len(intro_words) < 15:
            introduction_valid = False
            findings.append(
                ValidationFinding(
                    rule="introduction_length",
                    message=f"Introduction has insufficient content ({len(intro_words)} words; minimum 15 required).",
                    field="introduction",
                    severity="error",
                    details={"actual_words": len(intro_words), "min_words": 15},
                )
            )

        # ── 3. Conclusion Validation ──
        conclusion = (raw_draft.get("conclusion") or "").strip()
        conclusion_words = re.findall(r"\b\w+\b", conclusion, re.UNICODE)
        conclusion_valid = True
        if not conclusion:
            conclusion_valid = False
            findings.append(
                ValidationFinding(
                    rule="conclusion_required",
                    message="Conclusion is missing or empty.",
                    field="conclusion",
                    severity="error",
                )
            )
        elif len(conclusion_words) < 10:
            conclusion_valid = False
            findings.append(
                ValidationFinding(
                    rule="conclusion_length",
                    message=f"Conclusion has insufficient content ({len(conclusion_words)} words; minimum 10 required).",
                    field="conclusion",
                    severity="error",
                    details={"actual_words": len(conclusion_words), "min_words": 10},
                )
            )

        # ── 4. Sections & Heading Hierarchy Validation ──
        raw_sections = raw_draft.get("sections")
        sections_valid = True
        heading_hierarchy_valid = True
        duplicate_headings: List[str] = []
        seen_normalized_headings: Set[str] = set()

        if not raw_sections or not isinstance(raw_sections, list) or len(raw_sections) == 0:
            sections_valid = False
            findings.append(
                ValidationFinding(
                    rule="sections_required",
                    message="Blog draft has no body sections.",
                    field="sections",
                    severity="error",
                )
            )
        else:
            has_seen_h2 = False
            for idx, sec in enumerate(raw_sections, 1):
                sec_dict = sec if isinstance(sec, dict) else {}
                sec_heading = (sec_dict.get("heading") or "").strip()
                sec_level = sec_dict.get("level", 2)
                sec_content = (sec_dict.get("content") or "").strip()

                # Heading non-empty
                if not sec_heading:
                    sections_valid = False
                    findings.append(
                        ValidationFinding(
                            rule="section_heading_required",
                            message=f"Section {idx} has an empty heading.",
                            field=f"sections[{idx}].heading",
                            severity="error",
                        )
                    )
                else:
                    # Duplicate heading check (non-blocking warning)
                    norm_heading = re.sub(r"\s+", " ", sec_heading.lower())
                    if norm_heading in seen_normalized_headings:
                        if sec_heading not in duplicate_headings:
                            duplicate_headings.append(sec_heading)
                        findings.append(
                            ValidationFinding(
                                rule="duplicate_heading",
                                message=f"Duplicate heading detected: '{sec_heading}'.",
                                field=f"sections[{idx}].heading",
                                severity="warning",
                                details={"heading": sec_heading},
                            )
                        )
                    else:
                        seen_normalized_headings.add(norm_heading)

                # Section content length
                sec_words = re.findall(r"\b\w+\b", sec_content, re.UNICODE)
                if len(sec_words) < 15:
                    sections_valid = False
                    findings.append(
                        ValidationFinding(
                            rule="section_content_length",
                            message=f"Section {idx} ('{sec_heading}') has insufficient content ({len(sec_words)} words; minimum 15 required).",
                            field=f"sections[{idx}].content",
                            severity="error",
                            details={"actual_words": len(sec_words), "min_words": 15},
                        )
                    )

                # Heading Hierarchy check
                if sec_level == 1:
                    heading_hierarchy_valid = False
                    findings.append(
                        ValidationFinding(
                            rule="unexpected_h1_in_body",
                            message=f"Section {idx} ('{sec_heading}') uses H1 level in body; body sections must be H2 or H3.",
                            field=f"sections[{idx}].level",
                            severity="error",
                        )
                    )
                elif sec_level not in (2, 3):
                    heading_hierarchy_valid = False
                    findings.append(
                        ValidationFinding(
                            rule="invalid_heading_level",
                            message=f"Section {idx} ('{sec_heading}') has invalid heading level {sec_level}; must be H2 or H3.",
                            field=f"sections[{idx}].level",
                            severity="error",
                            details={"actual_level": sec_level},
                        )
                    )
                elif sec_level == 2:
                    has_seen_h2 = True
                elif sec_level == 3 and not has_seen_h2:
                    heading_hierarchy_valid = False
                    findings.append(
                        ValidationFinding(
                            rule="orphan_h3",
                            message=f"Section {idx} ('{sec_heading}') is an orphan H3 without preceding H2 parent.",
                            field=f"sections[{idx}].level",
                            severity="error",
                        )
                    )

        # Baseline sections composite validity
        baseline_sections_valid = (
            h1_title_valid
            and introduction_valid
            and conclusion_valid
            and sections_valid
            and heading_hierarchy_valid
        )

        # ── 5. Company-Specific Format Validation ──
        company_format_checked = False
        company_format_version = None
        company_sections_valid = True
        missing_company_sections: List[str] = []

        if active_format is not None:
            company_format_checked = True
            company_format_version = active_format.version

            # Parse format definition
            f_def = active_format.format_definition
            if isinstance(f_def, str):
                try:
                    f_def = json.loads(f_def)
                except Exception:
                    f_def = {}
            elif not isinstance(f_def, dict):
                f_def = {}

            required_sections = f_def.get("required_sections") or []
            # Extract section headings from draft for comparison
            actual_headings_lower = [
                h.lower() for h in seen_normalized_headings
            ]

            baseline_lookup = {s.lower() for s in MANDATORY_BASELINE_SECTIONS}

            for req in required_sections:
                req_norm = req.strip()
                req_lower = req_norm.lower()

                # Check if it's a baseline section
                if req_lower in baseline_lookup:
                    if req_lower == "title" and not h1_title_valid:
                        missing_company_sections.append(req_norm)
                    elif req_lower == "introduction" and not introduction_valid:
                        missing_company_sections.append(req_norm)
                    elif req_lower == "conclusion" and not conclusion_valid:
                        missing_company_sections.append(req_norm)
                    elif req_lower in ("headings", "main content") and not sections_valid:
                        missing_company_sections.append(req_norm)
                else:
                    # Custom required section: must match at least one section heading
                    matched = any(
                        req_lower == h or req_lower in h
                        for h in actual_headings_lower
                    )
                    if not matched:
                        missing_company_sections.append(req_norm)
                        findings.append(
                            ValidationFinding(
                                rule="missing_company_required_section",
                                message=f"Company required section '{req_norm}' is missing from blog draft.",
                                field="sections",
                                severity="error",
                                details={"required_section": req_norm},
                            )
                        )

            if missing_company_sections:
                company_sections_valid = False

        return FormatValidationReport(
            baseline_sections_valid=baseline_sections_valid,
            h1_title_valid=h1_title_valid,
            introduction_valid=introduction_valid,
            conclusion_valid=conclusion_valid,
            sections_valid=sections_valid,
            heading_hierarchy_valid=heading_hierarchy_valid,
            duplicate_headings=duplicate_headings,
            company_format_checked=company_format_checked,
            company_format_version=company_format_version,
            company_sections_valid=company_sections_valid,
            missing_company_sections=missing_company_sections,
            findings=findings,
        )

    @classmethod
    def validate_seo(cls, blog: Blog) -> SeoValidationReport:
        """
        Evaluate technical SEO metrics deterministically.
        
        Checks:
        1. Primary keyword exists and non-empty
        2. SEO Page Title (non-empty, 55-60 char target, primary keyword inclusion)
        3. Meta Description (non-empty, 140-160 char target, actionable CTA presence)
        4. Primary keyword in Introduction
        5. Primary keyword in at least one H2 heading (strict H2 level check)
        6. Slug validation (non-empty, lowercase URL-safe alphanumeric with hyphen separators)
        7. Keyword stuffing warning heuristic (> 3.5% density triggers warning, NOT error)
        """
        findings: List[ValidationFinding] = []
        raw_draft = cls._extract_draft_data(blog)

        # ── 1. Primary Keyword ──
        kw = (
            blog.primary_keyword
            if blog.primary_keyword is not None
            else (raw_draft.get("primary_keyword") or "")
        ).strip()
        kw_norm = re.sub(r"\s+", " ", kw.lower()) if kw else ""
        if not kw:
            findings.append(
                ValidationFinding(
                    rule="primary_keyword_required",
                    message="Primary keyword is missing or empty.",
                    field="primary_keyword",
                    severity="error",
                )
            )

        # ── 2. SEO Page Title ──
        seo_title = (
            blog.seo_title
            if blog.seo_title is not None
            else (raw_draft.get("seo_title") or "")
        ).strip()
        seo_title_length = len(seo_title)
        seo_title_valid = True
        keyword_in_seo_title = False

        if not seo_title:
            seo_title_valid = False
            findings.append(
                ValidationFinding(
                    rule="seo_title_required",
                    message="SEO page title is missing or empty.",
                    field="seo_title",
                    severity="error",
                )
            )
        else:
            # Length target: 55-60 characters
            if seo_title_length < 55 or seo_title_length > 60:
                findings.append(
                    ValidationFinding(
                        rule="seo_title_length",
                        message=(
                            f"SEO page title length is {seo_title_length} characters "
                            f"(target range: 55–60 characters)."
                        ),
                        field="seo_title",
                        severity="warning",
                        details={"actual_length": seo_title_length, "target_range": [55, 60]},
                    )
                )

            # Keyword presence in SEO title
            if kw_norm:
                st_norm = re.sub(r"\s+", " ", seo_title.lower())
                keyword_in_seo_title = kw_norm in st_norm
                if not keyword_in_seo_title:
                    seo_title_valid = False
                    findings.append(
                        ValidationFinding(
                            rule="keyword_in_seo_title",
                            message=f"Primary keyword '{kw}' is missing from SEO page title.",
                            field="seo_title",
                            severity="error",
                            details={"primary_keyword": kw},
                        )
                    )

        # ── 3. Meta Description ──
        meta_desc = (
            blog.meta_description
            if blog.meta_description is not None
            else (raw_draft.get("meta_description") or "")
        ).strip()
        meta_desc_length = len(meta_desc)
        meta_description_valid = True


        if not meta_desc:
            meta_description_valid = False
            findings.append(
                ValidationFinding(
                    rule="meta_description_required",
                    message="Meta description is missing or empty.",
                    field="meta_description",
                    severity="error",
                )
            )
        else:
            # Length target: 140-160 characters
            if meta_desc_length < 140 or meta_desc_length > 160:
                findings.append(
                    ValidationFinding(
                        rule="meta_description_length",
                        message=(
                            f"Meta description length is {meta_desc_length} characters "
                            f"(target range: 140–160 characters)."
                        ),
                        field="meta_description",
                        severity="warning",
                        details={"actual_length": meta_desc_length, "target_range": [140, 160]},
                    )
                )

            # Brand CTA actionability heuristic (non-blocking warning)
            md_lower = meta_desc.lower()
            has_cta = any(verb in md_lower for verb in CTA_ACTION_VERBS)
            if not has_cta:
                findings.append(
                    ValidationFinding(
                        rule="meta_description_cta",
                        message="Meta description does not contain an explicit brand call-to-action (e.g., 'Discover...', 'Learn how...').",
                        field="meta_description",
                        severity="warning",
                    )
                )

        # ── 4. Keyword in Introduction ──
        intro = (raw_draft.get("introduction") or "").strip()
        intro_norm = re.sub(r"\s+", " ", intro.lower())
        keyword_in_introduction = False

        if kw_norm:
            keyword_in_introduction = kw_norm in intro_norm
            if not keyword_in_introduction:
                findings.append(
                    ValidationFinding(
                        rule="keyword_in_introduction",
                        message=f"Primary keyword '{kw}' is missing from introduction.",
                        field="introduction",
                        severity="error",
                        details={"primary_keyword": kw},
                    )
                )

        # ── 5. Keyword in H2 ──
        raw_sections = raw_draft.get("sections") or []
        keyword_in_h2 = False
        h2_headings: List[str] = []

        if isinstance(raw_sections, list):
            for sec in raw_sections:
                sec_dict = sec if isinstance(sec, dict) else {}
                level = sec_dict.get("level", 2)
                heading = (sec_dict.get("heading") or "").strip()
                if level == 2 and heading:
                    h2_headings.append(heading)

        if kw_norm:
            keyword_in_h2 = any(
                kw_norm in re.sub(r"\s+", " ", h2.lower())
                for h2 in h2_headings
            )
            if not keyword_in_h2:
                findings.append(
                    ValidationFinding(
                        rule="keyword_in_h2",
                        message=f"Primary keyword '{kw}' must appear in at least one H2 heading.",
                        field="sections",
                        severity="error",
                        details={"primary_keyword": kw, "evaluated_h2_count": len(h2_headings)},
                    )
                )

        # ── 6. Slug Validation ──
        slug = (blog.slug or "").strip()
        slug_issues: List[str] = []
        slug_valid = True

        if not slug:
            slug_valid = False
            slug_issues.append("Slug is missing or empty.")
            findings.append(
                ValidationFinding(
                    rule="slug_required",
                    message="Blog slug is missing or empty.",
                    field="slug",
                    severity="error",
                )
            )
        else:
            if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug):
                slug_valid = False
                msg = f"Blog slug '{slug}' is invalid; must be lowercase alphanumeric with hyphen separators only."
                slug_issues.append(msg)
                findings.append(
                    ValidationFinding(
                        rule="slug_format",
                        message=msg,
                        field="slug",
                        severity="error",
                        details={"slug": slug},
                    )
                )
            if len(slug) > 255:
                slug_valid = False
                msg = f"Blog slug exceeds maximum length of 255 characters ({len(slug)} chars)."
                slug_issues.append(msg)
                findings.append(
                    ValidationFinding(
                        rule="slug_length",
                        message=msg,
                        field="slug",
                        severity="error",
                        details={"length": len(slug), "max_length": 255},
                    )
                )

        # ── 7. Keyword Stuffing Warning Heuristic (Non-blocking) ──
        # Computes keyword density across full rendered draft text
        h1 = (raw_draft.get("h1_title") or blog.title or "").strip()
        conclusion = (raw_draft.get("conclusion") or "").strip()
        full_text_parts = [
            h1,
            intro,
            conclusion,
        ]

        if isinstance(raw_sections, list):
            for sec in raw_sections:
                sec_dict = sec if isinstance(sec, dict) else {}
                full_text_parts.append(sec_dict.get("heading") or "")
                full_text_parts.append(sec_dict.get("content") or "")

        full_text = " ".join(full_text_parts)
        words = re.findall(r"\b\w+\b", full_text.lower(), re.UNICODE)
        total_words = len(words)

        keyword_stuffing_warning = False
        keyword_density: Optional[float] = None

        if kw_norm and total_words > 0:
            kw_words = re.findall(r"\b\w+\b", kw_norm, re.UNICODE)
            kw_len = len(kw_words)
            if kw_len > 0:
                pattern = re.compile(r"\b" + re.escape(kw_norm) + r"\b", re.IGNORECASE)
                occurrences = len(pattern.findall(full_text))
                density = (occurrences * kw_len / total_words) * 100.0
                keyword_density = round(density, 2)
                # Non-blocking warning heuristic threshold: > 3.5%
                if density > 3.5:
                    keyword_stuffing_warning = True
                    findings.append(
                        ValidationFinding(
                            rule="keyword_stuffing_heuristic",
                            message=(
                                f"High keyword density detected ({keyword_density}%). "
                                "Recommended keyword density is under 3% to avoid search engine over-optimization penalties."
                            ),
                            field="content",
                            severity="warning",
                            details={"keyword_density": keyword_density, "threshold": 3.5},
                        )
                    )

        return SeoValidationReport(
            seo_title_valid=seo_title_valid,
            seo_title_length=seo_title_length,
            meta_description_valid=meta_description_valid,
            meta_description_length=meta_desc_length,
            primary_keyword=kw or None,
            keyword_in_seo_title=keyword_in_seo_title,
            keyword_in_introduction=keyword_in_introduction,
            keyword_in_h2=keyword_in_h2,
            slug_valid=slug_valid,
            slug_issues=slug_issues,
            keyword_stuffing_warning=keyword_stuffing_warning,
            keyword_density=keyword_density,
            findings=findings,
        )

    @classmethod
    def synthesize_validation_result(
        cls,
        blog: Blog,
        format_report: FormatValidationReport,
        seo_report: SeoValidationReport,
    ) -> BlogValidationResponse:
        """
        Combine format and SEO findings into a unified validation result.
        
        Blocking errors cause passed=False.
        Warnings do not block passing.
        Generates actionable recommendations.
        """
        all_findings = format_report.findings + seo_report.findings
        errors = [f for f in all_findings if f.severity == "error"]
        warnings = [f for f in all_findings if f.severity == "warning"]

        recommendations: List[str] = []
        for w in warnings:
            if w.rule == "seo_title_length":
                recommendations.append("Adjust SEO page title length to fall within the target 55–60 character range.")
            elif w.rule == "meta_description_length":
                recommendations.append("Refine meta description length to fall within the target 140–160 character range.")
            elif w.rule == "meta_description_cta":
                recommendations.append("Incorporate a clear, brand-aligned call to action into the meta description.")
            elif w.rule == "duplicate_heading":
                recommendations.append(f"Diversify repeated section heading '{w.details.get('heading', '') if w.details else ''}'.")
            elif w.rule == "keyword_stuffing_heuristic":
                recommendations.append("Reduce repetitive keyword usage in body sections to maintain natural editorial flow.")

        passed = len(errors) == 0

        return BlogValidationResponse(
            blog_id=blog.id,
            company_id=blog.company_id,
            passed=passed,
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            seo_report=seo_report,
            format_report=format_report,
            validated_at=datetime.utcnow(),
        )

    def validate_blog(
        self,
        blog: Blog,
        active_format: Optional[BlogFormat] = None,
        persist: bool = True,
    ) -> BlogValidationResponse:
        """
        Execute full deterministic validation on a blog draft and optionally persist
        the result in Blog.generation_metadata["validation"].
        """
        format_report = self.validate_format(blog=blog, active_format=active_format)
        seo_report = self.validate_seo(blog=blog)
        result = self.synthesize_validation_result(
            blog=blog,
            format_report=format_report,
            seo_report=seo_report,
        )

        if persist and self.db is not None:
            # Safely merge into generation_metadata while preserving Phase 6 metadata
            current_metadata = dict(blog.generation_metadata or {})
            current_metadata["validation"] = json.loads(result.model_dump_json())
            blog.generation_metadata = current_metadata
            blog.updated_at = datetime.utcnow()
            self.db.add(blog)
            self.db.commit()
            self.db.refresh(blog)

        return result
