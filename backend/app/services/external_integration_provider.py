"""
EXTERNAL INTEGRATION PROVIDER ABSTRACTION & PLATFORM ADAPTERS

Provides a vendor-neutral interface for connecting, validating, fetching, and normalizing
external company social & web data.

ADAPTER IMPLEMENTATION STATUS:
- MockSocialIntegrationAdapter: Fully implemented & deterministic for tests/CI.
- LinkedInIntegrationAdapter: Adapter stubbed; live verification marked PENDING.
- InstagramIntegrationAdapter: Adapter stubbed; live verification marked PENDING.
- TwitterXIntegrationAdapter: Adapter stubbed; live verification marked PENDING.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from typing import Any, Dict, List, Optional

from backend.app.schemas.external_integration import IntegrationPlatform


class IntegrationProviderError(Exception):
    """Base exception for external integration provider errors."""
    pass


class IntegrationAuthError(IntegrationProviderError):
    """Raised when integration credentials fail authentication or are expired."""
    pass


@dataclass
class RawExternalPost:
    """Raw payload returned by an external connector."""
    external_id: str
    content: str
    author: Optional[str] = None
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedInsight:
    """Normalized, platform-agnostic insight ready for storage and retrieval."""
    platform: str
    external_id: str
    author: Optional[str]
    source_url: Optional[str]
    content: str
    content_hash: str
    published_at: Optional[datetime]
    metadata_payload: Dict[str, Any] = field(default_factory=dict)


class ExternalIntegrationProvider(ABC):
    """Abstract interface for external social and data connectors."""

    @property
    @abstractmethod
    def platform(self) -> IntegrationPlatform:
        pass

    @property
    @abstractmethod
    def is_live_supported(self) -> bool:
        pass

    @abstractmethod
    def validate_connection(self, credentials: Dict[str, Any]) -> bool:
        """Validate connection credentials against the remote or mock service."""
        pass

    @abstractmethod
    def fetch_recent_posts(
        self,
        credentials: Dict[str, Any],
        since: Optional[datetime] = None,
    ) -> List[RawExternalPost]:
        """Fetch recent publications/posts from the connected account."""
        pass

    def normalize(self, raw: RawExternalPost) -> NormalizedInsight:
        """
        Normalize a raw post into standard NormalizedInsight with deterministic SHA-256 hash.
        SECURITY: Content is stored as raw data, never executed.
        """
        clean_content = (raw.content or "").strip()
        # Compute SHA-256 content hash for idempotent deduplication
        hash_input = f"{self.platform.value}:{raw.external_id}:{clean_content}"
        content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        return NormalizedInsight(
            platform=self.platform.value,
            external_id=str(raw.external_id).strip(),
            author=(raw.author or "").strip() or None,
            source_url=(raw.source_url or "").strip() or None,
            content=clean_content,
            content_hash=content_hash,
            published_at=raw.published_at or datetime.utcnow(),
            metadata_payload=raw.raw_metadata,
        )


class MockSocialIntegrationAdapter(ExternalIntegrationProvider):
    """
    Deterministic mock adapter for unit tests, offline development, and CI.
    Supports injecting custom mock posts or simulating failure scenarios.
    """

    def __init__(
        self,
        platform: IntegrationPlatform = IntegrationPlatform.LINKEDIN,
        mock_posts: Optional[List[RawExternalPost]] = None,
        should_fail_auth: bool = False,
        should_fail_fetch: bool = False,
    ):
        self._platform = platform
        self._mock_posts = mock_posts if mock_posts is not None else []
        self._should_fail_auth = should_fail_auth
        self._should_fail_fetch = should_fail_fetch

    @property
    def platform(self) -> IntegrationPlatform:
        return self._platform

    @property
    def is_live_supported(self) -> bool:
        return False

    def set_mock_posts(self, posts: List[RawExternalPost]) -> None:
        self._mock_posts = posts

    def validate_connection(self, credentials: Dict[str, Any]) -> bool:
        if self._should_fail_auth:
            raise IntegrationAuthError("Mock authentication failure: invalid credentials.")
        # Require at least one credential key
        if not credentials:
            raise IntegrationAuthError("Mock authentication failure: empty credentials.")
        return True

    def fetch_recent_posts(
        self,
        credentials: Dict[str, Any],
        since: Optional[datetime] = None,
    ) -> List[RawExternalPost]:
        if self._should_fail_fetch:
            raise IntegrationProviderError("Mock fetch failure: simulated remote API timeout.")
        self.validate_connection(credentials)

        if not self._mock_posts:
            # Default seeded sample post
            return [
                RawExternalPost(
                    external_id="mock-post-101",
                    content="Excited to announce our company's new AI safety and quality milestone!",
                    author="Company Updates",
                    source_url="https://mock-social.example.com/posts/101",
                    published_at=datetime.utcnow(),
                    raw_metadata={"engagement_score": 95, "tags": ["AI", "Safety"]},
                )
            ]

        results = []
        for post in self._mock_posts:
            if since and post.published_at and post.published_at < since:
                continue
            results.append(post)
        return results


class LinkedInIntegrationAdapter(ExternalIntegrationProvider):
    """Production adapter for LinkedIn Pages API (Status: PENDING live credentials)."""

    @property
    def platform(self) -> IntegrationPlatform:
        return IntegrationPlatform.LINKEDIN

    @property
    def is_live_supported(self) -> bool:
        return False

    def validate_connection(self, credentials: Dict[str, Any]) -> bool:
        token = credentials.get("access_token") or credentials.get("api_key")
        if not token:
            raise IntegrationAuthError("LinkedIn requires a valid OAuth 2.0 access_token.")
        # Live external API verification is intentionally deferred
        raise IntegrationProviderError(
            "LinkedIn live integration requires enterprise app approval and active OAuth token. Live verification is PENDING."
        )

    def fetch_recent_posts(
        self,
        credentials: Dict[str, Any],
        since: Optional[datetime] = None,
    ) -> List[RawExternalPost]:
        self.validate_connection(credentials)
        return []


class InstagramIntegrationAdapter(ExternalIntegrationProvider):
    """Production adapter for Instagram Graph API (Status: PENDING live credentials)."""

    @property
    def platform(self) -> IntegrationPlatform:
        return IntegrationPlatform.INSTAGRAM

    @property
    def is_live_supported(self) -> bool:
        return False

    def validate_connection(self, credentials: Dict[str, Any]) -> bool:
        token = credentials.get("access_token") or credentials.get("api_key")
        if not token:
            raise IntegrationAuthError("Instagram requires a valid Meta Graph API access_token.")
        raise IntegrationProviderError(
            "Instagram live integration requires Meta Developer credentials and Page access. Live verification is PENDING."
        )

    def fetch_recent_posts(
        self,
        credentials: Dict[str, Any],
        since: Optional[datetime] = None,
    ) -> List[RawExternalPost]:
        self.validate_connection(credentials)
        return []


class TwitterXIntegrationAdapter(ExternalIntegrationProvider):
    """Production adapter for X/Twitter API v2 (Status: PENDING live credentials)."""

    @property
    def platform(self) -> IntegrationPlatform:
        return IntegrationPlatform.TWITTER_X

    @property
    def is_live_supported(self) -> bool:
        return False

    def validate_connection(self, credentials: Dict[str, Any]) -> bool:
        token = credentials.get("access_token") or credentials.get("api_key")
        if not token:
            raise IntegrationAuthError("X/Twitter requires a valid Bearer token or API key.")
        raise IntegrationProviderError(
            "X/Twitter live integration requires X Developer API v2 credentials. Live verification is PENDING."
        )

    def fetch_recent_posts(
        self,
        credentials: Dict[str, Any],
        since: Optional[datetime] = None,
    ) -> List[RawExternalPost]:
        self.validate_connection(credentials)
        return []


# Adapter registry & factory
_mock_override: Optional[ExternalIntegrationProvider] = None


def get_integration_adapter(platform: IntegrationPlatform | str) -> ExternalIntegrationProvider:
    """Factory returning the registered adapter for the specified platform."""
    global _mock_override
    if _mock_override is not None:
        return _mock_override

    plat_str = platform.value if isinstance(platform, IntegrationPlatform) else str(platform).lower()

    if plat_str == IntegrationPlatform.LINKEDIN.value:
        return LinkedInIntegrationAdapter()
    elif plat_str == IntegrationPlatform.INSTAGRAM.value:
        return InstagramIntegrationAdapter()
    elif plat_str == IntegrationPlatform.TWITTER_X.value:
        return TwitterXIntegrationAdapter()
    elif plat_str == IntegrationPlatform.GENERIC_WEB.value:
        return MockSocialIntegrationAdapter(platform=IntegrationPlatform.GENERIC_WEB)
    else:
        # Default fallback to mock adapter with requested platform
        return MockSocialIntegrationAdapter(platform=IntegrationPlatform(plat_str) if plat_str in [p.value for p in IntegrationPlatform] else IntegrationPlatform.LINKEDIN)


def set_mock_adapter(adapter: Optional[ExternalIntegrationProvider]) -> None:
    """Inject a mock adapter for test execution."""
    global _mock_override
    _mock_override = adapter
