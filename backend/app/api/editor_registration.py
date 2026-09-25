from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.editor_registration import (
    EditorCAPTCHAVerificationRequest,
    EditorOTPVerificationRequest,
    EditorRegistrationCompleteRequest,
    EditorRegistrationRequest,
    EditorReviewerSelectionRequest,
)
from backend.app.services.editor_registration_service import (
    complete_editor_registration,
    create_editor_registration_session,
    generate_editor_captcha,
    generate_editor_otp,
    get_active_reviewers,
    select_editor_reviewer,
    verify_editor_captcha,
    verify_editor_otp,
)


router = APIRouter(
    prefix="/api/v1/registration/editor",
    tags=["Editor Registration"],
)


@router.post("")
def start_editor_registration(
    request: EditorRegistrationRequest,
    db: Session = Depends(get_db),
):
    try:
        session = create_editor_registration_session(
            db=db,
            name=request.name,
            email=request.email,
            id_card_url=request.id_card_url,
        )

        otp = generate_editor_otp(
            db=db,
            registration_token=session.registration_token,
        )

        return {
            "message": "Editor registration started successfully.",
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
def send_editor_otp(
    registration_token: str,
    db: Session = Depends(get_db),
):
    try:
        otp = generate_editor_otp(
            db=db,
            registration_token=registration_token,
        )

        return {
            "message": "Editor OTP generated successfully.",
            "development_otp": otp,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/otp/verify")
def verify_editor_otp_endpoint(
    request: EditorOTPVerificationRequest,
    db: Session = Depends(get_db),
):
    try:
        session = verify_editor_otp(
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
def generate_editor_captcha_endpoint(
    registration_token: str,
    db: Session = Depends(get_db),
):
    try:
        captcha = generate_editor_captcha(
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
def verify_editor_captcha_endpoint(
    request: EditorCAPTCHAVerificationRequest,
    db: Session = Depends(get_db),
):
    try:
        session = verify_editor_captcha(
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


@router.get("/reviewers")
def get_editor_reviewers(
    registration_token: str,
    db: Session = Depends(get_db),
):
    try:
        reviewers = get_active_reviewers(
            db=db,
            registration_token=registration_token,
        )

        return {
            "reviewers": [
                {
                    "id": reviewer.id,
                    "name": reviewer.name,
                    "email": reviewer.email,
                }
                for reviewer in reviewers
            ]
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/reviewer/select")
def select_editor_reviewer_endpoint(
    request: EditorReviewerSelectionRequest,
    db: Session = Depends(get_db),
):
    try:
        session = select_editor_reviewer(
            db=db,
            registration_token=request.registration_token,
            reviewer_id=request.reviewer_id,
        )

        return {
            "message": "Reviewer selected successfully.",
            "selected_reviewer_id": session.selected_reviewer_id,
            "current_step": session.current_step,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/complete")
def complete_editor_registration_endpoint(
    request: EditorRegistrationCompleteRequest,
    db: Session = Depends(get_db),
):
    try:
        editor, access_request = complete_editor_registration(
            db=db,
            registration_token=request.registration_token,
        )

        return {
            "message": (
                "Editor registration completed. "
                "Access request has been sent to the selected Reviewer."
            ),
            "editor": {
                "id": editor.id,
                "name": editor.name,
                "email": editor.email,
                "company_id": editor.company_id,
                "role": editor.role.value,
                "status": editor.status.value,
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
            detail=str(exc)
        )