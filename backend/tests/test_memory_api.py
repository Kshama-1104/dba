from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.company_ai_profile import CompanyAIProfile
from backend.app.models.company_memory import MemoryStatus, MemoryType
from backend.app.models.user import UserRole
from backend.app.schemas.company_memory import CompanyMemoryCreate
from backend.app.services.memory_service import create_company_memory


def test_create_memory_by_editor_success(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    headers = auth_headers(editor)

    payload = {
        "memory_type": "SEMANTIC",
        "content": "NexaCore specializes in autonomous supply chain telemetry.",
        "source": "EDITOR_CHAT",
        "confidence": "HIGH",
        "importance": 5,
    }

    response = client.post("/api/v1/company/memory", headers=headers, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == company.id
    assert data["memory_type"] == "SEMANTIC"
    assert data["status"] == "ACTIVE"
    assert data["importance"] == 5


def test_create_memory_by_admin_success(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    headers = auth_headers(admin)

    payload = {
        "memory_type": "PROCEDURAL",
        "content": "Avoid informal slang; maintain an authoritative tone.",
        "source": "COMPANY_PROFILE",
    }

    response = client.post("/api/v1/company/memory", headers=headers, json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "ACTIVE"


def test_create_memory_by_reviewer_rejected_with_403(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    company = create_company()
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER)
    headers = auth_headers(reviewer)

    payload = {
        "memory_type": "EPISODIC",
        "content": "Reviewer rejected topic X.",
    }

    response = client.post("/api/v1/company/memory", headers=headers, json=payload)
    assert response.status_code == 403


def test_create_memory_unauthenticated_rejected_with_401(client: TestClient):
    response = client.post(
        "/api/v1/company/memory",
        json={"memory_type": "SEMANTIC", "content": "Some fact"},
    )
    assert response.status_code == 401


def test_create_memory_sensitive_data_rejected(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    headers = auth_headers(editor)

    payload = {
        "memory_type": "SEMANTIC",
        "content": "Database admin password: SecretPassword123!",
    }

    response = client.post("/api/v1/company/memory", headers=headers, json=payload)
    # Pydantic field_validator raises ValueError -> 422 Unprocessable Entity
    assert response.status_code in [400, 422]
    assert "sensitive credentials" in str(response.json()).lower()


def test_create_memory_invalid_type_rejected(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
):
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    headers = auth_headers(editor)

    payload = {
        "memory_type": "NON_EXISTENT_TYPE",
        "content": "Valid text content.",
    }

    response = client.post("/api/v1/company/memory", headers=headers, json=payload)
    assert response.status_code == 422


def test_list_and_get_memories_rbac_and_tenant_isolation(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session: Session,
):
    company_a = create_company(name="Alpha")
    company_b = create_company(name="Beta")

    reviewer_a = create_user(company_id=company_a.id, role=UserRole.REVIEWER)
    editor_b = create_user(company_id=company_b.id, role=UserRole.EDITOR)

    mem_a = create_company_memory(
        db=db_session,
        company_id=company_a.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.SEMANTIC,
            content="Alpha proprietary product facts.",
        ),
    )

    # Reviewer from Company A CAN list company memories
    res_list = client.get("/api/v1/company/memory", headers=auth_headers(reviewer_a))
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] == 1
    assert data["memories"][0]["id"] == mem_a.id

    # Reviewer from Company A CAN view memory details
    res_get = client.get(f"/api/v1/company/memory/{mem_a.id}", headers=auth_headers(reviewer_a))
    assert res_get.status_code == 200
    assert res_get.json()["id"] == mem_a.id

    # User from Company B CANNOT view Company A memory (404)
    res_cross = client.get(f"/api/v1/company/memory/{mem_a.id}", headers=auth_headers(editor_b))
    assert res_cross.status_code == 404


def test_update_memory_by_editor_and_reviewer_forbidden(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session: Session,
):
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER)

    mem = create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.PROCEDURAL,
            content="Initial procedural rule.",
        ),
    )

    # Reviewer cannot update (403)
    res_rev = client.put(
        f"/api/v1/company/memory/{mem.id}",
        headers=auth_headers(reviewer),
        json={"content": "Unauthorized update."},
    )
    assert res_rev.status_code == 403

    # Editor can update (200)
    res_ed = client.put(
        f"/api/v1/company/memory/{mem.id}",
        headers=auth_headers(editor),
        json={"content": "Updated procedural rule by editor."},
    )
    assert res_ed.status_code == 200
    assert res_ed.json()["content"] == "Updated procedural rule by editor."


def test_supersede_memory_api(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session: Session,
):
    company = create_company()
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)

    mem = create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.PROCEDURAL,
            content="Old call to action instruction.",
        ),
    )

    new_payload = {
        "memory_type": "PROCEDURAL",
        "content": "New replacement call to action instruction.",
        "status": "ACTIVE",
    }

    response = client.post(
        f"/api/v1/company/memory/{mem.id}/supersede",
        headers=auth_headers(editor),
        json=new_payload,
    )
    assert response.status_code == 201
    new_data = response.json()
    assert new_data["status"] == "ACTIVE"
    assert new_data["content"] == "New replacement call to action instruction."

    # Verify old memory is now SUPERSEDED
    old_res = client.get(f"/api/v1/company/memory/{mem.id}", headers=auth_headers(editor))
    assert old_res.status_code == 200
    assert old_res.json()["status"] == "SUPERSEDED"
    assert old_res.json()["superseded_by_id"] == new_data["id"]


def test_delete_and_archive_memory_rbac(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session: Session,
):
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)
    editor = create_user(company_id=company.id, role=UserRole.EDITOR)
    reviewer = create_user(company_id=company.id, role=UserRole.REVIEWER)

    mem = create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.EPISODIC,
            content="Historical event to archive.",
        ),
    )

    # Reviewer cannot delete (403)
    res_rev = client.delete(f"/api/v1/company/memory/{mem.id}", headers=auth_headers(reviewer))
    assert res_rev.status_code == 403

    # Editor hard-delete is rejected (403)
    res_ed_hard = client.delete(f"/api/v1/company/memory/{mem.id}?hard_delete=true", headers=auth_headers(editor))
    assert res_ed_hard.status_code == 403
    assert "only company admin can hard-delete" in res_ed_hard.json()["detail"].lower()

    # Editor soft-archives (200)
    res_ed = client.delete(f"/api/v1/company/memory/{mem.id}", headers=auth_headers(editor))
    assert res_ed.status_code == 200
    assert "archived" in res_ed.json()["message"]

    # Create another memory for Admin hard-delete test
    mem2 = create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.EPISODIC,
            content="Temporary record to hard delete.",
        ),
    )

    # Admin hard-deletes (200)
    res_admin_hard = client.delete(f"/api/v1/company/memory/{mem2.id}?hard_delete=true", headers=auth_headers(admin))
    assert res_admin_hard.status_code == 200
    assert "deleted" in res_admin_hard.json()["message"]


def test_retrieve_memories_api_tenant_isolation(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session: Session,
):
    company_a = create_company(name="Alpha")
    company_b = create_company(name="Beta")

    editor_a = create_user(company_id=company_a.id, role=UserRole.EDITOR)
    editor_b = create_user(company_id=company_b.id, role=UserRole.EDITOR)

    create_company_memory(
        db=db_session,
        company_id=company_a.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.SEMANTIC,
            content="Alpha unique positioning: autonomous edge computing systems.",
        ),
    )
    create_company_memory(
        db=db_session,
        company_id=company_b.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.SEMANTIC,
            content="Beta unique positioning: autonomous edge computing systems.",
        ),
    )

    payload = {"query": "autonomous edge computing systems", "top_k": 5}

    # Company A search
    res_a = client.post("/api/v1/company/memory/retrieve", headers=auth_headers(editor_a), json=payload)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total_results"] > 0
    for m in data_a["memories"]:
        assert m["company_id"] == company_a.id
        assert "Alpha" in m["content"]
        assert "Beta" not in m["content"]


def test_resolve_conflicts_api(
    client: TestClient,
    create_company,
    create_user,
    auth_headers,
    db_session: Session,
):
    company = create_company()
    admin = create_user(company_id=company.id, role=UserRole.COMPANY_ADMIN)

    # Set structured profile voice
    profile = CompanyAIProfile(
        company_id=company.id,
        brand_voice="Direct and Authoritative",
    )
    db_session.add(profile)

    # Contradicting procedural memory
    create_company_memory(
        db=db_session,
        company_id=company.id,
        memory_in=CompanyMemoryCreate(
            memory_type=MemoryType.PROCEDURAL,
            content="Preferred brand tone: Conversational and Casual.",
            source="EDITOR_CHAT",
        ),
    )

    response = client.post("/api/v1/company/memory/resolve-conflicts", headers=auth_headers(admin))
    assert response.status_code == 200
    data = response.json()
    assert data["structured_profile_precedence_applied"] is True
    assert data["conflicts_detected"] == 1
