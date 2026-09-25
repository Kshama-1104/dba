from pydantic import BaseModel, EmailStr, Field


class EditorRegistrationRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )

    email: EmailStr

    id_card_url: str = Field(
        min_length=1,
        max_length=500,
    )


class EditorOTPVerificationRequest(BaseModel):
    registration_token: str = Field(
        min_length=1,
    )

    otp: str = Field(
        min_length=4,
        max_length=10,
    )


class EditorCAPTCHAVerificationRequest(BaseModel):
    registration_token: str = Field(
        min_length=1,
    )

    captcha: str = Field(
        min_length=1,
        max_length=20,
    )


class EditorReviewerSelectionRequest(BaseModel):
    registration_token: str = Field(
        min_length=1,
    )

    reviewer_id: int


class EditorRegistrationCompleteRequest(BaseModel):
    registration_token: str = Field(
        min_length=1,
    )