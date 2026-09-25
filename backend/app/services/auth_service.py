from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import (
    create_access_token,
    verify_password,
)
from backend.app.models.user import User, UserStatus


def utc_now() -> datetime:
    return datetime.utcnow()


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:

    user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if user is None:
        return None

    if user.status != UserStatus.ACTIVE:
        return None

    if user.permanent_password_set:
        if user.password_hash is None:
            return None

        if not verify_password(
            password,
            user.password_hash,
        ):
            return None

        return user

    if user.temporary_password_hash is None:
        return None

    if (
        user.temporary_password_expires_at is None
        or user.temporary_password_expires_at <= utc_now()
    ):
        return None

    if not verify_password(
        password,
        user.temporary_password_hash,
    ):
        return None

    return user


def create_user_access_token(
    user: User,
) -> str:
    return create_access_token(
        user_id=user.id,
        role=user.role.value,
    )