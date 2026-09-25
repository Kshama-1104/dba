from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.otp import VerifyOTPRequest
from backend.app.services.registration_service import (
    generate_registration_captcha,
    generate_registration_otp,
    verify_registration_captcha,
    verify_registration_otp,
)


router = APIRouter(
    prefix="/api/v1/registration",
    tags=["Registration"],
)


@router.post("/otp/send")
def send_registration_otp(
    registration_token: str,
    db: Session = Depends(get_db),
):
    try:
        otp = generate_registration_otp(
            db=db,
            registration_token=registration_token,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Development only.
    # Production will send the OTP through an email service.
    return {
        "message": "OTP generated successfully.",
        "development_otp": otp,
    }


@router.post("/otp/verify")
def verify_registration_otp_endpoint(
    request: VerifyOTPRequest,
    db: Session = Depends(get_db),
):
    try:
        verified = verify_registration_otp(
            db=db,
            registration_token=request.registration_token,
            otp=request.otp,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP.",
        )

    return {
        "message": "OTP verified successfully.",
        "otp_verified": True,
        "next_step": "captcha",
    }


@router.post("/captcha/generate")
def generate_registration_captcha_endpoint(
    registration_token: str,
    db: Session = Depends(get_db),
):
    try:
        captcha = generate_registration_captcha(
            db=db,
            registration_token=registration_token,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Development only.
    # Production will return a CAPTCHA image/challenge instead.
    return {
        "message": "CAPTCHA generated successfully.",
        "development_captcha": captcha,
    }


@router.post("/captcha/verify")
def verify_registration_captcha_endpoint(
    registration_token: str,
    captcha: str,
    db: Session = Depends(get_db),
):
    try:
        verified = verify_registration_captcha(
            db=db,
            registration_token=registration_token,
            captcha=captcha,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CAPTCHA.",
        )

    return {
        "message": "CAPTCHA verified successfully.",
        "captcha_verified": True,
        "next_step": 3,
    }