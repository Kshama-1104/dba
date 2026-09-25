from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole


router = APIRouter(
    prefix="/api/v1/company/id-cards",
    tags=["ID Cards"],
)


@router.get("/{user_id}")
def view_company_user_id_card(
    user_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(
            User.id == user_id,
            User.company_id == current_user.company_id,
            User.role.in_(
                [
                    UserRole.REVIEWER,
                    UserRole.EDITOR,
                ]
            ),
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reviewer or Editor not found.",
        )

    if user.id_card_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ID card is not available.",
        )

    return {
        "user_id": user.id,
        "name": user.name,
        "role": user.role.value,
        "id_card_url": user.id_card_url,
    }