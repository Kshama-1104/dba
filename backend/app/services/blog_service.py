"""
Blog Service — Phase 6

Orchestrates the intelligent blog draft generation pipeline:
1. Validates authenticated tenant and topic candidate status (must be in SELECTED state).
2. Enforces concurrency protection (< 300s lock) and idempotency via PostgreSQL unique constraint.
3. Assembles multi-layer context (Company AI Context, Resolved Format, Topic, RAG, Categorized Memory, History, Editor Direction).
4. Resolves the 3-tier format hierarchy (System Baseline -> Company Global Format -> Editor Direction).
5. Generates structured blog plan via active provider.
6. Generates structured draft via active provider (Deterministic or ExternalLLMProvider).
7. Validates draft via Generation Quality & Grounding Evaluation gate.
8. Executes bounded targeted regeneration (up to 2 retries) if quality checks fail.
9. Renders clean Markdown representation and generates URL slug.
10. Persists the Blog record as DRAFT and transitions TopicCandidate to USED atomically.
11. Handles failures gracefully: marks Blog as GENERATION_FAILED, topic remains SELECTED for retry.
"""

from datetime import datetime, timedelta
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.blog import Blog, BlogStatus
from backend.app.models.company import Company
from backend.app.models.company_ai_profile import CompanyAIProfile
from backend.app.models.company_memory import MemoryType
from backend.app.models.topic_candidate import TopicCandidate, TopicStatus
from backend.app.schemas.blog import BlogPlan, StructuredBlogDraft
from backend.app.schemas.blog_format import MANDATORY_BASELINE_SECTIONS
from backend.app.services.blog_format_service import get_active_blog_format
from backend.app.services.blog_generation_provider import (
    BlogGenerationContext,
    ResolvedBlogFormat,
    get_blog_generation_provider,
    render_blog_to_markdown,
)
from backend.app.services.blog_quality_service import evaluate_blog_draft
from backend.app.services.memory_service import retrieve_relevant_memories
from backend.app.services.retrieval_service import retrieve_relevant_chunks

logger = logging.getLogger(__name__)


class ConcurrencyError(Exception):
    """Raised when generation is already in progress for a topic candidate."""
    pass


class BlogGenerationError(Exception):
    """Raised when the generation provider, quality gate, or context synthesis fails."""
    pass


class BlogService:
    """Service encapsulating Blog lifecycle operations and draft generation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _assemble_context(
        self,
        company_id: int,
        topic: TopicCandidate,
        editor_instruction: Optional[str] = None,
    ) -> BlogGenerationContext:
        """Assemble the complete multi-layer context required for blog draft generation."""
        ctx = BlogGenerationContext(
            company_id=company_id,
            topic_id=topic.id,
            topic_title=topic.title,
            topic_angle=topic.angle,
            topic_rationale=topic.rationale,
            topic_target_audience=topic.target_audience,
            primary_keyword=topic.primary_keyword,
            source_context=topic.source_context,
            editor_instruction=editor_instruction,
        )

        # ── Layer 1: Company & AI Brand Profile ──
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if company:
            ctx.company_name = company.name or ""
            ctx.company_industry = company.industry or ""

        profile = (
            self.db.query(CompanyAIProfile)
            .filter(CompanyAIProfile.company_id == company_id)
            .first()
        )
        if profile:
            ctx.brand_voice = profile.brand_voice or "Professional and authoritative"
            ctx.target_audience = profile.target_audience or ctx.topic_target_audience or "General audience"
            ctx.products_services = profile.products_services or ""
            ctx.marketing_goals = profile.marketing_goals or ""
            ctx.company_guidelines = profile.company_guidelines
            ctx.preferred_writing_style = profile.preferred_writing_style
            ctx.upcoming_projects = profile.upcoming_projects
            ctx.achievements = profile.achievements
            ctx.partner_companies = profile.partner_companies

        # ── Layer 2: 3-Tier Format Resolution (Baseline -> Company -> Editor) ──
        active_format = get_active_blog_format(self.db, company_id)
        resolved_sections = list(MANDATORY_BASELINE_SECTIONS)
        title_str = ctx.title_structure
        intro_str = ctx.introduction_structure
        head_str = ctx.heading_structure
        main_str = ctx.main_content_structure
        conc_str = ctx.conclusion_structure
        cta_val = ctx.call_to_action
        style_val = ctx.preferred_writing_style
        custom_rules_list: List[str] = []

        if active_format and active_format.format_definition:
            ctx.format_version = active_format.version
            try:
                f_def = json.loads(active_format.format_definition)
                resolved_sections = f_def.get("required_sections", resolved_sections)
                title_str = f_def.get("title_structure", title_str)
                intro_str = f_def.get("introduction_structure", intro_str)
                head_str = f_def.get("heading_structure", head_str)
                main_str = f_def.get("main_content_structure", main_str)
                conc_str = f_def.get("conclusion_structure", conc_str)
                cta_val = f_def.get("call_to_action") or cta_val
                style_val = f_def.get("preferred_writing_style") or style_val
                custom_rules_list = f_def.get("custom_rules", [])
            except Exception as e:
                logger.warning("Failed to parse active format definition for company %s: %s", company_id, e)

        resolved_format = ResolvedBlogFormat(
            format_version=ctx.format_version,
            required_sections=resolved_sections,
            title_structure=title_str,
            introduction_structure=intro_str,
            heading_structure=head_str,
            main_content_structure=main_str,
            conclusion_structure=conc_str,
            call_to_action=cta_val,
            preferred_writing_style=style_val,
            custom_rules=custom_rules_list,
            editor_instruction=editor_instruction,
        )

        ctx.resolved_format = resolved_format
        ctx.required_sections = resolved_sections
        ctx.title_structure = title_str
        ctx.introduction_structure = intro_str
        ctx.heading_structure = head_str
        ctx.main_content_structure = main_str
        ctx.conclusion_structure = conc_str
        ctx.call_to_action = cta_val
        ctx.custom_rules = custom_rules_list

        # ── Layer 4: Knowledge / RAG (Tenant-Scoped, READY only) ──
        query_parts = [topic.title]
        if topic.primary_keyword:
            query_parts.append(topic.primary_keyword)
        if topic.angle:
            query_parts.append(topic.angle)
        rag_query = " ".join(query_parts).strip()

        try:
            chunks = retrieve_relevant_chunks(
                db=self.db,
                company_id=company_id,
                query=rag_query,
                top_k=5,
            )
            ctx.knowledge_snippets = [
                {
                    "document_title": c.document_title,
                    "content": c.content,
                    "chunk_index": c.chunk_index,
                    "similarity_score": c.similarity_score,
                }
                for c in chunks
                if c.content
            ]
        except Exception as e:
            logger.warning("RAG chunk retrieval failed for company %s: %s", company_id, e)
            ctx.knowledge_snippets = []

        # ── Layer 5: Long-Term Memory (Tenant-Scoped, ACTIVE, Categorized) ──
        mem_parts = [topic.title]
        if topic.primary_keyword:
            mem_parts.append(topic.primary_keyword)
        mem_query = " ".join(mem_parts).strip()

        try:
            memories = retrieve_relevant_memories(
                db=self.db,
                company_id=company_id,
                query=mem_query,
                top_k=5,
                include_candidates=False,
            )
            for m in memories:
                if not m.content:
                    continue
                item = {
                    "memory_type": m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type),
                    "content": m.content,
                    "confidence": m.confidence.value if hasattr(m.confidence, "value") else str(m.confidence),
                    "importance": m.importance,
                }
                ctx.memory_snippets.append(item)
                m_type = str(item["memory_type"]).lower()
                if m_type == "semantic":
                    ctx.semantic_memories.append(item)
                elif m_type == "episodic":
                    ctx.episodic_memories.append(item)
                elif m_type == "procedural":
                    ctx.procedural_memories.append(item)
        except Exception as e:
            logger.warning("Memory retrieval failed for company %s: %s", company_id, e)

        # ── Layer 6: Recent Topic & Blog History ──
        try:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_topics_query = (
                self.db.query(TopicCandidate)
                .filter(
                    TopicCandidate.company_id == company_id,
                    TopicCandidate.id != topic.id,
                    TopicCandidate.created_at >= thirty_days_ago,
                    TopicCandidate.status.in_([TopicStatus.SELECTED, TopicStatus.USED]),
                )
                .order_by(TopicCandidate.created_at.desc())
                .limit(5)
                .all()
            )
            ctx.recent_topics = [
                {"title": t.title, "angle": t.angle or ""}
                for t in recent_topics_query
            ]
        except Exception as e:
            logger.warning("Recent topic history query failed for company %s: %s", company_id, e)

        try:
            recent_blogs_query = (
                self.db.query(Blog)
                .filter(
                    Blog.company_id == company_id,
                    Blog.status == BlogStatus.DRAFT,
                )
                .order_by(Blog.created_at.desc())
                .limit(5)
                .all()
            )
            ctx.recent_blogs = [
                {"title": b.title, "primary_keyword": b.primary_keyword or ""}
                for b in recent_blogs_query
            ]
        except Exception as e:
            logger.warning("Recent blogs query failed for company %s: %s", company_id, e)

        # ── Layer 8: Connected External Sources & Social Insights (Additive Integration Layer) ──
        try:
            from backend.app.services.external_integration_service import retrieve_relevant_social_insights

            insights = retrieve_relevant_social_insights(
                db=self.db,
                company_id=company_id,
                query=rag_query,
                top_k=5,
            )
            ctx.external_social_insights = [
                {
                    "platform": i.platform,
                    "content": i.content,
                    "author": i.author or "",
                    "source_url": i.source_url or "",
                    "similarity_score": i.similarity_score,
                    "freshness_score": i.freshness_score,
                }
                for i in insights
                if i.content
            ]
        except Exception as e:
            logger.warning("External social insight retrieval failed for company %s: %s", company_id, e)
            ctx.external_social_insights = []

        return ctx

    def _generate_unique_slug(
        self,
        company_id: int,
        title: str,
        topic_id: int,
        current_blog_id: Optional[int] = None,
    ) -> str:
        """Generate a URL-safe, tenant-scoped unique slug with deterministic collision handling (-2, -3, etc.)."""
        raw_slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
        base_slug = raw_slug[:240] if raw_slug else f"blog-{topic_id}"

        query = self.db.query(Blog.slug).filter(
            Blog.company_id == company_id,
            Blog.slug.isnot(None),
        )
        if current_blog_id:
            query = query.filter(Blog.id != current_blog_id)

        existing_slugs = {s[0] for s in query.all()}

        if base_slug not in existing_slugs:
            return base_slug

        counter = 2
        while True:
            candidate_slug = f"{base_slug}-{counter}"
            if candidate_slug not in existing_slugs:
                return candidate_slug
            counter += 1

    def generate_blog(
        self,
        company_id: int,
        user_id: int,
        topic_candidate_id: int,
        editor_instruction: Optional[str] = None,
    ) -> Tuple[Blog, bool]:
        """Generate and persist a blog draft synchronously.
        
        Returns:
            Tuple[Blog, bool]: (blog_record, is_new)
            is_new is True if a new draft was created, False if an existing draft was returned.
            
        Raises:
            ValueError: If topic candidate is not found, not owned by tenant, or not in valid state.
            ConcurrencyError: If generation is currently in progress.
            BlogGenerationError: If provider or quality validation fails.
        """
        # 1. Fetch topic candidate with strict tenant isolation
        topic = (
            self.db.query(TopicCandidate)
            .filter(
                TopicCandidate.id == topic_candidate_id,
                TopicCandidate.company_id == company_id,
            )
            .first()
        )
        if not topic:
            raise ValueError("Topic candidate not found.")

        # 2. Idempotency Check: if topic is already USED, return existing blog if DRAFT
        if topic.status == TopicStatus.USED:
            existing_blog = (
                self.db.query(Blog)
                .filter(
                    Blog.topic_candidate_id == topic.id,
                    Blog.company_id == company_id,
                )
                .first()
            )
            if existing_blog and existing_blog.status == BlogStatus.DRAFT:
                return existing_blog, False
            raise ValueError("Cannot generate blog: topic candidate has already been used.")

        # 3. Topic must be in SELECTED state to start generation
        if topic.status != TopicStatus.SELECTED:
            raise ValueError(
                f"Cannot generate blog: topic must be in 'selected' state (current: '{topic.status.value}')."
            )

        # 4. Concurrency & Failure Recovery Reconciliation
        existing_blog = (
            self.db.query(Blog)
            .filter(
                Blog.topic_candidate_id == topic.id,
                Blog.company_id == company_id,
            )
            .first()
        )

        blog_record: Blog
        now = datetime.utcnow()

        if existing_blog:
            if existing_blog.status == BlogStatus.DRAFT:
                # Idempotent return (ensure topic is synced to USED)
                topic.status = TopicStatus.USED
                self.db.commit()
                return existing_blog, False

            elif existing_blog.status == BlogStatus.GENERATING:
                age_seconds = (now - (existing_blog.updated_at or existing_blog.created_at)).total_seconds()
                if age_seconds < 300:  # 5 minutes active window
                    raise ConcurrencyError("Blog generation is currently in progress for this topic candidate.")
                # Stale crash recovery (> 5 min): reset GENERATING and proceed
                blog_record = existing_blog
                blog_record.status = BlogStatus.GENERATING
                blog_record.updated_at = now
                self.db.commit()
                self.db.refresh(blog_record)

            elif existing_blog.status == BlogStatus.GENERATION_FAILED:
                # Retry path: reuse existing blog record, reset to GENERATING
                blog_record = existing_blog
                blog_record.status = BlogStatus.GENERATING
                blog_record.generation_metadata = None
                blog_record.updated_at = now
                self.db.commit()
                self.db.refresh(blog_record)
            else:
                blog_record = existing_blog
        else:
            # Insert initial GENERATING record to acquire topic_candidate_id lock
            new_blog = Blog(
                company_id=company_id,
                topic_candidate_id=topic.id,
                created_by_user_id=user_id,
                title=topic.title,
                status=BlogStatus.GENERATING,
                content_json={},
                content_markdown="",
                created_at=now,
                updated_at=now,
            )
            try:
                self.db.add(new_blog)
                self.db.commit()
                self.db.refresh(new_blog)
                blog_record = new_blog
            except IntegrityError as exc:
                self.db.rollback()
                # Concurrent request inserted first
                recheck = (
                    self.db.query(Blog)
                    .filter(
                        Blog.topic_candidate_id == topic.id,
                        Blog.company_id == company_id,
                    )
                    .first()
                )
                if recheck:
                    if recheck.status == BlogStatus.DRAFT:
                        return recheck, False
                    if recheck.status == BlogStatus.GENERATING:
                        age = (datetime.utcnow() - (recheck.updated_at or recheck.created_at)).total_seconds()
                        if age < 300:
                            raise ConcurrencyError("Blog generation is currently in progress for this topic candidate.")
                raise ConcurrencyError("Blog generation is currently in progress for this topic candidate.") from exc

        # 5. Assemble Context
        context = self._assemble_context(
            company_id=company_id,
            topic=topic,
            editor_instruction=editor_instruction,
        )

        # 6. Invoke Provider & Orchestrate Generation Pipeline
        provider = get_blog_generation_provider()
        try:
            # Step A: Planning
            plan: Optional[BlogPlan] = None
            try:
                plan = provider.plan(context)
            except Exception as plan_err:
                logger.warning("Blog planning stage warning: %s", plan_err)

            # Step B: Generation & Quality Gate with Bounded Regeneration (max 2 retries)
            max_retries = 2
            attempt = 0
            draft: Optional[StructuredBlogDraft] = None
            quality_result = None

            import inspect
            gen_params = inspect.signature(provider.generate).parameters
            supports_plan = "plan" in gen_params
            supports_feedback = "targeted_feedback" in gen_params

            while attempt <= max_retries:
                attempt += 1
                gen_kwargs: Dict[str, Any] = {}
                if supports_plan:
                    gen_kwargs["plan"] = plan
                if supports_feedback:
                    gen_kwargs["targeted_feedback"] = (
                        quality_result.targeted_instructions
                        if (quality_result and not quality_result.passed)
                        else None
                    )

                draft = provider.generate(context, **gen_kwargs)
                if not isinstance(draft, StructuredBlogDraft):
                    draft = StructuredBlogDraft.model_validate(draft)

                quality_result = evaluate_blog_draft(draft, context)
                if quality_result.passed:
                    break

            if not quality_result or not quality_result.passed:
                issues_summary = "; ".join(quality_result.issues) if quality_result else "Unknown quality failure"
                raise BlogGenerationError(
                    f"Blog generation quality evaluation failed after {attempt} attempts: {issues_summary}"
                )

            # Step C: Render Markdown
            rendered_markdown = render_blog_to_markdown(draft)

            # Step D: Slug Generation with Deterministic Collision Handling
            slug = self._generate_unique_slug(
                company_id=company_id,
                title=draft.h1_title,
                topic_id=topic.id,
                current_blog_id=blog_record.id,
            )

            # Step E: Update Blog record to DRAFT and Transition Topic to USED
            blog_record.title = draft.h1_title
            blog_record.slug = slug
            blog_record.primary_keyword = draft.primary_keyword
            blog_record.seo_title = draft.seo_title
            blog_record.meta_description = draft.meta_description
            blog_record.content_json = draft.model_dump()
            blog_record.content_markdown = rendered_markdown
            blog_record.status = BlogStatus.DRAFT
            blog_record.format_version = context.format_version
            blog_record.generation_metadata = {
                "provider": provider.provider_name,
                "is_llm_backed": provider.is_llm_backed,
                "attempts": attempt,
                "quality_passed": True,
                "retrieved_chunk_count": len(context.knowledge_snippets),
                "retrieved_memory_count": len(context.memory_snippets),
                "has_plan": plan is not None,
                "generated_at": datetime.utcnow().isoformat(),
            }
            blog_record.updated_at = datetime.utcnow()

            # Atomically mark topic as USED
            topic.status = TopicStatus.USED
            topic.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(blog_record)
            return blog_record, True

        except Exception as exc:
            self.db.rollback()
            # Record failure state safely without exposing secrets
            try:
                failed_blog = (
                    self.db.query(Blog)
                    .filter(Blog.id == blog_record.id)
                    .first()
                )
                if failed_blog:
                    failed_blog.status = BlogStatus.GENERATION_FAILED
                    failed_blog.generation_metadata = {
                        "provider": provider.provider_name,
                        "failed_at": datetime.utcnow().isoformat(),
                        "error_type": type(exc).__name__,
                    }
                    failed_blog.updated_at = datetime.utcnow()
                    self.db.commit()
            except Exception:
                self.db.rollback()

            # Ensure topic remains SELECTED for retry
            raise BlogGenerationError(f"Blog generation failed. Topic remains selected for retry: {exc}") from exc

    def get_blog(self, company_id: int, blog_id: int) -> Optional[Blog]:
        """Retrieve a specific blog draft by ID with strict tenant isolation."""
        return (
            self.db.query(Blog)
            .filter(
                Blog.id == blog_id,
                Blog.company_id == company_id,
            )
            .first()
        )

    def list_blogs(
        self,
        company_id: int,
        status: Optional[BlogStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Blog]:
        """List blogs for the authenticated company, optionally filtered by status."""
        query = self.db.query(Blog).filter(Blog.company_id == company_id)
        if status:
            query = query.filter(Blog.status == status)

        bounded_limit = max(1, min(100, limit))
        bounded_skip = max(0, skip)

        return (
            query.order_by(Blog.created_at.desc())
            .offset(bounded_skip)
            .limit(bounded_limit)
            .all()
        )
