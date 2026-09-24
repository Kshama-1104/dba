from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.app.api.access_request_decisions import (
    router as access_request_decisions_router,
)
from backend.app.api.access_requests import (
    router as access_requests_router,
)
from backend.app.api.auth import router as auth_router
from backend.app.api.blog_format import (
    router as blog_format_router,
)
from backend.app.api.company import router as company_router
from backend.app.api.company_ai_profile import (
    router as company_ai_profile_router,
)
from backend.app.api.company_settings import (
    router as company_settings_router,
)
from backend.app.api.editors import router as editors_router
from backend.app.api.id_cards import router as id_cards_router
from backend.app.api.otp import router as otp_router
from backend.app.api.registration import router as registration_router
from backend.app.api.reviewer_registration import (
    router as reviewer_registration_router,
)
from backend.app.api.reviewers import router as reviewers_router
from backend.app.core.database import engine
from backend.app.core.security import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.api.editor_registration import (
    router as editor_registration_router,
)
from backend.app.api.external_integrations import (
    router as external_integrations_router,
)
from backend.app.api.knowledge import router as knowledge_router
from backend.app.api.memory import router as memory_router
from backend.app.api.topics import router as topics_router
from backend.app.api.blogs import router as blogs_router
from backend.app.api.blog_chat import router as blog_chat_router
from backend.app.api.blog_reviews import router as blog_reviews_router
from backend.app.api.blog_schedules import router as blog_schedules_router
from backend.app.api.wordpress import router as wordpress_router


import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.app.worker.scheduler_worker import SchedulerWorker
    from backend.app.services.wordpress_provider import WordPressPublicationProvider
    from backend.app.core.database import SessionLocal
    
    worker = SchedulerWorker()
    
    async def scheduler_loop():
        while True:
            try:
                with SessionLocal() as db:
                    claimed_ids = worker.claim_due_schedules(db)
                    for sid in claimed_ids:
                        publisher = WordPressPublicationProvider(db=db)
                        await worker.process_one_schedule(db, sid, publisher)
            except Exception as e:
                logger.error(f"Scheduler worker error: {e}")
            await asyncio.sleep(worker.poll_interval)
            
    task = asyncio.create_task(scheduler_loop())
    yield
    task.cancel()

app = FastAPI(
    title="DailyBlog AI API",
    description="AI-powered automated blog generation and publishing system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# API Routers
# ---------------------------------------------------------

app.include_router(auth_router)
app.include_router(registration_router)
app.include_router(otp_router)
app.include_router(company_router)
app.include_router(company_settings_router)
app.include_router(company_ai_profile_router)
app.include_router(blog_format_router)
app.include_router(knowledge_router)
app.include_router(memory_router)
app.include_router(wordpress_router)
app.include_router(external_integrations_router)
app.include_router(topics_router)
app.include_router(blogs_router)
app.include_router(blog_chat_router)
app.include_router(blog_reviews_router)
app.include_router(blog_schedules_router)
app.include_router(reviewers_router)
app.include_router(editors_router)
app.include_router(id_cards_router)
app.include_router(access_requests_router)
app.include_router(access_request_decisions_router)
app.include_router(reviewer_registration_router)
app.include_router(editor_registration_router)


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Daily Blog AI API",
    }


@app.get("/health/database")
def database_health_check():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        value = result.scalar()

    return {
        "status": "healthy",
        "database": "PostgreSQL",
        "test_result": value,
    }


# ---------------------------------------------------------
# Current User
# ---------------------------------------------------------

@app.get("/api/v1/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return {
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role.value,
        "company_id": current_user.company_id,
    }


# ---------------------------------------------------------
# Company Admin Test
# ---------------------------------------------------------

@app.get("/api/v1/admin/test")
def admin_test(
    current_user: User = Depends(
        require_role(UserRole.COMPANY_ADMIN)
    ),
):
    return {
        "message": "Company Admin access granted.",
        "user_id": current_user.id,
        "role": current_user.role.value,
        "company_id": current_user.company_id,
    }