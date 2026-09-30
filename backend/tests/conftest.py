import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.database import engine, get_db
from backend.app.core.security import hash_password
from backend.app.models.company import Company
from backend.app.models.user import User, UserRole, UserStatus
from backend.app.core.config import settings
from backend.app.services.auth_service import create_user_access_token
from backend.main import app


@pytest.fixture(autouse=True, scope="session")
def configure_test_environment():
    orig_provider = settings.llm_provider
    settings.llm_provider = "deterministic"
    yield
    settings.llm_provider = orig_provider


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """
    Provides a transactional database session using SQLAlchemy 2.0 savepoints.
    All commits within the test are scoped to savepoints and rolled back at teardown.
    Leaves the database completely clean with 0 persistent artifacts.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Provides a FastAPI TestClient with get_db overridden to use the transactional db_session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def create_company(db_session: Session):
    """
    Factory fixture to create test companies with unique attributes.
    """
    def _create(
        name: str = "Test Company",
        industry: str = "Technology",
        email: str | None = None,
    ) -> Company:
        unique_suffix = uuid.uuid4().hex[:8]
        if email is None:
            email = f"company_{unique_suffix}@example.com"

        company = Company(
            name=f"{name} {unique_suffix}",
            description="Test company description",
            logo_url="https://example.com/logo.png",
            company_type="Private",
            industry=industry,
            country_region="United States",
            company_email=email,
            notification_email=email,
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
        return company

    return _create


@pytest.fixture
def create_user(db_session: Session):
    """
    Factory fixture to create test users with specified role and status.
    """
    def _create(
        company_id: int,
        role: UserRole = UserRole.COMPANY_ADMIN,
        email: str | None = None,
        password: str = "StrongPassword123!",
        status: UserStatus = UserStatus.ACTIVE,
    ) -> User:
        unique_suffix = uuid.uuid4().hex[:8]
        if email is None:
            email = f"{role.value}_{unique_suffix}@example.com"

        user = User(
            company_id=company_id,
            name=f"Test {role.value.capitalize()}",
            email=email,
            role=role,
            status=status,
            password_hash=hash_password(password),
            permanent_password_set=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def auth_headers():
    """
    Helper to generate Authorization headers for a given user.
    """
    def _headers(user: User) -> dict[str, str]:
        token = create_user_access_token(user)
        return {"Authorization": f"Bearer {token}"}

    return _headers
