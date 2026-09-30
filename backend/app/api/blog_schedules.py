"""
Blog Scheduling API — Phase 10

Endpoints for scheduling approved blog revisions, managing schedule lifecycle,
rescheduling, and cancellation.

RBAC:
    POST /blogs/{id}/schedules:       Company Admin, Editor
    GET  /blogs/{id}/schedules:       Company Admin, Editor, Reviewer
    GET  /schedules/{id}:             Company Admin, Editor, Reviewer
    POST /schedules/{id}/reschedule:  Company Admin, Editor
    POST /schedules/{id}/cancel:      Company Admin, Editor
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.schemas.blog_schedule import (
    BlogScheduleDetailResponse,
    BlogScheduleResponse,
    RescheduleRequest,
    ScheduleCancelRequest,
    ScheduleCreateRequest,
)
from backend.app.services.blog_schedule_service import BlogScheduleService

router = APIRouter(prefix="/api/v1", tags=["Blog Scheduling"])


@router.post(
    "/blogs/{blog_id}/schedules",
    response_model=BlogScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule an approved blog for publication",
)
def create_schedule(
    blog_id: int,
    request: ScheduleCreateRequest,
    current_user: User = Depends(require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)),
    db: Session = Depends(get_db),
):
    return BlogScheduleService.create_schedule(db, blog_id, current_user, request)


@router.get(
    "/blogs/{blog_id}/schedules",
    response_model=List[BlogScheduleResponse],
    status_code=status.HTTP_200_OK,
    summary="List all publication schedules for a blog",
)
def list_blog_schedules(
    blog_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    return BlogScheduleService.list_blog_schedules(db, blog_id, current_user)


@router.get(
    "/schedules/{schedule_id}",
    response_model=BlogScheduleDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get details of a publication schedule including attempts and audit events",
)
def get_schedule(
    schedule_id: int,
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR, UserRole.REVIEWER)
    ),
    db: Session = Depends(get_db),
):
    return BlogScheduleService.get_schedule(db, schedule_id, current_user)


@router.post(
    "/schedules/{schedule_id}/reschedule",
    response_model=BlogScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Reschedule a pending SCHEDULED publication",
)
def reschedule(
    schedule_id: int,
    request: RescheduleRequest,
    current_user: User = Depends(require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)),
    db: Session = Depends(get_db),
):
    return BlogScheduleService.reschedule(db, schedule_id, current_user, request)


@router.post(
    "/schedules/{schedule_id}/cancel",
    response_model=BlogScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a SCHEDULED or QUEUED publication schedule",
)
def cancel_schedule(
    schedule_id: int,
    request: ScheduleCancelRequest = ScheduleCancelRequest(),
    current_user: User = Depends(require_role(UserRole.COMPANY_ADMIN, UserRole.EDITOR)),
    db: Session = Depends(get_db),
):
    return BlogScheduleService.cancel_schedule(db, schedule_id, current_user, request)
