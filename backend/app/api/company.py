from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.company import Company
from backend.app.models.user import User, UserRole
from backend.app.schemas.company import CompanyDashboardResponse


router = APIRouter(
    prefix="/api/v1/company",
    tags=["Company"],
)


@router.get(
    "/dashboard",
    response_model=CompanyDashboardResponse,
)
def get_company_dashboard(
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    company = db.scalar(
        select(Company).where(
            Company.id == current_user.company_id
        )
    )

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    return {
        "company": {
            "id": company.id,
            "name": company.name,
            "description": company.description,
            "logo_url": company.logo_url,
            "company_type": company.company_type,
            "industry": company.industry,
            "country_region": company.country_region,
            "company_email": company.company_email,
            "notification_email": company.notification_email,
        },
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "role": current_user.role.value,
        },
    }