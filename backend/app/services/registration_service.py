import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.company import Company
from backend.app.models.registration_session import RegistrationSession
from backend.app.schemas.registration import CompanyRegistrationRequest
from backend.app.services.captcha_service import (
    generate_captcha,
    hash_captcha,
    verify_captcha,
)
from backend.app.services.otp_service import (
    generate_otp,
    hash_otp,
    verify_otp,
)


REGISTRATION_SESSION_HOURS = 2
OTP_EXPIRY_MINUTES = 10

MAX_OTP_ATTEMPTS = 3
MAX_OTP_RESENDS = 3

MAX_CAPTCHA_ATTEMPTS = 3
MAX_CAPTCHA_REFRESHES = 2


def utc_now() -> datetime:
    """
    Return the current UTC time as a timezone-naive datetime.

    Our current PostgreSQL DateTime columns are timezone-naive,
    so all registration timestamps use the same representation.
    """
    return datetime.utcnow()


def create_registration_session(
    db: Session,
    request: CompanyRegistrationRequest,
) -> RegistrationSession:

    existing_company = db.scalar(
        select(Company).where(
            Company.company_email == request.company_email
        )
    )

    if existing_company is not None:
        raise ValueError(
            "A company account already exists with this email."
        )

    existing_session = db.scalar(
        select(RegistrationSession).where(
            RegistrationSession.company_email == request.company_email,
            RegistrationSession.expires_at > utc_now(),
        )
    )

    if existing_session is not None:
        raise ValueError(
            "An active registration session already exists for this email."
        )

    registration_token = secrets.token_urlsafe(32)

    session = RegistrationSession(
        registration_token=registration_token,
        company_name=request.company_name,
        company_description=request.company_description,
        logo_url=request.logo_url,
        company_type=request.company_type,
        industry=request.industry,
        country_region=request.country_region,
        company_email=str(request.company_email),
        expires_at=utc_now()
        + timedelta(hours=REGISTRATION_SESSION_HOURS),
        current_step=1,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def generate_registration_otp(
    db: Session,
    registration_token: str,
) -> str:

    session = db.scalar(
        select(RegistrationSession).where(
            RegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError("Registration session not found.")

    if session.expires_at <= utc_now():
        raise ValueError("Registration session has expired.")

    # Maximum number of OTP resends.
    if session.otp_resend_count >= MAX_OTP_RESENDS:
        raise ValueError(
            "Maximum OTP resend limit reached. Please restart registration."
        )

    otp = generate_otp()

    session.otp_code_hash = hash_otp(otp)

    session.otp_expires_at = (
        utc_now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    )

    session.otp_attempts = 0
    session.otp_resend_count += 1
    session.current_step = 2

    db.commit()

    return otp


def verify_registration_otp(
    db: Session,
    registration_token: str,
    otp: str,
) -> bool:

    session = db.scalar(
        select(RegistrationSession).where(
            RegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError("Registration session not found.")

    if session.expires_at <= utc_now():
        raise ValueError("Registration session has expired.")

    if session.otp_code_hash is None:
        raise ValueError("No OTP has been generated.")

    if session.otp_expires_at is None:
        raise ValueError("OTP expiry information is missing.")

    if session.otp_expires_at <= utc_now():
        raise ValueError("OTP has expired.")

    if session.otp_attempts >= MAX_OTP_ATTEMPTS:
        raise ValueError(
            "Maximum OTP attempts reached. Please restart registration."
        )

    session.otp_attempts += 1

    if not verify_otp(
        otp,
        session.otp_code_hash,
    ):
        db.commit()
        return False

    session.captcha_verified = False
    session.current_step = 2

    db.commit()

    return True


def generate_registration_captcha(
    db: Session,
    registration_token: str,
) -> str:

    session = db.scalar(
        select(RegistrationSession).where(
            RegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError("Registration session not found.")

    if session.expires_at <= utc_now():
        raise ValueError("Registration session has expired.")

    if session.otp_code_hash is None:
        raise ValueError(
            "OTP verification is required first."
        )

    if session.current_step != 2:
        raise ValueError(
            "Registration is not currently at the CAPTCHA stage."
        )

    # Allow the initial CAPTCHA plus limited refreshes.
    if session.captcha_refresh_count >= MAX_CAPTCHA_REFRESHES:
        raise ValueError(
            "Maximum CAPTCHA refresh limit reached. "
            "Please restart registration."
        )

    captcha = generate_captcha()

    session.captcha_code_hash = hash_captcha(captcha)
    session.captcha_attempts = 0
    session.captcha_verified = False
    session.captcha_refresh_count += 1

    db.commit()

    return captcha


def verify_registration_captcha(
    db: Session,
    registration_token: str,
    captcha: str,
) -> bool:

    session = db.scalar(
        select(RegistrationSession).where(
            RegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError("Registration session not found.")

    if session.expires_at <= utc_now():
        raise ValueError("Registration session has expired.")

    if session.captcha_code_hash is None:
        raise ValueError(
            "No CAPTCHA has been generated."
        )

    if session.captcha_attempts >= MAX_CAPTCHA_ATTEMPTS:
        raise ValueError(
            "Maximum CAPTCHA attempts reached. "
            "Please restart registration."
        )

    session.captcha_attempts += 1

    if not verify_captcha(
        captcha,
        session.captcha_code_hash,
    ):
        db.commit()
        return False

    session.captcha_verified = True
    session.current_step = 3

    db.commit()

    return True

def complete_company_registration(
    db: Session,
    registration_token: str,
    password: str,
    confirm_password: str,
) -> Company:

    if password != confirm_password:
        raise ValueError("Passwords do not match.")

    session = db.scalar(
        select(RegistrationSession).where(
            RegistrationSession.registration_token
            == registration_token
        )
    )

    if session is None:
        raise ValueError("Registration session not found.")

    if session.expires_at <= utc_now():
        raise ValueError("Registration session has expired.")

    if not session.captcha_verified:
        raise ValueError(
            "CAPTCHA verification is required before creating the account."
        )

    if session.current_step != 3:
        raise ValueError(
            "Registration is not ready for account creation."
        )

    existing_company = db.scalar(
        select(Company).where(
            Company.company_email == session.company_email
        )
    )

    if existing_company is not None:
        raise ValueError(
            "A company account already exists with this email."
        )

    from backend.app.models.company_settings import CompanySettings
    from backend.app.models.user import User, UserRole, UserStatus
    from backend.app.core.security import hash_password

    company = Company(
        name=session.company_name,
        description=session.company_description,
        logo_url=session.logo_url,
        company_type=session.company_type,
        industry=session.industry,
        country_region=session.country_region,
        company_email=session.company_email,
        notification_email=session.notification_email,
    )

    db.add(company)
    db.flush()

    admin_user = User(
        company_id=company.id,
        name=session.company_name,
        email=session.company_email,
        password_hash=hash_password(password),
        role=UserRole.COMPANY_ADMIN,
        status=UserStatus.ACTIVE,
        permanent_password_set=True,
    )

    db.add(admin_user)

    company_settings = CompanySettings(
        company_id=company.id,
        notification_email=session.notification_email,
        blog_generation_enabled=True,
        publishing_enabled=True,
    )

    db.add(company_settings)

    # Mark the registration session as completed.
    session.current_step = 4

    db.commit()
    db.refresh(company)

    return company