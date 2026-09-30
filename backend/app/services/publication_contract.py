from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PublicationContract(BaseModel):
    job_id: int = Field(..., description="ID of the execution attempt job")
    schedule_id: int = Field(..., description="ID of the parent BlogSchedule")
    company_id: int = Field(..., description="Company/tenant ID")
    blog_id: int = Field(..., description="Blog ID")
    revision_id: int = Field(..., description="Pinned immutable BlogRevision ID")
    title: str = Field(..., description="Title from the pinned revision")
    content_markdown: str = Field(..., description="Markdown content from the pinned revision")
    content_json: Dict[str, Any] = Field(default_factory=dict, description="Structured content from pinned revision")
    attempt_number: int = Field(..., description="Execution attempt index (1, 2, 3...)")
    publication_idempotency_key: str = Field(..., description="Stable logical publication key across all retries")


class PublicationResult(BaseModel):
    success: bool
    is_transient_error: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    external_reference: Optional[str] = None
    published_url: Optional[str] = None


class BasePublicationProvider(ABC):
    @abstractmethod
    async def publish(self, contract: PublicationContract) -> PublicationResult:
        """Execute publication to external destination according to contract."""
        pass


class MockPublicationProvider(BasePublicationProvider):
    """Default provider used for Phase 10 validation and testing."""

    def __init__(self, default_success: bool = True):
        self.default_success = default_success
        self.invocations: list[PublicationContract] = []
        self.override_result: Optional[PublicationResult] = None

    async def publish(self, contract: PublicationContract) -> PublicationResult:
        self.invocations.append(contract)
        if self.override_result is not None:
            return self.override_result

        if self.default_success:
            return PublicationResult(
                success=True,
                external_reference=f"ext_ref_{contract.blog_id}_{contract.revision_id}",
                published_url=f"https://example.com/published/{contract.blog_id}",
            )
        else:
            return PublicationResult(
                success=False,
                is_transient_error=True,
                error_code="MOCK_TRANSIENT_FAILURE",
                error_message="Simulated temporary network failure",
            )
