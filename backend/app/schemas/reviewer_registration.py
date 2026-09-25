from pydantic import BaseModel, EmailStr, Field


class ReviewerRegistrationRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )

    email: EmailStr

    id_card_url: str = Field(
        min_length=1,
        max_length=500,
    )


class ReviewerOTPVerificationRequest(BaseModel):
    registration_token: str = Field(
        min_length=1,
    )

    otp: str = Field(
        min_length=4,
        max_length=10,
    )


class ReviewerCAPTCHAVerificationRequest(BaseModel):
    registration_token: str = Field(
        min_length=1,
    )

    captcha: str = Field(
        min_length=1,
        max_length=20,
    )