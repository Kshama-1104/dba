"""
Blog Generation API — Phase 6

Endpoints for generating and retrieving daily blog drafts.

RBAC:
    Editor:        GENERATE, LIST, GET
    Company Admin: LIST, GET (403 on Generate)
    Reviewer:      LIST, GET (403 on Generate)
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role
from backend.app.models.blog import BlogStatus
from backend.app.models.user import User, UserRole
from backend.app.schemas.blog import (
    BlogDetailResponse,
    BlogGenerateRequest,
    BlogResponse,
    BlogSummaryResponse,
    BlogValidationResponse,
)
from backend.app.services.blog_format_service import get_active_blog_format
from backend.app.services.blog_service import (
    BlogGenerationError,
    BlogService,
    ConcurrencyError,
)
from backend.app.services.blog_validation_service import BlogValidationService


router = APIRouter(
    prefix="/api/v1/blogs",
    tags=["Blog Generation"],
)


@router.post(
    "/generate",
    response_model=BlogDetailResponse,
    summary="Generate a structured blog draft from a selected topic",
)
def generate_blog(
    request: BlogGenerateRequest,
    response: Response,
    current_user: User = Depends(require_role(UserRole.EDITOR)),
    db: Session = Depends(get_db),
):
    """
    Generate and persist a structured blog draft from a confirmed topic candidate.
    
    RBAC:
        Editor ONLY. Company Admin and Reviewer receive 403 Forbidden.
        
    Responses:
        201 Created: New blog draft generated and persisted.
        200 OK: Existing draft returned (idempotent reconciliation).
        400 Bad Request: Topic is not in 'selected' state.
        404 Not Found: Topic candidate not found or belongs to another tenant.
        409 Conflict: Generation is currently in progress for this topic.
        500 Internal Server Error: Provider or synthesis failure. Topic remains 'selected'.
    """
    service = BlogService(db=db)
    try:
        blog, is_new = service.generate_blog(
            company_id=current_user.company_id,
            user_id=current_user.id,
            topic_candidate_id=request.topic_candidate_id,
            editor_instruction=request.editor_instruction,
        )
        response.status_code = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
        return blog
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except ConcurrencyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except BlogGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blog generation failed. Topic remains selected for retry.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during blog generation.",
        )


@router.get(
    "",
    response_model=List[BlogSummaryResponse],
    summary="List blog drafts for the authenticated company",
)
def list_blogs(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    status: Optional[BlogStatus] = Query(None, description="Optional status filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List blog drafts for the authenticated company.
    
    RBAC:
        Editor, Company Admin, and Reviewer are permitted.
        Results are strictly isolated to the authenticated user's company_id.
    """
    service = BlogService(db=db)
    return service.list_blogs(
        company_id=current_user.company_id,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=BlogDetailResponse,
    summary="Get a specific blog draft by ID",
)
def get_blog(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve full details of a specific blog draft, including structured JSON AST
    and rendered Markdown.
    
    RBAC:
        Editor, Company Admin, and Reviewer are permitted.
        Strict tenant isolation: Cross-tenant IDs return 404 Not Found.
    """
    service = BlogService(db=db)
    blog = service.get_blog(company_id=current_user.company_id, blog_id=id)
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found.",
        )
    return blog


@router.post(
    "/{id}/validate",
    response_model=BlogValidationResponse,
    summary="Validate blog draft against deterministic SEO and format criteria",
)
def validate_blog(
    id: int,
    current_user: User = Depends(require_role(UserRole.EDITOR, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Execute deterministic SEO and format validation on a blog draft (Phase 7).
    
    RBAC:
        Editor and Company Admin are permitted.
        Reviewer receives 403 Forbidden.
        
    Tenant Isolation:
        Derives company_id strictly from authenticated user.
        Cross-tenant blog IDs return 404 Not Found.
    """
    service = BlogService(db=db)
    blog = service.get_blog(company_id=current_user.company_id, blog_id=id)
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found.",
        )

    active_format = get_active_blog_format(db=db, company_id=current_user.company_id)
    validation_service = BlogValidationService(db=db)
    return validation_service.validate_blog(
        blog=blog,
        active_format=active_format,
        persist=True,
    )


@router.get(
    "/{id}/validation",
    response_model=BlogValidationResponse,
    summary="Get the latest validation report for a blog draft",
)
def get_blog_validation(
    id: int,
    current_user: User = Depends(
        require_role(
            UserRole.EDITOR,
            UserRole.COMPANY_ADMIN,
            UserRole.REVIEWER,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve the latest persisted SEO and format validation report for a blog draft.
    
    RBAC:
        Editor, Company Admin, and Reviewer are permitted.
        
    Tenant Isolation:
        Strictly company-scoped. Cross-tenant queries return 404 Not Found.
        
    Responses:
        200 OK: Persisted validation report returned.
        404 Not Found: Blog does not exist or validation has not been executed yet.
    """
    service = BlogService(db=db)
    blog = service.get_blog(company_id=current_user.company_id, blog_id=id)
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found.",
        )

    metadata = blog.generation_metadata or {}
    validation_data = metadata.get("validation")
    if not validation_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation has not been executed for this blog.",
        )

    return BlogValidationResponse.model_validate(validation_data)

