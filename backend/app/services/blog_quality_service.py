"""
Generation Quality & Grounding Evaluation Service — Phase 6

Provides deterministic quality gates and grounding evaluation for generated blog drafts
prior to database finalization.

THIS IS NOT PHASE 7 SEO VALIDATION.
This service evaluates core draft completeness, heading hierarchy, keyword integration,
and context grounding to determine whether a draft passes or requires targeted regeneration.
"""

import logging
import re
from typing import List, Optional

from backend.app.schemas.blog import QualityEvaluationResult, StructuredBlogDraft
from backend.app.services.blog_generation_provider import BlogGenerationContext

logger = logging.getLogger(__name__)


def evaluate_blog_draft(
    draft: StructuredBlogDraft,
    context: BlogGenerationContext,
) -> QualityEvaluationResult:
    """Evaluate structural integrity, content completeness, and grounding.
    
    Returns:
        QualityEvaluationResult indicating whether draft passes and targeted instructions
        for regeneration if it fails.
    """
    issues: List[str] = []

    # 1. Title Verification
    h1 = (draft.h1_title or "").strip()
    if not h1 or len(h1) < 5:
        issues.append("H1 Title is empty or too short.")

    # 2. Introduction Verification
    intro = (draft.introduction or "").strip()
    intro_words = re.findall(r"\b\w+\b", intro)
    if len(intro_words) < 15:
        issues.append(f"Introduction is insufficient ({len(intro_words)} words; minimum 15 required).")

    # 3. Conclusion Verification
    conclusion = (draft.conclusion or "").strip()
    conclusion_words = re.findall(r"\b\w+\b", conclusion)
    if len(conclusion_words) < 10:
        issues.append(f"Conclusion is insufficient ({len(conclusion_words)} words; minimum 10 required).")

    # 4. Sections & Heading Hierarchy Verification
    if not draft.sections or len(draft.sections) < 2:
        issues.append(f"Draft contains insufficient sections ({len(draft.sections) if draft.sections else 0}; minimum 2 required).")

    has_h2 = False
    for idx, sec in enumerate(draft.sections or [], 1):
        sec_heading = (sec.heading or "").strip()
        if not sec_heading:
            issues.append(f"Section {idx} has an empty heading.")

        if sec.level == 2:
            has_h2 = True
        elif sec.level == 3 and not has_h2:
            issues.append(f"Section {idx} ('{sec_heading}') is an H3 without a preceding H2 parent.")

        sec_words = re.findall(r"\b\w+\b", (sec.content or ""))
        if len(sec_words) < 15:
            issues.append(f"Section {idx} ('{sec_heading}') has insufficient content ({len(sec_words)} words; minimum 15 required).")

    # 5. Keyword Placement Verification
    kw = (context.primary_keyword or "").strip().lower()
    if kw:
        # Check if keyword or its key terms appear in title, intro, or sections
        kw_pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
        found_in_title = bool(kw_pattern.search(draft.h1_title))
        found_in_intro = bool(kw_pattern.search(draft.introduction))
        found_in_sections = any(
            kw_pattern.search(s.heading) or kw_pattern.search(s.content)
            for s in draft.sections
        )

        if not (found_in_title or found_in_intro or found_in_sections):
            # Fallback check: check if any component word of a multi-word keyword is present
            kw_words = [w for w in re.findall(r"\b\w+\b", kw) if len(w) > 3]
            terms_found = any(
                re.search(r"\b" + re.escape(w) + r"\b", draft.h1_title + " " + draft.introduction, re.IGNORECASE)
                for w in kw_words
            )
            if not terms_found:
                issues.append(f"Primary keyword '{kw}' is completely missing from title, introduction, and body sections.")

    # 6. Synthesize Result
    if not issues:
        return QualityEvaluationResult(passed=True, issues=[], targeted_instructions=None)

    targeted_instructions = (
        "The generated blog draft did not meet all quality requirements. "
        "Please resolve the following specific issues in your revision:\n- "
        + "\n- ".join(issues)
    )

    return QualityEvaluationResult(
        passed=False,
        issues=issues,
        targeted_instructions=targeted_instructions,
    )
