from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.registration import (
    CompanyRegistrationRequest,
    CompleteCompanyRegistrationRequest,
)
from backend.app.services.registration_service import (
    create_registration_session,
    complete_company_registration,
)


router = APIRouter(
    prefix="/api/v1/registration",
    tags=["Registration"],
)


@router.post(
    "/company",
    status_code=status.HTTP_201_CREATED,
)
def start_company_registration(
    request: CompanyRegistrationRequest,
    db: Session = Depends(get_db),
):
    try:
        registration_session = create_registration_session(
            db=db,
            request=request,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return {
        "message": "Company registration started.",
        "registration_token": registration_session.registration_token,
        "current_step": registration_session.current_step,
        "next_step": 2,
    }


@router.post(
    "/company/complete",
    status_code=status.HTTP_201_CREATED,
)
def complete_company_registration_endpoint(
    request: CompleteCompanyRegistrationRequest,
    db: Session = Depends(get_db),
):
    try:
        company = complete_company_registration(
            db=db,
            registration_token=request.registration_token,
            password=request.password,
            confirm_password=request.confirm_password,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "message": "Company account created successfully.",
        "company_id": company.id,
        "company_name": company.name,
        "company_email": company.company_email,
        "role": "company_admin",
    }