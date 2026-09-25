from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyAIProfileBase(BaseModel):
    products_services: str | None = None
    target_audience: str | None = None
    preferred_writing_style: str | None = None
    brand_voice: str | None = None
    marketing_goals: str | None = None
    company_guidelines: str | None = None
    upcoming_projects: str | None = None
    partner_companies: str | None = None
    achievements: str | None = None


class CompanyAIProfileCreate(CompanyAIProfileBase):
    pass


class CompanyAIProfileUpdate(CompanyAIProfileBase):
    pass


class CompanyAIProfileResponse(CompanyAIProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime