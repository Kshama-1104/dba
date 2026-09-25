import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password, verify_password
from backend.app.models.access_request import (
    AccessRequest,
    AccessRequestStatus,
    AccessRequestType,
)
from backend.app.models.company import Company
from backend.app.models.editor_registration_session import (
    EditorRegistrationSession,
)
from backend.app.models.user import User, UserRole, UserStatus


REGISTRATION_SESSION_HOURS = 2

OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 3
MAX_OTP_RESENDS = 3

MAX_CAPTCHA_ATTEMPTS = 3
MAX_CAPTCHA_REFRESHES = 2


def utc_now() -> datetime:
    return datetime.utcnow()


def generate_registration_token() -> str:
    return secrets.token_urlsafe(32)


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_captcha(length: int = 6) -> str:
    characters = string.ascii_uppercase + string.digits

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def extract_email_domain(email: str) -> str:
    return email.strip().lower().split("@")[-1]


def find_company_by_email_domain(
    db: Session,
    email: str,
) -> Company | None:
    domain = extract_email_domain(email)

    companies = db.scalars(
        select(Company)
    ).all()

    matches = []

    for company in companies:
        company_domain = extract_email_domain(
            company.company_email
        )

        if company_domain == domain:
            matches.append(company)

    if len(matches) == 1:
        return matches[0]

    return None


def create_editor_registration_session(
    db: Session,
    name: str,
    email: str,
    id_card_url: str,
) -> EditorRegistrationSession:
    email = email.strip().lower()

    company = find_company_by_email_domain(
        db=db,
        email=email,
    )

    if company is None:
        raise ValueError(
            "No unique company was found for this email domain."
        )

    existing_user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if existing_user is not None:
        raise ValueError(
            "A user with this email already exists."
        )

    existing_session = db.scalar(
        select(EditorRegistrationSession).where(
            EditorRegistrationSession.email == email,
            EditorRegistrationSession.expires_at > utc_now(),
        )
    )

    if existing_session is not None:
        raise ValueError(
            "An active editor registration session already exists."
        )

    session = EditorRegistrationSession(
        registration_token=generate_registration_token(),
        name=name.strip(),
        email=email,
        id_card_url=id_card_url.strip(),
        company_id=company.id,
        current_step=1,
        expires_at=(
            utc_now()
            + timedelta(hours=REGISTRATION_SESSION_HOURS)
        ),
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def generate_editor_otp(
    db: Session,
    registration_token: str,
) -> str:
    session = db.scalar(
        select(EditorRegistrationSession).where(
            EditorRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Editor registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Editor registration session has expired."
        )

    if session.otp_resend_count >= MAX_OTP_RESENDS:
        raise ValueError(
            "Maximum OTP resend limit reached."
        )

    otp = generate_otp()

    session.otp_code_hash = hash_password(otp)

    session.otp_expires_at = (
        utc_now()
        + timedelta(minutes=OTP_EXPIRY_MINUTES)
    )

    session.otp_attempts = 0
    session.otp_resend_count += 1

    db.commit()
    db.refresh(session)

    return otp


def verify_editor_otp(
    db: Session,
    registration_token: str,
    otp: str,
) -> EditorRegistrationSession:
    session = db.scalar(
        select(EditorRegistrationSession).where(
            EditorRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Editor registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Editor registration session has expired."
        )

    if session.otp_code_hash is None:
        raise ValueError(
            "OTP has not been generated."
        )

    if (
        session.otp_expires_at is None
        or session.otp_expires_at <= utc_now()
    ):
        raise ValueError(
            "OTP has expired."
        )

    if session.otp_attempts >= MAX_OTP_ATTEMPTS:
        raise ValueError(
            "Maximum OTP verification attempts reached."
        )

    session.otp_attempts += 1

    if not verify_password(
        otp,
        session.otp_code_hash,
    ):
        db.commit()

        raise ValueError(
            "Invalid OTP."
        )

    session.current_step = 2

    db.commit()
    db.refresh(session)

    return session


def generate_editor_captcha(
    db: Session,
    registration_token: str,
) -> str:
    session = db.scalar(
        select(EditorRegistrationSession).where(
            EditorRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Editor registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Editor registration session has expired."
        )

    if session.current_step < 2:
        raise ValueError(
            "OTP verification is required before CAPTCHA."
        )

    if session.captcha_refresh_count >= MAX_CAPTCHA_REFRESHES:
        raise ValueError(
            "Maximum CAPTCHA refresh limit reached."
        )

    captcha = generate_captcha()

    session.captcha_code_hash = hash_password(captcha)
    session.captcha_attempts = 0
    session.captcha_refresh_count += 1
    session.captcha_verified = False

    db.commit()
    db.refresh(session)

    return captcha


def verify_editor_captcha(
    db: Session,
    registration_token: str,
    captcha: str,
) -> EditorRegistrationSession:
    session = db.scalar(
        select(EditorRegistrationSession).where(
            EditorRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Editor registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Editor registration session has expired."
        )

    if session.current_step < 2:
        raise ValueError(
            "OTP verification is required before CAPTCHA."
        )

    if session.captcha_code_hash is None:
        raise ValueError(
            "CAPTCHA has not been generated."
        )

    if session.captcha_attempts >= MAX_CAPTCHA_ATTEMPTS:
        raise ValueError(
            "Maximum CAPTCHA verification attempts reached."
        )

    session.captcha_attempts += 1

    if not verify_password(
        captcha,
        session.captcha_code_hash,
    ):
        db.commit()

        raise ValueError(
            "Invalid CAPTCHA."
        )

    session.captcha_verified = True
    session.current_step = 3

    db.commit()
    db.refresh(session)

    return session


def get_active_reviewers(
    db: Session,
    registration_token: str,
) -> list[User]:
    session = db.scalar(
        select(EditorRegistrationSession).where(
            EditorRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Editor registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Editor registration session has expired."
        )

    if not session.captcha_verified:
        raise ValueError(
            "CAPTCHA verification is required."
        )

    reviewers = db.scalars(
        select(User).where(
            User.company_id == session.company_id,
            User.role == UserRole.REVIEWER,
            User.status == UserStatus.ACTIVE,
        ).order_by(User.name)
    ).all()

    return list(reviewers)


def select_editor_reviewer(
    db: Session,
    registration_token: str,
    reviewer_id: int,
) -> EditorRegistrationSession:
    session = db.scalar(
        select(EditorRegistrationSession).where(
            EditorRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Editor registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Editor registration session has expired."
        )

    if not session.captcha_verified:
        raise ValueError(
            "CAPTCHA verification is required."
        )

    reviewer = db.scalar(
        select(User).where(
            User.id == reviewer_id,
            User.company_id == session.company_id,
            User.role == UserRole.REVIEWER,
            User.status == UserStatus.ACTIVE,
        )
    )

    if reviewer is None:
        raise ValueError(
            "Selected Reviewer is not available for this company."
        )

    session.selected_reviewer_id = reviewer.id
    session.current_step = 4

    db.commit()
    db.refresh(session)

    return session


def complete_editor_registration(
    db: Session,
    registration_token: str,
) -> tuple[User, AccessRequest]:
    session = db.scalar(
        select(EditorRegistrationSession).where(
            EditorRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Editor registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Editor registration session has expired."
        )

    if not session.captcha_verified:
        raise ValueError(
            "CAPTCHA verification is required."
        )

    if session.selected_reviewer_id is None:
        raise ValueError(
            "A Reviewer must be selected."
        )

    reviewer = db.scalar(
        select(User).where(
            User.id == session.selected_reviewer_id,
            User.company_id == session.company_id,
            User.role == UserRole.REVIEWER,
            User.status == UserStatus.ACTIVE,
        )
    )

    if reviewer is None:
        raise ValueError(
            "Selected Reviewer is no longer available."
        )

    existing_user = db.scalar(
        select(User).where(
            User.email == session.email
        )
    )

    if existing_user is not None:
        raise ValueError(
            "A user with this email already exists."
        )

    editor = User(
        company_id=session.company_id,
        name=session.name,
        email=session.email,
        password_hash=None,
        role=UserRole.EDITOR,
        status=UserStatus.PENDING,
        id_card_url=session.id_card_url,
        temporary_password_hash=None,
        temporary_password_expires_at=None,
        permanent_password_set=False,
    )

    db.add(editor)
    db.flush()

    access_request = AccessRequest(
        company_id=session.company_id,
        requester_id=editor.id,
        approver_id=reviewer.id,
        request_type=AccessRequestType.EDITOR_ACCESS,
        status=AccessRequestStatus.PENDING,
        expires_at=(
            utc_now()
            + timedelta(hours=24)
        ),
    )

    db.add(access_request)

    session.current_step = 5

    db.commit()

    db.refresh(editor)
    db.refresh(access_request)

    return editor, access_request