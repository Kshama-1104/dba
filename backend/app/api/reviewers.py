from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole, UserStatus


router = APIRouter(
    prefix="/api/v1/company/reviewers",
    tags=["Reviewers"],
)


@router.get("")
def get_company_reviewers(
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    reviewers = db.scalars(
        select(User)
        .where(
            User.company_id == current_user.company_id,
            User.role == UserRole.REVIEWER,
            User.status != UserStatus.DEACTIVATED,
        )
        .order_by(User.name.asc())
    ).all()

    return {
        "count": len(reviewers),
        "reviewers": [
            {
                "id": reviewer.id,
                "name": reviewer.name,
                "email": reviewer.email,
                "status": reviewer.status.value,
            }
            for reviewer in reviewers
        ],
    }