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
from backend.app.models.reviewer_registration_session import (
    ReviewerRegistrationSession,
)
from backend.app.models.user import User, UserRole, UserStatus


REGISTRATION_SESSION_HOURS = 2

OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 3
MAX_OTP_RESENDS = 3

MAX_CAPTCHA_ATTEMPTS = 3
MAX_CAPTCHA_REFRESHES = 2


def utc_now() -> datetime:
    """
    Return current UTC time as a timezone-naive datetime.

    The current database DateTime columns use timezone-naive
    timestamps, so we keep the same representation here.
    """
    return datetime.utcnow()


def generate_registration_token() -> str:
    """Generate a secure token for the reviewer registration session."""
    return secrets.token_urlsafe(32)


def generate_otp() -> str:
    """Generate a 6-digit OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_captcha(length: int = 6) -> str:
    """Generate a simple alphanumeric CAPTCHA value."""
    characters = string.ascii_uppercase + string.digits

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def extract_email_domain(email: str) -> str:
    """
    Extract the domain from an email address.

    Example:
        person@nexacore.com
        -> nexacore.com
    """
    return email.strip().lower().split("@")[-1]


def find_company_by_email_domain(
    db: Session,
    email: str,
) -> Company | None:
    """
    Find the company whose registered company email
    uses the same domain as the reviewer email.
    """

    reviewer_domain = extract_email_domain(email)

    companies = db.scalars(
        select(Company)
    ).all()

    matching_companies = []

    for company in companies:
        company_domain = extract_email_domain(
            company.company_email
        )

        if company_domain == reviewer_domain:
            matching_companies.append(company)

    if len(matching_companies) == 1:
        return matching_companies[0]

    # Do not guess if the domain belongs to multiple companies.
    return None


def create_reviewer_registration_session(
    db: Session,
    name: str,
    email: str,
    id_card_url: str,
) -> ReviewerRegistrationSession:
    """
    Create the first-stage reviewer registration session.

    The reviewer is NOT created as an active user yet.

    The reviewer must first:
        1. Verify OTP
        2. Verify CAPTCHA
        3. Send access request to Company Admin
    """

    email = email.strip().lower()

    # ---------------------------------------------------------
    # 1. Identify company from the company email domain
    # ---------------------------------------------------------

    company = find_company_by_email_domain(
        db=db,
        email=email,
    )

    if company is None:
        raise ValueError(
            "No unique company was found for this email domain."
        )

    # ---------------------------------------------------------
    # 2. Check whether this email is already registered
    # ---------------------------------------------------------

    existing_user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if existing_user is not None:
        raise ValueError(
            "A user with this email already exists."
        )

    # ---------------------------------------------------------
    # 3. Prevent duplicate active registration sessions
    # ---------------------------------------------------------

    existing_session = db.scalar(
        select(ReviewerRegistrationSession).where(
            ReviewerRegistrationSession.email == email,
            ReviewerRegistrationSession.expires_at > utc_now(),
        )
    )

    if existing_session is not None:
        raise ValueError(
            "An active reviewer registration session already exists."
        )

    # ---------------------------------------------------------
    # 4. Create registration session
    # ---------------------------------------------------------

    session = ReviewerRegistrationSession(
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


def generate_reviewer_otp(
    db: Session,
    registration_token: str,
) -> str:
    """
    Generate a reviewer OTP.

    OTP rules:
        - 10 minute expiry
        - maximum 3 OTP resends
    """

    session = db.scalar(
        select(ReviewerRegistrationSession).where(
            ReviewerRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Reviewer registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Reviewer registration session has expired."
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


def verify_reviewer_otp(
    db: Session,
    registration_token: str,
    otp: str,
) -> ReviewerRegistrationSession:
    """Verify the reviewer OTP."""

    session = db.scalar(
        select(ReviewerRegistrationSession).where(
            ReviewerRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Reviewer registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Reviewer registration session has expired."
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


def generate_reviewer_captcha(
    db: Session,
    registration_token: str,
) -> str:
    """
    Generate CAPTCHA for reviewer registration.

    CAPTCHA rules:
        - maximum 2 refreshes
        - maximum 3 verification attempts
    """

    session = db.scalar(
        select(ReviewerRegistrationSession).where(
            ReviewerRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Reviewer registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Reviewer registration session has expired."
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


def verify_reviewer_captcha(
    db: Session,
    registration_token: str,
    captcha: str,
) -> ReviewerRegistrationSession:
    """Verify reviewer CAPTCHA."""

    session = db.scalar(
        select(ReviewerRegistrationSession).where(
            ReviewerRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Reviewer registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Reviewer registration session has expired."
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


def complete_reviewer_registration(
    db: Session,
    registration_token: str,
) -> tuple[User, AccessRequest]:
    """
    Complete reviewer registration.

    At this point:
        - OTP must be verified
        - CAPTCHA must be verified

    The reviewer is created as PENDING.

    An access request is then created for the
    Company's active Company Admin.
    """

    session = db.scalar(
        select(ReviewerRegistrationSession).where(
            ReviewerRegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError(
            "Reviewer registration session not found."
        )

    if session.expires_at <= utc_now():
        raise ValueError(
            "Reviewer registration session has expired."
        )

    if not session.captcha_verified:
        raise ValueError(
            "CAPTCHA verification is required."
        )

    if session.current_step != 3:
        raise ValueError(
            "Reviewer registration is not ready to be completed."
        )

    # ---------------------------------------------------------
    # Find company admin
    # ---------------------------------------------------------

    company_admin = db.scalar(
        select(User).where(
            User.company_id == session.company_id,
            User.role == UserRole.COMPANY_ADMIN,
            User.status == UserStatus.ACTIVE,
        )
    )

    if company_admin is None:
        raise ValueError(
            "No active Company Admin is available."
        )

    # ---------------------------------------------------------
    # Re-check duplicate email
    # ---------------------------------------------------------

    existing_user = db.scalar(
        select(User).where(
            User.email == session.email
        )
    )

    if existing_user is not None:
        raise ValueError(
            "A user with this email already exists."
        )

    # ---------------------------------------------------------
    # Create pending reviewer
    # ---------------------------------------------------------

    reviewer = User(
        company_id=session.company_id,
        name=session.name,
        email=session.email,
        password_hash=None,
        role=UserRole.REVIEWER,
        status=UserStatus.PENDING,
        id_card_url=session.id_card_url,
        temporary_password_hash=None,
        temporary_password_expires_at=None,
        permanent_password_set=False,
    )

    db.add(reviewer)
    db.flush()

    # ---------------------------------------------------------
    # Create Reviewer → Company Admin access request
    # ---------------------------------------------------------

    access_request = AccessRequest(
        company_id=session.company_id,
        requester_id=reviewer.id,
        approver_id=company_admin.id,
        request_type=AccessRequestType.REVIEWER_ACCESS,
        status=AccessRequestStatus.PENDING,
        expires_at=(
            utc_now()
            + timedelta(hours=24)
        ),
    )

    db.add(access_request)

    # ---------------------------------------------------------
    # Mark registration session completed
    # ---------------------------------------------------------

    session.current_step = 4

    db.commit()

    db.refresh(reviewer)
    db.refresh(access_request)

    return reviewer, access_request