import hashlib
import secrets


OTP_LENGTH = 6


def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    """Hash an OTP before storing it."""
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def verify_otp(otp: str, hashed_otp: str) -> bool:
    """Verify an entered OTP against its stored hash."""
    return secrets.compare_digest(
        hash_otp(otp),
        hashed_otp,
    )