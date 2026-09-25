from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User
from backend.app.schemas.access_request import AccessRequestDecision
from backend.app.services.access_request_decision_service import (
    decide_access_request,
)


router = APIRouter(
    prefix="/api/v1/access-requests",
    tags=["Access Request Decisions"],
)


@router.patch("/{request_id}/decision")
def decide_access_request_endpoint(
    request_id: int,
    request: AccessRequestDecision,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept or reject an access request.

    Accepted requests:
        - Activate the requester
        - Generate a temporary password
        - Return the temporary password for the
          email-delivery layer

    Rejected requests:
        - Mark the request as rejected
        - Mark the requester as rejected
    """

    try:
        (
            access_request,
            requester,
            temporary_password,
        ) = decide_access_request(
            db=db,
            request_id=request_id,
            approver=current_user,
            decision=request.decision,
        )

        response = {
            "message": (
                "Access request accepted successfully."
                if access_request.status.value == "accepted"
                else "Access request rejected successfully."
            ),
            "access_request": {
                "id": access_request.id,
                "company_id": access_request.company_id,
                "requester_id": access_request.requester_id,
                "approver_id": access_request.approver_id,
                "request_type": access_request.request_type.value,
                "status": access_request.status.value,
                "responded_at": access_request.responded_at,
            },
            "requester": {
                "id": requester.id,
                "name": requester.name,
                "email": requester.email,
                "role": requester.role.value,
                "status": requester.status.value,
                "permanent_password_set": (
                    requester.permanent_password_set
                ),
                "temporary_password_expires_at": (
                    requester.temporary_password_expires_at
                ),
            },
        }

        # -----------------------------------------------------
        # IMPORTANT:
        # Only return the plaintext temporary password when
        # the request was accepted and a new password was
        # generated.
        # -----------------------------------------------------

        if temporary_password is not None:
            response["temporary_password"] = temporary_password

            response["message"] = (
                "Access request accepted successfully. "
                "A temporary password has been generated."
            )

        return response

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )