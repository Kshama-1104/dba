from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.schemas.company_ai_profile import (
    CompanyAIProfileResponse,
    CompanyAIProfileUpdate,
)
from backend.app.services.company_ai_profile_service import (
    create_or_update_company_ai_profile,
    get_company_ai_profile,
)

router = APIRouter(
    prefix="/api/v1/company/ai-profile",
    tags=["Company AI Profile"],
)


@router.get(
    "",
    response_model=CompanyAIProfileResponse,
    summary="Get company AI profile",
)
def get_company_ai_profile_endpoint(
    current_user: User = Depends(
        require_role(
            UserRole.COMPANY_ADMIN,
            UserRole.REVIEWER,
            UserRole.EDITOR,
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve the AI context profile for the authenticated user's company.
    Tenant isolation is enforced by current_user.company_id.
    """
    profile = get_company_ai_profile(
        db=db,
        company_id=current_user.company_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company AI profile not found.",
        )

    return profile


@router.put(
    "",
    response_model=CompanyAIProfileResponse,
    summary="Create or update company AI profile",
)
def put_company_ai_profile_endpoint(
    request: CompanyAIProfileUpdate,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    """
    Create or update the AI context profile for the authenticated Company Admin's company.
    Only COMPANY_ADMIN has permission to create or modify brand guidelines.
    """
    try:
        profile = create_or_update_company_ai_profile(
            db=db,
            company_id=current_user.company_id,
            profile_in=request,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return profile
