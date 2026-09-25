from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccessRequestCreate(BaseModel):
    approver_id: int


class AccessRequestResponse(BaseModel):
    id: int
    company_id: int
    requester_id: int
    approver_id: int
    request_type: str
    status: str
    expires_at: datetime
    responded_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class AccessRequestDecision(BaseModel):
    decision: str