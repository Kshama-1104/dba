from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.company_settings import CompanySettings
from backend.app.models.user import User, UserRole


class NotificationEmailUpdateRequest(BaseModel):
    notification_email: EmailStr


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


router = APIRouter(
    prefix="/api/v1/company/settings",
    tags=["Company Settings"],
)


@router.get("")
def get_company_settings(
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    settings = db.scalar(
        select(CompanySettings).where(
            CompanySettings.company_id == current_user.company_id
        )
    )

    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company settings not found.",
        )

    return {
        "company_id": settings.company_id,
        "notification_email": settings.notification_email,
        "blog_generation_enabled": settings.blog_generation_enabled,
        "publishing_enabled": settings.publishing_enabled,
    }


@router.patch("/notification-email")
def update_notification_email(
    request: NotificationEmailUpdateRequest,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    settings = db.scalar(
        select(CompanySettings).where(
            CompanySettings.company_id == current_user.company_id
        )
    )

    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company settings not found.",
        )

    settings.notification_email = str(request.notification_email)

    db.commit()
    db.refresh(settings)

    return {
        "message": "Notification email updated successfully.",
        "notification_email": settings.notification_email,
    }


@router.patch("/password")
def change_company_admin_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    from backend.app.core.security import (
        hash_password,
        verify_password,
    )

    if current_user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is not configured.",
        )

    if not verify_password(
        request.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if request.new_password != request.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match.",
        )

    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must contain at least 8 characters.",
        )

    if request.current_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )

    current_user.password_hash = hash_password(
        request.new_password
    )

    db.commit()

    return {
        "message": "Password changed successfully."
    }