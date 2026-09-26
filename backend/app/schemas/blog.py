from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.blog import BlogStatus


class BlogDraftSection(BaseModel):
    heading: str = Field(..., min_length=1)
    level: int = Field(default=2, ge=2, le=3)
    content: str = Field(default="")


class StructuredBlogDraft(BaseModel):
    seo_title: str = Field(default="")
    meta_description: str = Field(default="")
    primary_keyword: str = Field(default="")
    h1_title: str = Field(..., min_length=1)
    introduction: str = Field(default="")
    sections: List[BlogDraftSection] = Field(default_factory=list)
    conclusion: str = Field(default="")
    call_to_action: str = Field(default="")


class BlogPlanSection(BaseModel):
    heading: str = Field(..., min_length=1)
    key_points: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    memory_refs: List[str] = Field(default_factory=list)


class BlogPlan(BaseModel):
    title: str = Field(..., min_length=1)
    narrative_angle: str = Field(default="")
    target_audience: str = Field(default="")
    sections: List[BlogPlanSection] = Field(default_factory=list)
    estimated_word_count: int = Field(default=800)


class QualityEvaluationResult(BaseModel):
    passed: bool
    issues: List[str] = Field(default_factory=list)
    targeted_instructions: Optional[str] = None


class BlogGenerateRequest(BaseModel):
    topic_candidate_id: int
    editor_instruction: Optional[str] = None


class BlogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    topic_candidate_id: int
    created_by_user_id: Optional[int] = None
    title: str
    slug: Optional[str] = None
    primary_keyword: Optional[str] = None
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    status: BlogStatus
    format_version: Optional[int] = None
    generation_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class BlogDetailResponse(BlogResponse):
    content_json: Dict[str, Any]
    content_markdown: str


class BlogSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    topic_candidate_id: int
    title: str
    primary_keyword: Optional[str] = None
    status: BlogStatus
    created_at: datetime
    updated_at: datetime


class ValidationFinding(BaseModel):
    rule: str
    message: str
    field: Optional[str] = None
    severity: str = "error"  # "error" | "warning"
    details: Optional[Dict[str, Any]] = None


class SeoValidationReport(BaseModel):
    seo_title_valid: bool
    seo_title_length: int
    meta_description_valid: bool
    meta_description_length: int
    primary_keyword: Optional[str] = None
    keyword_in_seo_title: bool
    keyword_in_introduction: bool
    keyword_in_h2: bool
    slug_valid: bool
    slug_issues: List[str] = Field(default_factory=list)
    keyword_stuffing_warning: bool
    keyword_density: Optional[float] = None
    findings: List[ValidationFinding] = Field(default_factory=list)


class FormatValidationReport(BaseModel):
    baseline_sections_valid: bool
    h1_title_valid: bool
    introduction_valid: bool
    conclusion_valid: bool
    sections_valid: bool
    heading_hierarchy_valid: bool
    duplicate_headings: List[str] = Field(default_factory=list)
    company_format_checked: bool
    company_format_version: Optional[int] = None
    company_sections_valid: bool
    missing_company_sections: List[str] = Field(default_factory=list)
    findings: List[ValidationFinding] = Field(default_factory=list)


class BlogValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    blog_id: int
    company_id: int
    passed: bool
    errors: List[ValidationFinding] = Field(default_factory=list)
    warnings: List[ValidationFinding] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    seo_report: SeoValidationReport
    format_report: FormatValidationReport
    validated_at: datetime

