import base64
from datetime import datetime, timezone
import logging
import re
from typing import Optional

from fastapi import HTTPException, status
import httpx
from sqlalchemy.orm import Session

from backend.app.core.credential_vault import (
    decrypt_credentials,
    encrypt_credentials,
    mask_credential_string,
)
from backend.app.core.ssrf_protection import (
    SSRFProtectionError,
    validate_destination_url,
)
from backend.app.models.wordpress_connection import (
    WordPressConnection,
    WordPressConnectionStatus,
)
from backend.app.schemas.wordpress import (
    WordPressConnectRequest,
    WordPressConnectionResponse,
    WordPressTestResponse,
    WordPressUpdateRequest,
)

logger = logging.getLogger(__name__)


def sanitize_error_message(msg: Optional[str]) -> Optional[str]:
    """Strip passwords, application passwords, bearer tokens, and secrets from error strings."""
    if not msg:
        return msg
    sanitized = re.sub(r'(bearer\s+)[A-Za-z0-9_\-\.]+', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
    sanitized = re.sub(r'(basic\s+)[A-Za-z0-9=+/]+', r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'(password=)[^\s&]+', r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'(application_password=)[^\s&]+', r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'(authorization:\s*)[^\r\n]+', r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
    return sanitized[:1000]


class WordPressService:
    @staticmethod
    def get_connection(db: Session, company_id: int) -> Optional[WordPressConnection]:
        """Fetch the WordPressConnection for a company (tenant-scoped)."""
        return (
            db.query(WordPressConnection)
            .filter(WordPressConnection.company_id == company_id)
            .first()
        )

    @classmethod
    def create_or_update_connection(
        cls,
        db: Session,
        company_id: int,
        user_id: int,
        request: WordPressConnectRequest,
    ) -> WordPressConnection:
        """Create or update a tenant's WordPress connection with encrypted credentials."""
        # 1. SSRF Validation
        try:
            validated_url = validate_destination_url(request.site_url)
        except SSRFProtectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid WordPress site URL: {str(exc)}",
            ) from exc

        # 2. Authenticated encryption of Application Password
        encrypted_blob = encrypt_credentials(
            {"application_password": request.application_password.strip()}
        )

        existing = cls.get_connection(db, company_id)
        now_utc = datetime.now(timezone.utc)

        if existing:
            existing.site_url = validated_url
            existing.username = request.username.strip()
            existing.encrypted_credential = encrypted_blob
            existing.status = WordPressConnectionStatus.ACTIVE.value
            existing.default_post_status = request.default_post_status
            existing.last_error = None
            existing.updated_at = now_utc
            db.commit()
            db.refresh(existing)
            return existing

        new_conn = WordPressConnection(
            company_id=company_id,
            site_url=validated_url,
            username=request.username.strip(),
            encrypted_credential=encrypted_blob,
            status=WordPressConnectionStatus.ACTIVE.value,
            default_post_status=request.default_post_status,
            created_by_user_id=user_id,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(new_conn)
        db.commit()
        db.refresh(new_conn)
        return new_conn

    @classmethod
    def update_connection(
        cls,
        db: Session,
        company_id: int,
        request: WordPressUpdateRequest,
    ) -> WordPressConnection:
        """Update existing WordPress connection or rotate password."""
        conn = cls.get_connection(db, company_id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WordPress connection not configured for this company.",
            )

        now_utc = datetime.now(timezone.utc)

        if request.site_url is not None:
            try:
                conn.site_url = validate_destination_url(request.site_url)
            except SSRFProtectionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid WordPress site URL: {str(exc)}",
                ) from exc

        if request.username is not None:
            conn.username = request.username.strip()

        if request.application_password is not None:
            conn.encrypted_credential = encrypt_credentials(
                {"application_password": request.application_password.strip()}
            )

        if request.status is not None:
            conn.status = request.status

        if request.default_post_status is not None:
            conn.default_post_status = request.default_post_status

        conn.updated_at = now_utc
        db.commit()
        db.refresh(conn)
        return conn

    @classmethod
    def delete_connection(cls, db: Session, company_id: int) -> None:
        """Physically delete WordPress connection and purge encrypted credentials."""
        conn = cls.get_connection(db, company_id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WordPress connection not configured for this company.",
            )
        db.delete(conn)
        db.commit()

    @classmethod
    async def test_connection(
        cls,
        db: Session,
        company_id: int,
        client: Optional[httpx.AsyncClient] = None,
    ) -> WordPressTestResponse:
        """Test reachability, authentication, and publication capabilities against WordPress."""
        conn = cls.get_connection(db, company_id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WordPress connection not configured for this company.",
            )

        # 1. Decrypt credentials in memory
        try:
            creds = decrypt_credentials(conn.encrypted_credential)
            app_pass = creds.get("application_password")
            if not app_pass:
                raise ValueError("Missing application password in decrypted vault payload.")
        except Exception as exc:
            return WordPressTestResponse(
                success=False,
                site_url=conn.site_url,
                error_message="Failed to decrypt connection credentials.",
            )

        # 2. SSRF Destination Validation
        try:
            validated_url = validate_destination_url(conn.site_url)
        except SSRFProtectionError as exc:
            return WordPressTestResponse(
                success=False,
                site_url=conn.site_url,
                error_message=f"SSRF validation blocked: {str(exc)}",
            )

        # 3. HTTP Call to /wp-json/wp/v2/users/me?context=edit
        test_endpoint = f"{validated_url}/wp-json/wp/v2/users/me?context=edit"
        auth_header = (conn.username, app_pass)

        now_utc = datetime.now(timezone.utc)
        timeout = httpx.Timeout(10.0, connect=5.0)

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=timeout, verify=True)
            should_close_client = True

        try:
            resp = await client.get(test_endpoint, auth=auth_header)
            
            # If context=edit returned 401/403, try context=view to distinguish auth vs capability
            if resp.status_code == 401:
                conn.last_tested_at = now_utc
                conn.last_error = "WordPress authentication failed: invalid username or Application Password."
                db.commit()
                return WordPressTestResponse(
                    success=False,
                    site_url=conn.site_url,
                    error_message=conn.last_error,
                )

            if resp.status_code == 404:
                conn.last_tested_at = now_utc
                conn.last_error = "WordPress REST API endpoint not found. Verify site_url and permalinks."
                db.commit()
                return WordPressTestResponse(
                    success=False,
                    site_url=conn.site_url,
                    error_message=conn.last_error,
                )

            if resp.status_code >= 400:
                sanitized_err = sanitize_error_message(f"HTTP {resp.status_code}: {resp.text[:200]}")
                conn.last_tested_at = now_utc
                conn.last_error = sanitized_err
                db.commit()
                return WordPressTestResponse(
                    success=False,
                    site_url=conn.site_url,
                    error_message=sanitized_err,
                )

            data = resp.json()
            user_name = data.get("name") or data.get("slug") or conn.username
            capabilities = data.get("capabilities") or {}
            roles = data.get("roles") or []

            # Check publication capabilities (publish_posts or edit_posts or author/editor/administrator)
            can_publish = (
                capabilities.get("publish_posts") is True
                or capabilities.get("edit_posts") is True
                or any(r in ("administrator", "editor", "author") for r in roles)
            )

            if not can_publish:
                err_msg = (
                    f"Authenticated as '{user_name}', but user lacks sufficient publishing capability "
                    "('publish_posts' or 'edit_posts')."
                )
                conn.last_tested_at = now_utc
                conn.last_error = err_msg
                db.commit()
                return WordPressTestResponse(
                    success=False,
                    site_url=conn.site_url,
                    authenticated_user=user_name,
                    can_publish=False,
                    error_message=err_msg,
                )

            conn.last_tested_at = now_utc
            conn.last_error = None
            db.commit()

            return WordPressTestResponse(
                success=True,
                site_url=conn.site_url,
                authenticated_user=user_name,
                can_publish=True,
            )

        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as exc:
            sanitized_err = sanitize_error_message(f"Connection timeout: {str(exc)}")
            conn.last_tested_at = now_utc
            conn.last_error = sanitized_err
            db.commit()
            return WordPressTestResponse(
                success=False,
                site_url=conn.site_url,
                error_message=sanitized_err,
            )
        except httpx.RequestError as exc:
            sanitized_err = sanitize_error_message(f"Network error: {str(exc)}")
            conn.last_tested_at = now_utc
            conn.last_error = sanitized_err
            db.commit()
            return WordPressTestResponse(
                success=False,
                site_url=conn.site_url,
                error_message=sanitized_err,
            )
        except Exception as exc:
            sanitized_err = sanitize_error_message(f"Unexpected connection error: {str(exc)}")
            conn.last_tested_at = now_utc
            conn.last_error = sanitized_err
            db.commit()
            return WordPressTestResponse(
                success=False,
                site_url=conn.site_url,
                error_message=sanitized_err,
            )
        finally:
            if should_close_client:
                await client.aclose()
