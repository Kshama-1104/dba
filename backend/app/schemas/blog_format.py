import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

MANDATORY_BASELINE_SECTIONS: list[str] = [
    "Title",
    "Introduction",
    "Headings",
    "Main Content",
    "Conclusion",
]


class BlogFormatDefinition(BaseModel):
    """
    Structured specification of the reusable Company Global Blog Format.
    Enforces the immutable Level 1 System Baseline requirements.
    """
    title_structure: str = Field(
        default="Compelling, brand-aligned H1 headline",
        description="Structural instructions for H1 title",
    )
    introduction_structure: str = Field(
        default="Hook, problem articulation, thesis statement",
        description="Structural instructions for introduction",
    )
    heading_structure: str = Field(
        default="Hierarchical H2 and H3 sections organizing core arguments",
        description="Structural instructions for H2/H3 headings",
    )
    main_content_structure: str = Field(
        default="Educational body sections, bullet points, data callouts",
        description="Structural instructions for main content body",
    )
    conclusion_structure: str = Field(
        default="Summary synthesis, closing thoughts, brand CTA",
        description="Structural instructions for conclusion",
    )
    call_to_action: str | None = Field(
        default=None,
        description="Closing brand call-to-action directive",
    )
    preferred_writing_style: str | None = Field(
        default=None,
        description="Tone and formatting style preference",
    )
    required_sections: list[str] = Field(
        default_factory=lambda: list(MANDATORY_BASELINE_SECTIONS),
        description="List of mandatory sections for future blog generation",
    )
    optional_sections: list[str] = Field(
        default_factory=list,
        description="List of optional or conditional sections (e.g. FAQ, Key Takeaways)",
    )
    seo_guidelines: dict[str, Any] | None = Field(
        default=None,
        description="Technical SEO formatting requirements",
    )
    custom_rules: list[str] = Field(
        default_factory=list,
        description="Additional company-specific editorial formatting rules",
    )

    @field_validator("required_sections")
    @classmethod
    def validate_baseline_sections(cls, v: list[str]) -> list[str]:
        if not v:
            return list(MANDATORY_BASELINE_SECTIONS)

        existing_lower = {s.strip().lower() for s in v}
        for baseline in MANDATORY_BASELINE_SECTIONS:
            if baseline.lower() not in existing_lower:
                raise ValueError(
                    f"Mandatory system baseline section '{baseline}' cannot be omitted from required_sections."
                )
        return v


class BlogFormatCreate(BaseModel):
    """
    Payload for creating or updating a Company Global Blog Format.
    Supports either a nested format_definition object or top-level specification attributes.
    """
    format_definition: BlogFormatDefinition | None = None
    title_structure: str | None = None
    introduction_structure: str | None = None
    heading_structure: str | None = None
    main_content_structure: str | None = None
    conclusion_structure: str | None = None
    call_to_action: str | None = None
    preferred_writing_style: str | None = None
    required_sections: list[str] | None = None
    optional_sections: list[str] | None = None
    seo_guidelines: dict[str, Any] | None = None
    custom_rules: list[str] | None = None

    @field_validator("required_sections")
    @classmethod
    def validate_baseline_sections(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        existing_lower = {s.strip().lower() for s in v}
        for baseline in MANDATORY_BASELINE_SECTIONS:
            if baseline.lower() not in existing_lower:
                raise ValueError(
                    f"Mandatory system baseline section '{baseline}' cannot be omitted from required_sections."
                )
        return v


class BlogFormatUpdate(BlogFormatCreate):
    pass


class BlogFormatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    version: int
    format_definition: BlogFormatDefinition
    is_active: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("format_definition", mode="before")
    @classmethod
    def parse_format_definition(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                pass
        return v


class BlogFormatListResponse(BaseModel):
    total_versions: int
    active_version: int | None
    formats: list[BlogFormatResponse]
