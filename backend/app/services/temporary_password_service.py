import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.models.user import User, UserRole


REVIEWER_TEMP_PASSWORD_HOURS = 42
EDITOR_TEMP_PASSWORD_HOURS = 48


def utc_now() -> datetime:
    return datetime.utcnow()


def generate_temporary_password(length: int = 16) -> str:
    characters = (
        string.ascii_letters
        + string.digits
        + "!@#$%^&*"
    )

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def assign_temporary_password(
    db: Session,
    user: User,
) -> str:

    if user.role == UserRole.REVIEWER:
        expiry_hours = REVIEWER_TEMP_PASSWORD_HOURS

    elif user.role == UserRole.EDITOR:
        expiry_hours = EDITOR_TEMP_PASSWORD_HOURS

    else:
        raise ValueError(
            "Temporary passwords are only supported for Reviewers and Editors."
        )

    temporary_password = generate_temporary_password()

    user.temporary_password_hash = hash_password(
        temporary_password
    )

    user.temporary_password_expires_at = (
        utc_now()
        + timedelta(hours=expiry_hours)
    )

    user.permanent_password_set = False

    db.commit()
    db.refresh(user)

    return temporary_password