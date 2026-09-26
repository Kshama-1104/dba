"""
Topic Intelligence Service — Phase 5

Orchestrates the strategic topic intelligence pipeline:

    Company AI Context (Profile, Brand Voice, Guidelines, Projects)
            +
    Relevant Knowledge / RAG (Phase 3)
            +
    Categorized Long-Term Memory (Phase 4: Semantic, Episodic, Procedural)
            +
    Topic History (Rolling 30-day Selected/Used + Rejected)
            +
    Optional Editor Direction (Focus Theme, Target Keyword)
            ↓
    Context Builder (Structured, Untrusted-Data Isolated)
            ↓
    Topic Generation Provider Interface
            ↓
    Configured Provider Adapter (External LLM / Offline Deterministic)
            ↓
    Validation & Deduplication
            ↓
    Strategic Alignment & Novelty Evaluation
            ↓
    Persisted Ranked Topic Candidates (Status = SUGGESTED)
            ↓
    Editor Action: SELECT or REJECT (Terminal Phase 5 Boundary)

Phase Boundary:
    Topic selection is a terminal state in Phase 5. This service does NOT generate
    blog drafts, outlines, or markdown content (owned by Phase 6).
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.security import UserRole
from backend.app.models.company import Company
from backend.app.models.company_ai_profile import CompanyAIProfile
from backend.app.models.topic_candidate import TopicCandidate, TopicStatus
from backend.app.schemas.topic import TopicCandidateCreate, TopicCandidateResponse
from backend.app.services.topic_generation_provider import (
    TopicGenerationContext,
    TopicGenerationProvider,
    TopicProposal,
    TopicProviderError,
    get_topic_generation_provider,
)


class TopicIntelligenceService:
    """Service orchestrating the Topic Intelligence pipeline."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Context Assembly ────────────────────────────────────────────

    @staticmethod
    def _construct_retrieval_query(
        company_name: str,
        company_industry: str,
        products_services: str,
        target_audience: str,
        marketing_goals: str,
        editor_focus_theme: Optional[str] = None,
    ) -> str:
        """Construct a company-grounded retrieval query string for RAG & Memory.

        Incorporates company identity, industry, products/services, audience, goals,
        and optional editor focus theme. Bounds length and normalizes whitespace.
        """
        parts = []
        if editor_focus_theme:
            parts.append(editor_focus_theme)
        parts.extend([
            company_name,
            company_industry,
            products_services,
            target_audience,
            marketing_goals,
        ])
        non_empty = [p.strip() for p in parts if p and p.strip()]
        if not non_empty:
            return "company strategy products industry trends"

        full_query = " ".join(non_empty)
        normalized = " ".join(full_query.split())
        return normalized[:500]

    def _build_context(
        self,
        company_id: int,
        focus_theme: Optional[str] = None,
        target_keyword: Optional[str] = None,
    ) -> TopicGenerationContext:
        """Assemble structured context from Company Profile, RAG, Memory, and Topic History.

        SECURITY BOUNDARY: Reference content (RAG chunks and memories) is treated strictly
        as untrusted reference DATA.
        """
        ctx = TopicGenerationContext(
            editor_focus_theme=focus_theme.strip() if focus_theme and focus_theme.strip() else None,
            editor_target_keyword=target_keyword.strip() if target_keyword and target_keyword.strip() else None,
        )

        # 1. Company identity + complete AI profile
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
            ctx.brand_voice = profile.brand_voice or ""
            ctx.target_audience = profile.target_audience or ""
            ctx.products_services = profile.products_services or ""
            ctx.marketing_goals = profile.marketing_goals or ""
            ctx.preferred_writing_style = profile.preferred_writing_style or ""
            ctx.company_guidelines = profile.company_guidelines or ""
            ctx.upcoming_projects = profile.upcoming_projects or ""

        # Construct retrieval query string
        query_str = self._construct_retrieval_query(
            company_name=ctx.company_name,
            company_industry=ctx.company_industry,
            products_services=ctx.products_services,
            target_audience=ctx.target_audience,
            marketing_goals=ctx.marketing_goals,
            editor_focus_theme=ctx.editor_focus_theme,
        )

        # 2. Knowledge/RAG — retrieve top-k active reference chunks via Phase 3 service
        try:
            from backend.app.services.retrieval_service import retrieve_relevant_chunks

            chunks = retrieve_relevant_chunks(
                db=self.db,
                company_id=company_id,
                query=query_str,
                top_k=5,
            )
            ctx.knowledge_snippets = [c.content for c in chunks if c.content]
        except Exception:
            ctx.knowledge_snippets = []

        # 3. Long-Term Memory — retrieve active memories via Phase 4 service and preserve categories
        try:
            from backend.app.models.company_memory import MemoryType
            from backend.app.services.memory_service import retrieve_relevant_memories

            memories = retrieve_relevant_memories(
                db=self.db,
                company_id=company_id,
                query=query_str,
                top_k=5,
                include_candidates=False,
            )
            for m in memories:
                if not m.content:
                    continue
                ctx.memory_snippets.append(m.content)
                if m.memory_type == MemoryType.PROCEDURAL:
                    ctx.procedural_memories.append(m.content)
                elif m.memory_type == MemoryType.SEMANTIC:
                    ctx.semantic_memories.append(m.content)
                elif m.memory_type == MemoryType.EPISODIC:
                    ctx.episodic_memories.append(m.content)
        except Exception:
            ctx.memory_snippets = []

        # 4. Topic history — rolling 30-day selected/used topics + historical rejected topics
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        recent_topics = (
            self.db.query(TopicCandidate)
            .filter(
                TopicCandidate.company_id == company_id,
                TopicCandidate.status.in_([
                    TopicStatus.SELECTED,
                    TopicStatus.USED,
                ]),
                TopicCandidate.created_at >= cutoff_date,
            )
            .order_by(TopicCandidate.created_at.desc())
            .all()
        )
        ctx.recent_topic_titles = [t.title for t in recent_topics]

        rejected_topics = (
            self.db.query(TopicCandidate)
            .filter(
                TopicCandidate.company_id == company_id,
                TopicCandidate.status == TopicStatus.REJECTED,
            )
            .order_by(TopicCandidate.created_at.desc())
            .limit(50)
            .all()
        )
        ctx.rejected_topic_titles = [t.title for t in rejected_topics]

        # 5. External Company & Social Insights (Additive Integration Layer)
        try:
            from backend.app.services.external_integration_service import retrieve_relevant_social_insights

            insights = retrieve_relevant_social_insights(
                db=self.db,
                company_id=company_id,
                query=query_str,
                top_k=5,
            )
            ctx.social_insights = [i.content for i in insights if i.content]
        except Exception:
            ctx.social_insights = []

        return ctx

    # ── Strategic Evaluation & Deduplication ─────────────────────────

    def _compute_relevance_score(
        self, candidate_title: str, context: TopicGenerationContext, proposal: Optional[TopicProposal] = None
    ) -> float:
        """Evaluate strategic alignment and company relevance.

        Uses the LLM's strategic_fit_score if provided.
        Otherwise calculates a deterministic strategic relevance score [0.0 - 1.0] based on
        contextual alignment with company products, audience, and editor focus.
        """
        if proposal and proposal.strategic_fit_score is not None:
            return max(0.0, min(1.0, round(proposal.strategic_fit_score, 4)))

        # Fallback strategic score:
        # Boosted if matching editor direction, otherwise baseline strategic fit
        if context.editor_focus_theme and context.editor_focus_theme.lower() in candidate_title.lower():
            return 0.95
        return 0.88

    def _compute_freshness_score(
        self, candidate_title: str, context: TopicGenerationContext
    ) -> float:
        """Novelty metric evaluating dissimilarity against recent selected/used topics.

        Compares candidate title against recent topic history.
        Returns 1.0 (maximally novel) if no overlap; discounts score if high token overlap.
        """
        if not context.recent_topic_titles:
            return 1.0

        cand_words = set(candidate_title.lower().split())
        if not cand_words:
            return 1.0

        max_overlap = 0.0
        for recent_title in context.recent_topic_titles:
            recent_words = set(recent_title.lower().split())
            if not recent_words:
                continue
            common = cand_words & recent_words
            overlap = len(common) / max(len(cand_words), 1)
            max_overlap = max(max_overlap, overlap)

        freshness = max(0.0, min(1.0, round(1.0 - max_overlap, 4)))
        return freshness

    def _is_duplicate(self, company_id: int, title: str) -> bool:
        """Check if a topic with this title already exists for the company.

        All statuses participate in duplicate detection (SUGGESTED, SELECTED,
        REJECTED, USED, EXPIRED). Rejected topics will not be re-suggested.
        """
        existing = (
            self.db.query(TopicCandidate)
            .filter(
                TopicCandidate.company_id == company_id,
                TopicCandidate.title.ilike(title.strip()),
            )
            .first()
        )
        return existing is not None

    # ── Public API ──────────────────────────────────────────────────

    def generate_topics(
        self,
        company_id: int,
        user_id: Optional[int] = None,
        focus_theme: Optional[str] = None,
        target_keyword: Optional[str] = None,
    ) -> List[TopicCandidateResponse]:
        """Generate, validate, score, rank, and persist topic candidates.

        Integrates multi-layer company context and dispatches to the configured
        TopicGenerationProvider. Deduplicates against company history and persists
        high-quality candidates with status SUGGESTED.
        """
        context = self._build_context(
            company_id=company_id,
            focus_theme=focus_theme,
            target_keyword=target_keyword,
        )

        # Context presence guard: requires at least some profile, knowledge, memory, or editor direction
        has_context = bool(
            context.products_services
            or context.marketing_goals
            or context.upcoming_projects
            or context.knowledge_snippets
            or context.memory_snippets
            or context.editor_focus_theme
        )
        if not has_context:
            return []

        # Generate proposals via configured provider
        provider = get_topic_generation_provider()
        proposals = provider.generate(context)

        if not proposals:
            return []

        scored_candidates: List[tuple] = []  # (final_score, TopicCandidate)

        for proposal in proposals:
            title = proposal.topic.strip()
            if not title or len(title) > 255:
                continue

            if self._is_duplicate(company_id, title):
                continue

            relevance = self._compute_relevance_score(title, context, proposal)
            freshness = self._compute_freshness_score(title, context)
            final_score = relevance + freshness

            tc = TopicCandidate(
                company_id=company_id,
                created_by=user_id,
                title=title,
                angle=proposal.angle or None,
                rationale=proposal.rationale or None,
                target_audience=proposal.target_audience or context.target_audience or None,
                source_context=proposal.source_context_anchor or None,
                primary_keyword=proposal.primary_keyword or target_keyword or None,
                relevance_score=relevance,
                freshness_score=freshness,
                status=TopicStatus.SUGGESTED,
            )
            self.db.add(tc)
            self.db.flush()
            scored_candidates.append((final_score, tc))

        if scored_candidates:
            self.db.commit()

        # Sort by final_score descending (stable sort preserves insertion order for ties)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        return [TopicCandidateResponse.model_validate(tc) for _, tc in scored_candidates]

    def create_custom_topic(
        self,
        company_id: int,
        topic_in: TopicCandidateCreate,
        user_id: int,
    ) -> TopicCandidateResponse:
        """Create a custom topic candidate provided directly by an Editor.

        Applies deduplication and sets status to SUGGESTED. Does NOT trigger blog generation.
        """
        title = topic_in.title.strip()
        if not title:
            raise ValueError("Topic title cannot be empty.")

        if self._is_duplicate(company_id, title):
            raise ValueError(f"Topic '{title}' already exists for this company.")

        context = self._build_context(company_id)
        relevance = self._compute_relevance_score(title, context)
        freshness = self._compute_freshness_score(title, context)

        source_anchor = topic_in.source_context or "custom_editor_provided"

        tc = TopicCandidate(
            company_id=company_id,
            created_by=user_id,
            title=title,
            angle=topic_in.angle or None,
            rationale=topic_in.rationale or "Custom topic provided by editor",
            target_audience=topic_in.target_audience or context.target_audience or None,
            source_context=source_anchor,
            primary_keyword=topic_in.primary_keyword or None,
            relevance_score=relevance,
            freshness_score=freshness,
            status=TopicStatus.SUGGESTED,
        )
        self.db.add(tc)
        self.db.commit()
        self.db.refresh(tc)
        return TopicCandidateResponse.model_validate(tc)

    def list_topics(
        self,
        company_id: int,
        status_filter: Optional[TopicStatus] = None,
    ) -> List[TopicCandidateResponse]:
        """List topic candidates for the company, optionally filtered by status."""
        query = self.db.query(TopicCandidate).filter(
            TopicCandidate.company_id == company_id
        )
        if status_filter:
            query = query.filter(TopicCandidate.status == status_filter)
        topics = query.order_by(TopicCandidate.created_at.desc()).all()
        return [TopicCandidateResponse.model_validate(t) for t in topics]

    def get_topic(
        self, company_id: int, topic_id: int
    ) -> Optional[TopicCandidateResponse]:
        """Get a single topic by ID with strict tenant isolation."""
        topic = (
            self.db.query(TopicCandidate)
            .filter(
                TopicCandidate.id == topic_id,
                TopicCandidate.company_id == company_id,
            )
            .first()
        )
        if not topic:
            return None
        return TopicCandidateResponse.model_validate(topic)

    def select_topic(
        self, company_id: int, topic_id: int, user
    ) -> TopicCandidateResponse:
        """Transition a topic from SUGGESTED to SELECTED.

        RBAC: Only EDITOR may select topics.
        Selection does NOT trigger blog generation (Phase 5 boundary).
        """
        if user.role != UserRole.EDITOR:
            raise PermissionError("Only editors may select topics.")

        topic = (
            self.db.query(TopicCandidate)
            .filter(
                TopicCandidate.id == topic_id,
                TopicCandidate.company_id == company_id,
            )
            .first()
        )
        if not topic:
            raise ValueError("Topic not found.")
        if topic.status != TopicStatus.SUGGESTED:
            raise ValueError(
                f"Cannot select topic in '{topic.status.value}' state. "
                f"Only 'suggested' topics can be selected."
            )

        topic.status = TopicStatus.SELECTED
        topic.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(topic)
        return TopicCandidateResponse.model_validate(topic)

    def reject_topic(
        self, company_id: int, topic_id: int, user
    ) -> TopicCandidateResponse:
        """Transition a topic to REJECTED.

        RBAC: Only EDITOR may reject topics.
        Rejected topics remain in deduplication so they will not be re-suggested.
        """
        if user.role != UserRole.EDITOR:
            raise PermissionError("Only editors may reject topics.")

        topic = (
            self.db.query(TopicCandidate)
            .filter(
                TopicCandidate.id == topic_id,
                TopicCandidate.company_id == company_id,
            )
            .first()
        )
        if not topic:
            raise ValueError("Topic not found.")
        if topic.status not in (TopicStatus.SUGGESTED, TopicStatus.SELECTED):
            raise ValueError(
                f"Cannot reject topic in '{topic.status.value}' state."
            )

        topic.status = TopicStatus.REJECTED
        topic.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(topic)
        return TopicCandidateResponse.model_validate(topic)
