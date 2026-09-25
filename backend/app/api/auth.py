from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import (
    get_current_user,
    hash_password,
    verify_password,
)
from backend.app.models.user import User
from backend.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    SetPermanentPasswordRequest,
)
from backend.app.services.auth_service import (
    authenticate_user,
    create_user_access_token,
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db=db,
        email=request.email,
        password=request.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_user_access_token(user)

    return LoginResponse(
        access_token=access_token,
        user_id=user.id,
        role=user.role.value,
        company_id=user.company_id,
        requires_password_setup=(
            not user.permanent_password_set
        ),
    )


@router.post("/set-permanent-password")
def set_permanent_password(
    request: SetPermanentPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.permanent_password_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permanent password has already been configured.",
        )

    if current_user.temporary_password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Temporary password is not available.",
        )

    if (
        current_user.temporary_password_expires_at is None
        or current_user.temporary_password_expires_at
        <= datetime.utcnow()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Temporary password has expired.",
        )

    if not verify_password(
        request.current_temporary_password,
        current_user.temporary_password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current temporary password is incorrect.",
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

    if verify_password(
        request.new_password,
        current_user.temporary_password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the temporary password.",
        )

    current_user.password_hash = hash_password(
        request.new_password,
    )

    current_user.temporary_password_hash = None
    current_user.temporary_password_expires_at = None
    current_user.permanent_password_set = True

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Permanent password created successfully.",
        "requires_password_setup": False,
    }