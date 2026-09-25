from pydantic import BaseModel, EmailStr


class CompanyDashboardCompany(BaseModel):
    id: int
    name: str
    description: str
    logo_url: str
    company_type: str
    industry: str
    country_region: str
    company_email: EmailStr
    notification_email: EmailStr | None = None


class CompanyDashboardUser(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str


class CompanyDashboardResponse(BaseModel):
    company: CompanyDashboardCompany
    user: CompanyDashboardUser