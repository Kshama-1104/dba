from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.schemas.blog_format import (
    BlogFormatCreate,
    BlogFormatListResponse,
    BlogFormatResponse,
    BlogFormatUpdate,
)
from backend.app.services.blog_format_service import (
    activate_blog_format_version,
    create_or_update_blog_format,
    get_active_blog_format,
    get_blog_format_by_version,
    list_blog_format_versions,
)

router = APIRouter(
    prefix="/api/v1/company/blog-format",
    tags=["Global Blog Format"],
)


@router.get(
    "",
    response_model=BlogFormatResponse,
    summary="Get active global blog format",
)
def get_active_blog_format_endpoint(
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
            UserRole.REVIEWER,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve the currently active Company Global Blog Format (Level 2).
    Tenant isolation is enforced by current_user.company_id.
    """
    blog_format = get_active_blog_format(
        db=db,
        company_id=current_user.company_id,
    )
    if blog_format is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active global blog format found for this company.",
        )
    return blog_format


@router.put(
    "",
    response_model=BlogFormatResponse,
    summary="Create or update global blog format version",
)
def put_blog_format_endpoint(
    request: BlogFormatCreate,
    current_user: User = Depends(
        require_role(
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Create a new version of the Company Global Blog Format.
    Preserves all previous versions in the audit history and activates the new version.
    Restricted to Editor role (Company Admin and Reviewer are View-Only).
    """
    try:
        new_format = create_or_update_blog_format(
            db=db,
            company_id=current_user.company_id,
            format_in=request,
            user_id=current_user.id,
            activate=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return new_format


@router.get(
    "/versions",
    response_model=BlogFormatListResponse,
    summary="List all format versions",
)
def list_blog_format_versions_endpoint(
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
            UserRole.REVIEWER,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve all historical and active format versions for the authenticated company.
    """
    formats = list_blog_format_versions(
        db=db,
        company_id=current_user.company_id,
    )
    active_format = next((f for f in formats if f.is_active), None)
    return BlogFormatListResponse(
        total_versions=len(formats),
        active_version=active_format.version if active_format else None,
        formats=formats,
    )


@router.get(
    "/versions/{version}",
    response_model=BlogFormatResponse,
    summary="Get a specific format version",
)
def get_blog_format_version_endpoint(
    version: int,
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.EDITOR,
            UserRole.REVIEWER,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific version of the Company Global Blog Format.
    """
    blog_format = get_blog_format_by_version(
        db=db,
        company_id=current_user.company_id,
        version=version,
    )
    if blog_format is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Format version {version} not found for this company.",
        )
    return blog_format


@router.post(
    "/versions/{version}/activate",
    response_model=BlogFormatResponse,
    summary="Activate/approve a specific format version",
)
def activate_blog_format_version_endpoint(
    version: int,
    current_user: User = Depends(
        require_role(
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Approve and activate a specific historical format version as the current active format.
    Deactivates any other active format for the company.
    Restricted to Editor role (Company Admin and Reviewer are View-Only).
    """
    try:
        activated_format = activate_blog_format_version(
            db=db,
            company_id=current_user.company_id,
            version=version,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return activated_format
