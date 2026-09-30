"""
EXTERNAL INTEGRATIONS API ROUTER

Endpoints for managing company integrations, triggering data synchronization,
and executing semantic relevance retrieval over company social insights.

RBAC:
- COMPANY_ADMIN: Connect, disconnect, sync, list, retrieve.
- EDITOR: List, retrieve.
- REVIEWER: Access denied (403).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role
from backend.app.models.external_integration import (
    CompanySocialInsight,
    ExternalIntegration,
)
from backend.app.models.user import User, UserRole
from backend.app.schemas.external_integration import (
    InsightItemResponse,
    InsightRetrievalRequest,
    IntegrationConnectRequest,
    IntegrationPlatform,
    IntegrationResponse,
    RetrievedInsightItem,
    SyncResultResponse,
)
from backend.app.services.external_integration_provider import (
    IntegrationAuthError,
    IntegrationProviderError,
)
from backend.app.services.external_integration_service import (
    IntegrationNotFoundError,
    MaxIntegrationsReachedError,
    connect_integration,
    disconnect_integration,
    get_integration,
    list_integrations,
    retrieve_relevant_social_insights,
    sync_integration_data,
)

router = APIRouter(
    prefix="/api/v1/integrations",
    tags=["Integrations"],
)


@router.get(
    "",
    response_model=List[IntegrationResponse],
    summary="List all company external integrations",
)
def list_company_integrations(
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """List integrations strictly scoped to current user's company."""
    records = list_integrations(db=db, company_id=current_user.company_id)
    return records


@router.post(
    "/connect",
    response_model=IntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect or update an external platform integration",
)
def connect_platform_integration(
    request: IntegrationConnectRequest,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    """Company Admin connects an external integration. Enforces max 5 limit."""
    try:
        integration = connect_integration(
            db=db,
            company_id=current_user.company_id,
            request=request,
        )
        return integration
    except MaxIntegrationsReachedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IntegrationAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Integration authentication failed: {str(exc)}",
        ) from exc
    except IntegrationProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/insights",
    response_model=List[InsightItemResponse],
    summary="List company external insights",
)
def list_company_insights(
    platform: Optional[IntegrationPlatform] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """List normalized insights for the authenticated company."""
    query = (
        db.query(CompanySocialInsight)
        .filter(CompanySocialInsight.company_id == current_user.company_id)
    )
    if platform:
        query = query.filter(CompanySocialInsight.platform == platform.value)

    records = query.order_by(CompanySocialInsight.published_at.desc().nullslast()).offset(offset).limit(limit).all()
    return records


@router.post(
    "/insights/retrieve",
    response_model=List[RetrievedInsightItem],
    summary="Semantic retrieval over company social insights",
)
def retrieve_insights(
    request: InsightRetrievalRequest,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """Retrieve top-k relevant external insights using pgvector cosine distance and freshness."""
    results = retrieve_relevant_social_insights(
        db=db,
        company_id=current_user.company_id,
        query=request.query,
        top_k=request.top_k,
        platform=request.platform,
        min_similarity=request.min_similarity,
    )
    return results


@router.get(
    "/{integration_id}",
    response_model=IntegrationResponse,
    summary="Get integration status",
)
def get_integration_status(
    integration_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """Retrieve integration by ID (tenant-scoped)."""
    record = get_integration(
        db=db,
        company_id=current_user.company_id,
        integration_id=integration_id,
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found.",
        )
    return record


@router.post(
    "/{integration_id}/sync",
    response_model=SyncResultResponse,
    summary="Trigger synchronization for integration",
)
def trigger_integration_sync(
    integration_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    """Manually trigger data synchronization for an active integration."""
    try:
        result = sync_integration_data(
            db=db,
            company_id=current_user.company_id,
            integration_id=integration_id,
        )
        return result
    except IntegrationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except IntegrationProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{integration_id}",
    summary="Disconnect an integration",
)
def disconnect_company_integration(
    integration_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    """Disconnect an integration. Scoped to the authenticated company."""
    try:
        record = disconnect_integration(
            db=db,
            company_id=current_user.company_id,
            integration_id=integration_id,
        )
        return {
            "message": "Integration successfully disconnected.",
            "id": record.id,
            "status": record.status,
        }
    except IntegrationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
