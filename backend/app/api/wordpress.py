from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.schemas.wordpress import (
    WordPressConnectRequest,
    WordPressConnectionResponse,
    WordPressTestResponse,
    WordPressUpdateRequest,
)
from backend.app.services.wordpress_service import WordPressService

router = APIRouter(
    prefix="/api/v1/integrations/wordpress",
    tags=["WordPress Integration"],
)


@router.post(
    "",
    response_model=WordPressConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect or register WordPress site for the company",
)
def connect_wordpress(
    request: WordPressConnectRequest,
    current_user: User = Depends(require_role(UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    """Company Admin connects or updates the company WordPress site."""
    conn = WordPressService.create_or_update_connection(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        request=request,
    )
    return conn


@router.get(
    "",
    response_model=WordPressConnectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get company WordPress connection details (credentials masked)",
)
def get_wordpress_connection(
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    """Retrieve company WordPress connection metadata. Passwords are never returned."""
    conn = WordPressService.get_connection(db=db, company_id=current_user.company_id)
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WordPress connection not configured for this company.",
        )
    return conn


@router.put(
    "",
    response_model=WordPressConnectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update WordPress connection or rotate Application Password",
)
def update_wordpress_connection(
    request: WordPressUpdateRequest,
    current_user: User = Depends(require_role(UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    """Company Admin updates settings or rotates Application Password."""
    conn = WordPressService.update_connection(
        db=db,
        company_id=current_user.company_id,
        request=request,
    )
    return conn


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect and physically remove company WordPress connection",
)
def delete_wordpress_connection(
    current_user: User = Depends(require_role(UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    """Company Admin disconnects WordPress site. Encrypted credentials are permanently purged."""
    WordPressService.delete_connection(db=db, company_id=current_user.company_id)
    return None


@router.post(
    "/test",
    response_model=WordPressTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test reachability, credentials, and publishing capabilities without creating a post",
)
async def test_wordpress_connection(
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)
    ),
    db: Session = Depends(get_db),
):
    """Test target WordPress connection. Reviewers are forbidden from executing tests."""
    return await WordPressService.test_connection(db=db, company_id=current_user.company_id)
