from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class WordPressConnectRequest(BaseModel):
    site_url: str = Field(..., min_length=1, max_length=500, description="Base WordPress site URL")
    username: str = Field(..., min_length=1, max_length=255, description="WordPress username")
    application_password: str = Field(
        ..., min_length=1, max_length=255, description="WordPress Application Password"
    )
    default_post_status: str = Field(
        default="publish",
        pattern=r"^(publish|draft)$",
        description="Default status for created posts ('publish' or 'draft')",
    )

    @field_validator("site_url")
    @classmethod
    def validate_site_url(cls, v: str) -> str:
        s = v.strip().rstrip("/")
        if not s.startswith("http://") and not s.startswith("https://"):
            raise ValueError("site_url must start with https:// (or http:// in dev)")
        return s

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("username cannot be whitespace only")
        return s

    @field_validator("application_password")
    @classmethod
    def validate_application_password(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("application_password cannot be whitespace only")
        return s


class WordPressUpdateRequest(BaseModel):
    site_url: Optional[str] = Field(None, min_length=1, max_length=500)
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    application_password: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, pattern=r"^(ACTIVE|INACTIVE)$")
    default_post_status: Optional[str] = Field(None, pattern=r"^(publish|draft)$")

    @field_validator("site_url")
    @classmethod
    def validate_site_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip().rstrip("/")
            if not s.startswith("http://") and not s.startswith("https://"):
                raise ValueError("site_url must start with https:// (or http:// in dev)")
            return s
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("username cannot be whitespace only")
            return s
        return v

    @field_validator("application_password")
    @classmethod
    def validate_application_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("application_password cannot be whitespace only")
            return s
        return v


class WordPressConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    site_url: str
    username: str
    status: str
    default_post_status: str
    masked_credential: str = "••••••••"
    last_tested_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WordPressTestResponse(BaseModel):
    success: bool
    site_url: str
    authenticated_user: Optional[str] = None
    can_publish: Optional[bool] = None
    error_message: Optional[str] = None
