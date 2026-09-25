from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.access_request import (
    AccessRequest,
    AccessRequestStatus,
    AccessRequestType,
)
from backend.app.models.user import User, UserRole, UserStatus


ACCESS_REQUEST_EXPIRY_HOURS = 24


def utc_now() -> datetime:
    return datetime.utcnow()


def create_reviewer_access_request(
    db: Session,
    reviewer: User,
) -> AccessRequest:

    if reviewer.role != UserRole.REVIEWER:
        raise ValueError(
            "Only a Reviewer can create a Reviewer access request."
        )

    if reviewer.status != UserStatus.PENDING:
        raise ValueError(
            "Reviewer account is not in a pending state."
        )

    company_admin = db.scalar(
        select(User).where(
            User.company_id == reviewer.company_id,
            User.role == UserRole.COMPANY_ADMIN,
            User.status == UserStatus.ACTIVE,
        )
    )

    if company_admin is None:
        raise ValueError(
            "Active Company Admin not found."
        )

    existing_request = db.scalar(
        select(AccessRequest).where(
            AccessRequest.requester_id == reviewer.id,
            AccessRequest.request_type
            == AccessRequestType.REVIEWER_ACCESS,
            AccessRequest.status == AccessRequestStatus.PENDING,
        )
    )

    if existing_request is not None:
        raise ValueError(
            "A pending Reviewer access request already exists."
        )

    request = AccessRequest(
        company_id=reviewer.company_id,
        requester_id=reviewer.id,
        approver_id=company_admin.id,
        request_type=AccessRequestType.REVIEWER_ACCESS,
        status=AccessRequestStatus.PENDING,
        expires_at=(
            utc_now()
            + timedelta(
                hours=ACCESS_REQUEST_EXPIRY_HOURS
            )
        ),
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    return request


def create_editor_access_request(
    db: Session,
    editor: User,
    reviewer_id: int,
) -> AccessRequest:

    if editor.role != UserRole.EDITOR:
        raise ValueError(
            "Only an Editor can create an Editor access request."
        )

    if editor.status != UserStatus.PENDING:
        raise ValueError(
            "Editor account is not in a pending state."
        )

    reviewer = db.scalar(
        select(User).where(
            User.id == reviewer_id,
            User.company_id == editor.company_id,
            User.role == UserRole.REVIEWER,
            User.status == UserStatus.ACTIVE,
        )
    )

    if reviewer is None:
        raise ValueError(
            "Selected Reviewer is not available."
        )

    existing_request = db.scalar(
        select(AccessRequest).where(
            AccessRequest.requester_id == editor.id,
            AccessRequest.request_type
            == AccessRequestType.EDITOR_ACCESS,
            AccessRequest.status == AccessRequestStatus.PENDING,
        )
    )

    if existing_request is not None:
        raise ValueError(
            "A pending Editor access request already exists."
        )

    request = AccessRequest(
        company_id=editor.company_id,
        requester_id=editor.id,
        approver_id=reviewer.id,
        request_type=AccessRequestType.EDITOR_ACCESS,
        status=AccessRequestStatus.PENDING,
        expires_at=(
            utc_now()
            + timedelta(
                hours=ACCESS_REQUEST_EXPIRY_HOURS
            )
        ),
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    return request

def list_access_requests(db: Session, user: User):
    return db.scalars(
        select(AccessRequest).where(
            AccessRequest.company_id == user.company_id,
            AccessRequest.approver_id == user.id,
            AccessRequest.status == AccessRequestStatus.PENDING
        ).order_by(AccessRequest.created_at.desc())
    ).all()