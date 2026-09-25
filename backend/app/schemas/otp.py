from pydantic import BaseModel, Field


class VerifyOTPRequest(BaseModel):
    registration_token: str = Field(min_length=1)
    otp: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )