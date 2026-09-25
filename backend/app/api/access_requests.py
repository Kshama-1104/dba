from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User, UserRole
from backend.app.schemas.access_request import (
    AccessRequestCreate,
    AccessRequestResponse,
)
from backend.app.services.access_request_service import (
    create_editor_access_request,
    create_reviewer_access_request,
)


router = APIRouter(
    prefix="/api/v1/access-requests",
    tags=["Access Requests"],
)


@router.post(
    "/reviewer",
    response_model=AccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_reviewer_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        request = create_reviewer_access_request(
            db=db,
            reviewer=current_user,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return request


@router.post(
    "/editor",
    response_model=AccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_editor_access(
    request_data: AccessRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        request = create_editor_access_request(
            db=db,
            editor=current_user,
            reviewer_id=request_data.approver_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return request

@router.get(
    "",
    response_model=list[AccessRequestResponse],
    status_code=status.HTTP_200_OK,
)
def list_access_requests_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.services.access_request_service import list_access_requests
    return list_access_requests(db=db, user=current_user)