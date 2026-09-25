import hashlib
import secrets


CAPTCHA_LENGTH = 6


def generate_captcha() -> str:
    """
    Generate a secure 6-character CAPTCHA.
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    return "".join(
        secrets.choice(alphabet)
        for _ in range(CAPTCHA_LENGTH)
    )


def hash_captcha(captcha: str) -> str:
    """
    Hash a CAPTCHA before storing it.
    """
    return hashlib.sha256(
        captcha.upper().encode("utf-8")
    ).hexdigest()


def verify_captcha(
    captcha: str,
    hashed_captcha: str,
) -> bool:
    """
    Verify a CAPTCHA against its stored hash.
    """
    return secrets.compare_digest(
        hash_captcha(captcha),
        hashed_captcha,
    )