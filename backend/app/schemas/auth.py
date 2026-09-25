from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    company_id: int
    requires_password_setup: bool


class SetPermanentPasswordRequest(BaseModel):
    current_temporary_password: str
    new_password: str
    confirm_password: str