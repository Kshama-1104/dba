from pydantic import BaseModel, EmailStr, Field


class CompanyRegistrationRequest(BaseModel):
    company_name: str = Field(
        min_length=1,
        max_length=255,
    )

    company_description: str = Field(
        min_length=1,
        max_length=1200,
    )

    logo_url: str = Field(
        min_length=1,
        max_length=500,
    )

    company_type: str = Field(
        min_length=1,
        max_length=100,
    )

    industry: str = Field(
        min_length=1,
        max_length=150,
    )

    country_region: str = Field(
        min_length=1,
        max_length=150,
    )

    company_email: EmailStr


class CompanyConfigurationRequest(BaseModel):
    notification_email: EmailStr | None = None


class CompleteCompanyRegistrationRequest(BaseModel):
    registration_token: str = Field(
        min_length=1,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    confirm_password: str = Field(
        min_length=8,
        max_length=128,
    )