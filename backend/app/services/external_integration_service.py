"""
EXTERNAL INTEGRATION SERVICE

Orchestrates connection management, credential encryption, synchronization,
deduplication, pgvector embeddings, and tenant-scoped relevance retrieval.

ARCHITECTURAL INVARIANTS:
1. Strict Multi-Tenancy: All queries filtered by company_id.
2. Max 5 Active Integrations per enterprise company.
3. Memory Quarantine: Synchronized content is stored in company_social_insights;
   NEVER automatically promoted into company_memories.
4. Deduplication: (company_id, platform, external_id) + SHA-256 content hashing.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from backend.app.core.credential_vault import (
    decrypt_credentials,
    encrypt_credentials,
    mask_credential_string,
)
from backend.app.models.external_integration import (
    CompanySocialInsight,
    ExternalIntegration,
)
from backend.app.schemas.external_integration import (
    InsightItemResponse,
    IntegrationConnectRequest,
    IntegrationPlatform,
    IntegrationResponse,
    IntegrationStatus,
    RetrievedInsightItem,
    SyncResultResponse,
    SyncStatus,
)
from backend.app.services.embedding_service import get_embedding_provider
from backend.app.services.external_integration_provider import (
    ExternalIntegrationProvider,
    IntegrationAuthError,
    IntegrationProviderError,
    get_integration_adapter,
)

MAX_ACTIVE_INTEGRATIONS_PER_COMPANY = 5


class MaxIntegrationsReachedError(Exception):
    """Raised when an enterprise company attempts to connect more than 5 active integrations."""
    pass


class IntegrationNotFoundError(Exception):
    """Raised when an integration is not found within the tenant scope."""
    pass


def connect_integration(
    db: Session,
    company_id: int,
    request: IntegrationConnectRequest,
) -> ExternalIntegration:
    """
    Connect or update an external platform integration for the tenant.
    Enforces the maximum 5 active integrations limit and validates credentials.
    """
    # 1. Check existing integration for this company and platform
    existing = (
        db.query(ExternalIntegration)
        .filter(
            ExternalIntegration.company_id == company_id,
            ExternalIntegration.platform == request.platform.value,
        )
        .first()
    )

    # 2. If creating a new active integration, enforce max 5 limit
    if not existing:
        active_count = (
            db.query(func.count(ExternalIntegration.id))
            .filter(
                ExternalIntegration.company_id == company_id,
                ExternalIntegration.status == IntegrationStatus.ACTIVE.value,
            )
            .scalar()
            or 0
        )
        if active_count >= MAX_ACTIVE_INTEGRATIONS_PER_COMPANY:
            raise MaxIntegrationsReachedError(
                f"Maximum active integrations ({MAX_ACTIVE_INTEGRATIONS_PER_COMPANY}) reached for this company."
            )

    # 3. Validate credentials with platform adapter
    creds = request.get_credential_dict()
    adapter = get_integration_adapter(request.platform)
    adapter.validate_connection(creds)

    # 4. Authenticated encryption of credentials at rest
    encrypted_blob = encrypt_credentials(creds)

    if existing:
        existing.name = request.name
        existing.status = IntegrationStatus.ACTIVE.value
        existing.credentials_encrypted = encrypted_blob
        existing.sync_error = None
        if request.metadata_payload:
            existing.metadata_payload = request.metadata_payload
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    new_integration = ExternalIntegration(
        company_id=company_id,
        platform=request.platform.value,
        name=request.name,
        status=IntegrationStatus.ACTIVE.value,
        credentials_encrypted=encrypted_blob,
        sync_status=SyncStatus.IDLE.value,
        metadata_payload=request.metadata_payload,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_integration)
    db.commit()
    db.refresh(new_integration)
    return new_integration


def disconnect_integration(
    db: Session,
    company_id: int,
    integration_id: int,
) -> ExternalIntegration:
    """
    Disconnect an integration (tenant-scoped).
    Marks integration as DISCONNECTED without deleting historical insights.
    """
    integration = (
        db.query(ExternalIntegration)
        .filter(
            ExternalIntegration.id == integration_id,
            ExternalIntegration.company_id == company_id,
        )
        .first()
    )
    if not integration:
        raise IntegrationNotFoundError("Integration not found for this company.")

    integration.status = IntegrationStatus.DISCONNECTED.value
    integration.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(integration)
    return integration


def get_integration(
    db: Session,
    company_id: int,
    integration_id: int,
) -> Optional[ExternalIntegration]:
    """Retrieve integration with strict tenant scoping."""
    return (
        db.query(ExternalIntegration)
        .filter(
            ExternalIntegration.id == integration_id,
            ExternalIntegration.company_id == company_id,
        )
        .first()
    )


def list_integrations(
    db: Session,
    company_id: int,
) -> List[ExternalIntegration]:
    """List all integrations for the authenticated company."""
    return (
        db.query(ExternalIntegration)
        .filter(ExternalIntegration.company_id == company_id)
        .order_by(ExternalIntegration.created_at.desc())
        .all()
    )


def sync_integration_data(
    db: Session,
    company_id: int,
    integration_id: int,
) -> SyncResultResponse:
    """
    Fetch recent external content, normalize, deduplicate, compute pgvector embeddings,
    and persist into company_social_insights.
    
    CRITICAL MEMORY QUARANTINE INVARIANT:
    No rows are written to company_memories.
    """
    integration = get_integration(db, company_id, integration_id)
    if not integration:
        raise IntegrationNotFoundError("Integration not found for this company.")

    if integration.status != IntegrationStatus.ACTIVE.value:
        raise IntegrationProviderError(f"Cannot sync integration in '{integration.status}' status.")

    integration.sync_status = SyncStatus.SYNCING.value
    db.commit()

    created_count = 0
    updated_count = 0
    skipped_count = 0

    try:
        # Decrypt credentials
        creds = decrypt_credentials(integration.credentials_encrypted)
        adapter = get_integration_adapter(integration.platform)

        # Fetch posts
        raw_posts = adapter.fetch_recent_posts(creds, since=integration.last_synced_at)
        embedding_provider = get_embedding_provider()

        for raw in raw_posts:
            norm = adapter.normalize(raw)
            if not norm.content:
                skipped_count += 1
                continue

            # Deduplication lookup
            existing_insight = (
                db.query(CompanySocialInsight)
                .filter(
                    CompanySocialInsight.company_id == company_id,
                    CompanySocialInsight.platform == integration.platform,
                    CompanySocialInsight.external_id == norm.external_id,
                )
                .first()
            )

            if existing_insight:
                if existing_insight.content_hash == norm.content_hash:
                    # Unchanged content: skip re-embedding
                    skipped_count += 1
                    continue

                # Content updated: re-embed and update
                new_vec = embedding_provider.embed_text(norm.content)
                existing_insight.content = norm.content
                existing_insight.content_hash = norm.content_hash
                existing_insight.author = norm.author
                existing_insight.source_url = norm.source_url
                existing_insight.embedding = new_vec
                existing_insight.fetched_at = datetime.utcnow()
                existing_insight.metadata_payload = norm.metadata_payload
                updated_count += 1
            else:
                # New insight: generate 384-dimensional vector embedding
                vec = embedding_provider.embed_text(norm.content)
                insight_record = CompanySocialInsight(
                    company_id=company_id,
                    integration_id=integration.id,
                    platform=integration.platform,
                    external_id=norm.external_id,
                    source_url=norm.source_url,
                    author=norm.author,
                    content=norm.content,
                    content_hash=norm.content_hash,
                    published_at=norm.published_at,
                    fetched_at=datetime.utcnow(),
                    freshness_score=1.0,
                    embedding=vec,
                    metadata_payload=norm.metadata_payload,
                    created_at=datetime.utcnow(),
                )
                db.add(insight_record)
                created_count += 1

        integration.sync_status = SyncStatus.SUCCESS.value
        integration.last_synced_at = datetime.utcnow()
        integration.sync_error = None
        db.commit()

        return SyncResultResponse(
            integration_id=integration.id,
            company_id=company_id,
            platform=integration.platform,
            fetched_count=len(raw_posts),
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            sync_status=SyncStatus.SUCCESS.value,
        )

    except Exception as exc:
        integration.sync_status = SyncStatus.FAILED.value
        integration.sync_error = str(exc)
        db.commit()
        raise IntegrationProviderError(f"Synchronization failed: {str(exc)}") from exc


def retrieve_relevant_social_insights(
    db: Session,
    company_id: int,
    query: str,
    top_k: int = 5,
    platform: Optional[IntegrationPlatform | str] = None,
    min_similarity: float = 0.0,
) -> List[RetrievedInsightItem]:
    """
    Retrieve top-k relevant external company insights using pgvector cosine distance
    and freshness decay ranking.
    
    STRICT TENANT ISOLATION:
    Vector search matches strictly against company_id.
    """
    if not query or not query.strip():
        return []

    bounded_top_k = max(1, min(50, top_k))
    embedding_provider = get_embedding_provider()
    query_vector = embedding_provider.embed_text(query.strip())

    distance_expr = CompanySocialInsight.embedding.cosine_distance(query_vector)

    query_builder = (
        db.query(
            CompanySocialInsight.id,
            CompanySocialInsight.company_id,
            CompanySocialInsight.integration_id,
            CompanySocialInsight.platform,
            CompanySocialInsight.external_id,
            CompanySocialInsight.source_url,
            CompanySocialInsight.author,
            CompanySocialInsight.content,
            CompanySocialInsight.published_at,
            distance_expr.label("distance"),
        )
        .filter(
            CompanySocialInsight.company_id == company_id,
            CompanySocialInsight.embedding.isnot(None),
        )
    )

    if platform:
        p_val = platform.value if isinstance(platform, IntegrationPlatform) else str(platform).lower()
        query_builder = query_builder.filter(CompanySocialInsight.platform == p_val)

    # Fetch extra candidates to account for freshness decay re-ranking
    candidates = query_builder.order_by(distance_expr).limit(bounded_top_k * 2).all()

    now = datetime.utcnow()
    ranked_items: List[Tuple[float, RetrievedInsightItem]] = []

    for r in candidates:
        cosine_distance = float(r.distance) if r.distance is not None else 1.0
        similarity = max(0.0, min(1.0, round(1.0 - cosine_distance, 4)))

        if similarity < min_similarity:
            continue

        # Freshness score based on half-life decay (~30 days)
        if r.published_at:
            pub_date = r.published_at if r.published_at.tzinfo is None else r.published_at.replace(tzinfo=None)
            days_old = max(0.0, (now - pub_date).total_seconds() / 86400.0)
            freshness = max(0.1, round(math.exp(-0.023 * days_old), 4))
        else:
            freshness = 1.0

        final_score = round(similarity * freshness, 4)

        item = RetrievedInsightItem(
            id=r.id,
            company_id=r.company_id,
            integration_id=r.integration_id,
            platform=r.platform,
            external_id=r.external_id,
            source_url=r.source_url,
            author=r.author,
            content=r.content,
            published_at=r.published_at,
            similarity_score=similarity,
            freshness_score=freshness,
            final_score=final_score,
        )
        ranked_items.append((final_score, item))

    # Sort by final score descending
    ranked_items.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in ranked_items[:bounded_top_k]]
