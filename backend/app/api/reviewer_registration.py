from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.reviewer_registration import (
    ReviewerCAPTCHAVerificationRequest,
    ReviewerOTPVerificationRequest,
    ReviewerRegistrationRequest,
)
from backend.app.services.reviewer_registration_service import (
    complete_reviewer_registration,
    create_reviewer_registration_session,
    generate_reviewer_captcha,
    generate_reviewer_otp,
    verify_reviewer_captcha,
    verify_reviewer_otp,
)


router = APIRouter(
    prefix="/api/v1/registration/reviewer",
    tags=["Reviewer Registration"],
)


@router.post("")
def start_reviewer_registration(
    request: ReviewerRegistrationRequest,
    db: Session = Depends(get_db),
):
    """
    Start Reviewer registration.

    The company is identified automatically from the
    domain of the reviewer's company email.
    """

    try:
        session = create_reviewer_registration_session(
            db=db,
            name=request.name,
            email=request.email,
            id_card_url=request.id_card_url,
        )

        # Development mode:
        # In production this OTP must be sent through
        # the configured email service.
        otp = generate_reviewer_otp(
            db=db,
            registration_token=session.registration_token,
        )

        return {
            "message": "Reviewer registration started successfully.",
            "registration_token": session.registration_token,
            "company_id": session.company_id,
            "current_step": session.current_step,
            "development_otp": otp,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/otp/send")
def send_reviewer_otp(
    registration_token: str,
    db: Session = Depends(get_db),
):
    """
    Resend Reviewer OTP.

    Maximum:
        3 OTP sends/resends per registration session.
    """

    try:
        otp = generate_reviewer_otp(
            db=db,
            registration_token=registration_token,
        )

        return {
            "message": "Reviewer OTP generated successfully.",
            "development_otp": otp,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/otp/verify")
def verify_reviewer_otp_endpoint(
    request: ReviewerOTPVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    Verify Reviewer OTP.
    """

    try:
        session = verify_reviewer_otp(
            db=db,
            registration_token=request.registration_token,
            otp=request.otp,
        )

        return {
            "message": "OTP verified successfully.",
            "registration_token": session.registration_token,
            "current_step": session.current_step,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/captcha/generate")
def generate_reviewer_captcha_endpoint(
    registration_token: str,
    db: Session = Depends(get_db),
):
    """
    Generate Reviewer CAPTCHA.

    CAPTCHA refresh is limited by the registration service.
    """

    try:
        captcha = generate_reviewer_captcha(
            db=db,
            registration_token=registration_token,
        )

        return {
            "message": "CAPTCHA generated successfully.",
            "development_captcha": captcha,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/captcha/verify")
def verify_reviewer_captcha_endpoint(
    request: ReviewerCAPTCHAVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    Verify Reviewer CAPTCHA.
    """

    try:
        session = verify_reviewer_captcha(
            db=db,
            registration_token=request.registration_token,
            captcha=request.captcha,
        )

        return {
            "message": "CAPTCHA verified successfully.",
            "registration_token": session.registration_token,
            "current_step": session.current_step,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/complete")
def complete_reviewer_registration_endpoint(
    registration_token: str,
    db: Session = Depends(get_db),
):
    """
    Complete Reviewer registration.

    Creates:
        - Reviewer with PENDING status
        - Reviewer -> Company Admin access request
    """

    try:
        reviewer, access_request = complete_reviewer_registration(
            db=db,
            registration_token=registration_token,
        )

        return {
            "message": (
                "Reviewer registration completed. "
                "Access request has been sent to the Company Admin."
            ),
            "reviewer": {
                "id": reviewer.id,
                "name": reviewer.name,
                "email": reviewer.email,
                "company_id": reviewer.company_id,
                "role": reviewer.role.value,
                "status": reviewer.status.value,
            },
            "access_request": {
                "id": access_request.id,
                "status": access_request.status.value,
                "request_type": access_request.request_type.value,
                "approver_id": access_request.approver_id,
                "expires_at": access_request.expires_at,
            },
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )