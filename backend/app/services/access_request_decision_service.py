from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.access_request import (
    AccessRequest,
    AccessRequestStatus,
    AccessRequestType,
)
from backend.app.models.user import User, UserRole, UserStatus
from backend.app.services.temporary_password_service import (
    assign_temporary_password,
)


def utc_now() -> datetime:
    """
    Return current UTC time as a timezone-naive datetime.

    Database DateTime columns currently use timezone-naive
    timestamps.
    """
    return datetime.utcnow()


def decide_access_request(
    db: Session,
    request_id: int,
    approver: User,
    decision: str,
) -> tuple[AccessRequest, User, str | None]:
    """
    Accept or reject an access request.

    Reviewer approval:
        Company Admin
            ↓
        Reviewer becomes ACTIVE
            ↓
        42-hour temporary password generated

    Editor approval:
        Reviewer
            ↓
        Editor becomes ACTIVE
            ↓
        48-hour temporary password generated

    Returns:
        access_request
        requester
        temporary_password

    The temporary password is returned only when an access
    request is accepted.
    """

    # ---------------------------------------------------------
    # 1. Find access request
    # ---------------------------------------------------------

    access_request = db.scalar(
        select(AccessRequest).where(
            AccessRequest.id == request_id
        )
    )

    if access_request is None:
        raise ValueError(
            "Access request not found."
        )

    # ---------------------------------------------------------
    # 2. Verify approver
    # ---------------------------------------------------------

    if access_request.approver_id != approver.id:
        raise ValueError(
            "You are not authorized to decide this access request."
        )

    # ---------------------------------------------------------
    # 3. Request must still be pending
    # ---------------------------------------------------------

    if access_request.status != AccessRequestStatus.PENDING:
        raise ValueError(
            "This access request has already been decided."
        )

    # ---------------------------------------------------------
    # 4. Check request expiry
    # ---------------------------------------------------------

    if access_request.expires_at <= utc_now():
        access_request.status = AccessRequestStatus.EXPIRED
        access_request.responded_at = utc_now()

        db.commit()

        raise ValueError(
            "This access request has expired."
        )

    # ---------------------------------------------------------
    # 5. Validate decision
    # ---------------------------------------------------------

    normalized_decision = decision.strip().lower()

    if normalized_decision not in {
        "accepted",
        "rejected",
    }:
        raise ValueError(
            "Decision must be 'accepted' or 'rejected'."
        )

    # ---------------------------------------------------------
    # 6. Load requester
    # ---------------------------------------------------------

    requester = db.scalar(
        select(User).where(
            User.id == access_request.requester_id
        )
    )

    if requester is None:
        raise ValueError(
            "Requester account not found."
        )

    # ---------------------------------------------------------
    # 7. Verify company isolation
    # ---------------------------------------------------------

    if requester.company_id != approver.company_id:
        raise ValueError(
            "Requester and approver must belong to the same company."
        )

    if access_request.company_id != approver.company_id:
        raise ValueError(
            "Access request does not belong to your company."
        )

    # ---------------------------------------------------------
    # 8. Validate role hierarchy
    # ---------------------------------------------------------

    if access_request.request_type == AccessRequestType.REVIEWER_ACCESS:

        # Only Company Admin can approve Reviewer access.
        if approver.role != UserRole.COMPANY_ADMIN:
            raise ValueError(
                "Only a Company Admin can approve Reviewer access."
            )

        # Requester must actually be a Reviewer.
        if requester.role != UserRole.REVIEWER:
            raise ValueError(
                "Requester is not a Reviewer."
            )

    elif access_request.request_type == AccessRequestType.EDITOR_ACCESS:

        # Only Reviewer can approve Editor access.
        if approver.role != UserRole.REVIEWER:
            raise ValueError(
                "Only a Reviewer can approve Editor access."
            )

        # Requester must actually be an Editor.
        if requester.role != UserRole.EDITOR:
            raise ValueError(
                "Requester is not an Editor."
            )

    else:
        raise ValueError(
            "Unsupported access request type."
        )

    # ---------------------------------------------------------
    # 9. Handle rejection
    # ---------------------------------------------------------

    if normalized_decision == "rejected":

        access_request.status = AccessRequestStatus.REJECTED
        requester.status = UserStatus.REJECTED
        access_request.responded_at = utc_now()

        db.commit()

        db.refresh(access_request)
        db.refresh(requester)

        return (
            access_request,
            requester,
            None,
        )

    # ---------------------------------------------------------
    # 10. Handle acceptance
    # ---------------------------------------------------------

    requester.status = UserStatus.ACTIVE

    access_request.status = AccessRequestStatus.ACCEPTED
    access_request.responded_at = utc_now()

    # ---------------------------------------------------------
    # 11. Generate temporary password
    # ---------------------------------------------------------

    temporary_password = assign_temporary_password(
        db=db,
        user=requester,
    )

    # assign_temporary_password() commits the user update.
    # We still commit the access-request state explicitly.
    db.commit()

    db.refresh(access_request)
    db.refresh(requester)

    return (
        access_request,
        requester,
        temporary_password,
    )