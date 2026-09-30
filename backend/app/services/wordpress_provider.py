from datetime import datetime, timedelta, timezone
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from backend.app.core.credential_vault import decrypt_credentials
from backend.app.core.ssrf_protection import (
    SSRFProtectionError,
    validate_destination_url,
)
from backend.app.models.wordpress_connection import (
    WordPressConnection,
    WordPressConnectionStatus,
    WordPressPublicationRecord,
    WordPressPublicationStatus,
)
from backend.app.services.publication_contract import (
    BasePublicationProvider,
    PublicationContract,
    PublicationResult,
)
from backend.app.services.wordpress_service import sanitize_error_message

logger = logging.getLogger(__name__)


def sanitize_html(raw_html: str) -> str:
    """Sanitize HTML content to strip dangerous tags (script, iframe, etc.), event handlers, and javascript: URIs."""
    if not raw_html:
        return ""
    # Strip script/iframe/style/embed/object tags and their contents
    cleaned = re.sub(
        r'<\s*(script|style|iframe|object|embed|applet|form|meta|link)[^>]*>.*?<\s*/\s*\1\s*>',
        '',
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Strip unclosed or self-closing dangerous tags
    cleaned = re.sub(
        r'<\s*(script|style|iframe|object|embed|applet|form|meta|link)[^>]*>',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )
    # Strip event handlers (e.g., onclick=..., onload=...)
    cleaned = re.sub(
        r'\s+on[a-zA-Z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )
    # Strip javascript: and data: URIs
    cleaned = re.sub(
        r'(href|src)\s*=\s*["\']\s*(javascript|data):[^"\']*["\']',
        r'\1="#"',
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def render_structured_draft_to_html(
    draft_dict: Dict[str, Any],
    fallback_markdown: str,
    idempotency_marker: str,
) -> str:
    """
    Transform approved structured draft into clean, sanitized WordPress HTML.
    Preserves exact semantics, sections, headings, conclusion, and CTA.
    Appends the deterministic idempotency marker comment.
    """
    html_parts: List[str] = []

    # 1. Introduction
    intro = draft_dict.get("introduction")
    if intro and str(intro).strip():
        html_parts.append(f'<p class="dailyblog-intro">{str(intro).strip()}</p>')

    # 2. Body Sections
    sections = draft_dict.get("sections")
    if isinstance(sections, list) and sections:
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            heading = sec.get("heading", "").strip()
            level = sec.get("level", 2)
            if level not in (2, 3):
                level = 2
            content = sec.get("content", "").strip()

            if heading:
                html_parts.append(f'<h{level}>{heading}</h{level}>')
            if content:
                # Wrap paragraphs
                paras = [p.strip() for p in content.split("\n\n") if p.strip()]
                for p in paras:
                    html_parts.append(f'<p>{p}</p>')

    # Fallback to markdown lines if sections was empty
    elif fallback_markdown and fallback_markdown.strip():
        # Simple line-by-line paragraph/heading conversion
        for line in fallback_markdown.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            if line_s.startswith("### "):
                html_parts.append(f'<h3>{line_s[4:].strip()}</h3>')
            elif line_s.startswith("## "):
                html_parts.append(f'<h2>{line_s[3:].strip()}</h2>')
            elif line_s.startswith("# "):
                # Skip H1 inside body
                continue
            else:
                html_parts.append(f'<p>{line_s}</p>')

    # 3. Conclusion
    conclusion = draft_dict.get("conclusion")
    if conclusion and str(conclusion).strip():
        html_parts.append('<h2>Conclusion</h2>')
        html_parts.append(f'<p>{str(conclusion).strip()}</p>')

    # 4. Call to Action
    cta = draft_dict.get("call_to_action")
    if cta and str(cta).strip():
        html_parts.append(f'<p class="dailyblog-cta"><strong>Call to Action:</strong> {str(cta).strip()}</p>')

    # 5. Append deterministic idempotency marker
    html_parts.append(f'\n{idempotency_marker}\n')

    raw_html = "\n".join(html_parts)

    clean_html = sanitize_html(raw_html)
    if idempotency_marker not in clean_html:
        clean_html = f"{clean_html.strip()}\n{idempotency_marker}\n"

    return clean_html



class WordPressPublicationProvider(BasePublicationProvider):
    """
    Production-grade WordPress Publication Provider.
    Implements BasePublicationProvider with atomic pre-POST claim, SSRF validation,
    deterministic remote idempotency recovery, and semantic content preservation.
    """

    def __init__(
        self,
        db: Session,
        client: Optional[httpx.AsyncClient] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        self.db = db
        self._client = client
        self.worker_id = worker_id or "wp_publisher_worker"

    async def publish(self, contract: PublicationContract) -> PublicationResult:
        now_utc = datetime.now(timezone.utc)

        # ── 1. Resolve Company Connection ─────────────────────────────────
        conn = (
            self.db.query(WordPressConnection)
            .filter(
                WordPressConnection.company_id == contract.company_id,
                WordPressConnection.status == WordPressConnectionStatus.ACTIVE.value,
            )
            .first()
        )
        if not conn:
            logger.warning(
                f"WordPress publication failed: connection not configured or inactive for company {contract.company_id}."
            )
            return PublicationResult(
                success=False,
                is_transient_error=False,
                error_code="WORDPRESS_NOT_CONFIGURED",
                error_message="WordPress connection is not configured or inactive for this company.",
            )

        # ── 2. Pre-POST Logical Publication Claim (Atomic Gate) ───────────
        record = (
            self.db.query(WordPressPublicationRecord)
            .filter(
                WordPressPublicationRecord.company_id == contract.company_id,
                WordPressPublicationRecord.publication_idempotency_key == contract.publication_idempotency_key,
            )
            .with_for_update()
            .first()
        )

        # Case B: Already SUCCEEDED -> Zero HTTP calls
        if record and record.status == WordPressPublicationStatus.SUCCEEDED.value:
            self.db.commit()
            return PublicationResult(
                success=True,
                external_reference=f"wp_post:{record.external_post_id}",
                published_url=record.external_url,
            )

        # Case C: IN_PROGRESS with Active Lease -> Concurrency rejection
        if (
            record
            and record.status == WordPressPublicationStatus.IN_PROGRESS.value
            and record.claim_lease_until
            and record.claim_lease_until > now_utc
        ):
            self.db.commit()
            return PublicationResult(
                success=False,
                is_transient_error=True,
                error_code="WP_PUBLICATION_IN_PROGRESS",
                error_message="Concurrent publication attempt currently in progress by another worker.",
            )

        # Case D: IN_PROGRESS with Expired Lease -> Steal Claim
        if record and record.status == WordPressPublicationStatus.IN_PROGRESS.value:
            record.claim_worker_id = self.worker_id
            record.claim_lease_until = now_utc + timedelta(minutes=3)
            record.last_job_id = contract.job_id
            record.updated_at = now_utc
            self.db.commit()

        # Case A: Record does not exist -> Create IN_PROGRESS Claim
        elif not record:
            record = WordPressPublicationRecord(
                company_id=contract.company_id,
                connection_id=conn.id,
                schedule_id=contract.schedule_id,
                last_job_id=contract.job_id,
                blog_id=contract.blog_id,
                revision_id=contract.revision_id,
                publication_idempotency_key=contract.publication_idempotency_key,
                status=WordPressPublicationStatus.IN_PROGRESS.value,
                claim_worker_id=self.worker_id,
                claim_lease_until=now_utc + timedelta(minutes=3),
                post_status=conn.default_post_status or "publish",
                target_site_url=conn.site_url,
                target_username=conn.username,
                created_at=now_utc,
                updated_at=now_utc,
            )
            self.db.add(record)
            self.db.commit()

        # ── 3. Decrypt Credentials & Validate SSRF ────────────────────────
        try:
            creds = decrypt_credentials(conn.encrypted_credential)
            app_pass = creds.get("application_password")
            if not app_pass:
                raise ValueError("Application password missing from decrypted vault.")
        except Exception as exc:
            self._mark_terminal_failure(record.id, "WP_CREDENTIAL_DECRYPTION_ERROR", str(exc))
            return PublicationResult(
                success=False,
                is_transient_error=False,
                error_code="WP_CREDENTIAL_DECRYPTION_ERROR",
                error_message="Failed to decrypt WordPress credentials.",
            )

        try:
            validated_url = validate_destination_url(conn.site_url)
        except SSRFProtectionError as exc:
            self._mark_terminal_failure(record.id, "SECURITY_SSRF_BLOCKED", str(exc))
            return PublicationResult(
                success=False,
                is_transient_error=False,
                error_code="SECURITY_SSRF_BLOCKED",
                error_message=f"SSRF validation blocked target WordPress URL: {str(exc)}",
            )

        # ── 4. Remote Idempotency Lookup (Check Before POST) ──────────────
        slug = (
            contract.content_json.get("slug")
            or re.sub(r"[^a-z0-9]+", "-", contract.title.lower()).strip("-")
            or f"blog-{contract.blog_id}"
        )
        marker = f"<!-- dailyblog-pub-key: {contract.publication_idempotency_key} -->"

        should_close_client = False
        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), verify=True)
            should_close_client = True

        auth = (conn.username, app_pass)

        try:
            # Query posts by slug
            lookup_endpoint = f"{validated_url}/wp-json/wp/v2/posts?slug={slug}&status=any"
            lookup_resp = await client.get(lookup_endpoint, auth=auth)

            if lookup_resp.status_code == 200:
                posts_data = lookup_resp.json()
                if isinstance(posts_data, list) and len(posts_data) > 0:
                    for post_item in posts_data:
                        raw_content = ""
                        if isinstance(post_item, dict):
                            raw_content = (
                                post_item.get("content", {}).get("raw", "")
                                or post_item.get("content", {}).get("rendered", "")
                            )
                        if marker in raw_content:
                            # Exact match discovered remotely!
                            post_id = str(post_item.get("id"))
                            post_url = post_item.get("link")
                            self._mark_success(record.id, post_id, post_url)
                            return PublicationResult(
                                success=True,
                                external_reference=f"wp_post:{post_id}",
                                published_url=post_url,
                            )
                    # A post with that slug exists, but none have our exact marker -> SLUG CONFLICT!
                    self._mark_terminal_failure(
                        record.id,
                        "WP_SLUG_CONFLICT",
                        f"Post with slug '{slug}' exists on WordPress without matching publication marker.",
                    )
                    return PublicationResult(
                        success=False,
                        is_transient_error=False,
                        error_code="WP_SLUG_CONFLICT",
                        error_message=f"Slug conflict: post with slug '{slug}' exists on WordPress.",
                    )

            # ── 5. Transform Content & Execute POST ─────────────────────────
            post_content = render_structured_draft_to_html(
                draft_dict=contract.content_json or {},
                fallback_markdown=contract.content_markdown or "",
                idempotency_marker=marker,
            )

            post_status = conn.default_post_status or "publish"
            post_payload = {
                "title": contract.title,
                "content": post_content,
                "slug": slug,
                "status": post_status,
            }
            # Add excerpt if meta_description exists
            meta_desc = contract.content_json.get("meta_description")
            if meta_desc and str(meta_desc).strip():
                post_payload["excerpt"] = str(meta_desc).strip()

            create_endpoint = f"{validated_url}/wp-json/wp/v2/posts"
            resp = await client.post(create_endpoint, json=post_payload, auth=auth)

            # ── 6. Parse Response & Classify Outcome ────────────────────────
            if resp.status_code in (200, 201):
                created_data = resp.json()
                post_id = str(created_data.get("id"))
                post_url = created_data.get("link")
                self._mark_success(record.id, post_id, post_url)
                return PublicationResult(
                    success=True,
                    external_reference=f"wp_post:{post_id}",
                    published_url=post_url,
                )

            # Handle 429 Rate Limiting
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                err_msg = "WordPress rate limited (HTTP 429)."
                if retry_after:
                    err_msg += f" Retry-After: {retry_after}s"
                self._mark_transient_error(record.id, "WP_RATE_LIMITED", err_msg)
                return PublicationResult(
                    success=False,
                    is_transient_error=True,
                    error_code="WP_RATE_LIMITED",
                    error_message=err_msg,
                )

            # Handle 401 / 403 (Terminal Auth / Permission Failures)
            if resp.status_code in (401, 403):
                err_code = "WP_AUTH_FAILED" if resp.status_code == 401 else "WP_FORBIDDEN"
                sanitized_err = sanitize_error_message(f"HTTP {resp.status_code}: {resp.text[:300]}")
                self._mark_terminal_failure(record.id, err_code, sanitized_err)
                return PublicationResult(
                    success=False,
                    is_transient_error=False,
                    error_code=err_code,
                    error_message=sanitized_err,
                )

            # Handle 400 / 422 (Terminal Payload Errors)
            if resp.status_code in (400, 422):
                sanitized_err = sanitize_error_message(f"HTTP {resp.status_code}: {resp.text[:300]}")
                self._mark_terminal_failure(record.id, "WP_INVALID_PAYLOAD", sanitized_err)
                return PublicationResult(
                    success=False,
                    is_transient_error=False,
                    error_code="WP_INVALID_PAYLOAD",
                    error_message=sanitized_err,
                )

            # Handle 404 (Terminal Endpoint Error)
            if resp.status_code == 404:
                sanitized_err = sanitize_error_message(f"HTTP 404: Endpoint not found on {validated_url}")
                self._mark_terminal_failure(record.id, "WP_NOT_FOUND", sanitized_err)
                return PublicationResult(
                    success=False,
                    is_transient_error=False,
                    error_code="WP_NOT_FOUND",
                    error_message=sanitized_err,
                )

            # 5xx Server Errors (Transient)
            if resp.status_code >= 500:
                sanitized_err = sanitize_error_message(f"HTTP {resp.status_code}: {resp.text[:300]}")
                self._mark_transient_error(record.id, "WP_SERVER_ERROR", sanitized_err)
                return PublicationResult(
                    success=False,
                    is_transient_error=True,
                    error_code="WP_SERVER_ERROR",
                    error_message=sanitized_err,
                )

            # Fallback for unexpected status codes
            sanitized_err = sanitize_error_message(f"HTTP {resp.status_code}: {resp.text[:300]}")
            self._mark_transient_error(record.id, "WP_HTTP_ERROR", sanitized_err)
            return PublicationResult(
                success=False,
                is_transient_error=True,
                error_code="WP_HTTP_ERROR",
                error_message=sanitized_err,
            )

        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as exc:
            sanitized_err = sanitize_error_message(f"Network timeout: {str(exc)}")
            self._mark_transient_error(record.id, "WP_NETWORK_TIMEOUT", sanitized_err)
            return PublicationResult(
                success=False,
                is_transient_error=True,
                error_code="WP_NETWORK_TIMEOUT",
                error_message=sanitized_err,
            )
        except httpx.RequestError as exc:
            sanitized_err = sanitize_error_message(f"Network connection error: {str(exc)}")
            self._mark_transient_error(record.id, "WP_CONNECTION_FAILURE", sanitized_err)
            return PublicationResult(
                success=False,
                is_transient_error=True,
                error_code="WP_CONNECTION_FAILURE",
                error_message=sanitized_err,
            )
        except Exception as exc:
            sanitized_err = sanitize_error_message(f"Unexpected publication error: {str(exc)}")
            self._mark_transient_error(record.id, "WP_UNEXPECTED_ERROR", sanitized_err)
            return PublicationResult(
                success=False,
                is_transient_error=True,
                error_code="WP_UNEXPECTED_ERROR",
                error_message=sanitized_err,
            )
        finally:
            if should_close_client:
                await client.aclose()

    def _mark_success(self, record_id: int, external_post_id: str, external_url: Optional[str]) -> None:
        """Mark logical publication record as SUCCEEDED."""
        now_utc = datetime.now(timezone.utc)
        rec = self.db.query(WordPressPublicationRecord).filter(WordPressPublicationRecord.id == record_id).first()
        if rec:
            rec.status = WordPressPublicationStatus.SUCCEEDED.value
            rec.external_post_id = external_post_id
            rec.external_url = external_url
            rec.published_at = now_utc
            rec.error_code = None
            rec.error_message = None
            rec.updated_at = now_utc
            self.db.commit()

    def _mark_terminal_failure(self, record_id: int, error_code: str, error_message: str) -> None:
        """Mark logical publication record as FAILED_TERMINAL."""
        now_utc = datetime.now(timezone.utc)
        rec = self.db.query(WordPressPublicationRecord).filter(WordPressPublicationRecord.id == record_id).first()
        if rec:
            rec.status = WordPressPublicationStatus.FAILED_TERMINAL.value
            rec.error_code = error_code
            rec.error_message = sanitize_error_message(error_message)
            rec.updated_at = now_utc
            self.db.commit()

    def _mark_transient_error(self, record_id: int, error_code: str, error_message: str) -> None:
        """Record transient failure details while keeping record for next attempt lease recovery."""
        now_utc = datetime.now(timezone.utc)
        rec = self.db.query(WordPressPublicationRecord).filter(WordPressPublicationRecord.id == record_id).first()
        if rec:
            rec.error_code = error_code
            rec.error_message = sanitize_error_message(error_message)
            rec.updated_at = now_utc
            self.db.commit()
