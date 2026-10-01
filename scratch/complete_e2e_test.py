import requests
import json
from datetime import datetime, timedelta, timezone

BASE_URL = "http://127.0.0.1:8000"

def log_step(title):
    print(f"\n{'='*60}\n>>> {title}\n{'='*60}")

def login(email, password="password123"):
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    print(f" [PASS] Authenticated as {email}")
    return token

def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def run_e2e():
    print("Starting Comprehensive End-to-End Test Suite...")

    # -------------------------------------------------------------
    # 1. ADMIN WORKFLOW
    # -------------------------------------------------------------
    log_step("1. ADMIN: Configure AI Context & Brand Format")
    admin_token = login("admin@test.com")
    admin_hdr = auth_headers(admin_token)

    # 1.1 Update AI Context
    profile_data = {
        "products_services": "Next-Gen Cloud Security & Zero Trust Network Access Platform",
        "target_audience": "Enterprise CISOs, DevOps Engineers, and Security Directors",
        "brand_voice": "Authoritative, technical, clear, and reassuring",
        "preferred_writing_style": "Data-backed architectural thought leadership",
        "marketing_goals": "Position our company as the standard for multi-cloud zero trust",
        "company_guidelines": "Always emphasize least-privilege access and zero-trust principles",
        "upcoming_projects": "Global Cloud Defense Summit 2026",
        "partner_companies": "AWS, Google Cloud, HashiCorp",
        "achievements": "SOC 2 Type II Certified, protecting 1M+ workloads",
    }
    resp = requests.put(f"{BASE_URL}/api/v1/company/ai-profile", json=profile_data, headers=admin_hdr)
    assert resp.status_code == 200, f"Admin AI profile update failed: {resp.text}"
    print(" [PASS] Admin successfully updated Company AI Profile.")

    # 1.2 Verify Admin can View Active Blog Format
    resp = requests.get(f"{BASE_URL}/api/v1/company/blog-format", headers=admin_hdr)
    assert resp.status_code == 200, f"Admin format retrieval failed: {resp.text}"
    print(" [PASS] Admin successfully audited active Global Blog Format.")

    # -------------------------------------------------------------
    # 2. EDITOR WORKFLOW
    # -------------------------------------------------------------
    log_step("2. EDITOR: Blog Format, Topic Creation, Selection, AI Blog Synthesis, Chat Revision")
    editor_token = login("editor@test.com")
    editor_hdr = auth_headers(editor_token)

    # 2.0 Editor Configures & Activates Global Blog Format
    format_data = {
        "title_structure": "Compelling H1 with primary keyword under 60 chars",
        "introduction_structure": "Hook, quantification of enterprise problem, clear thesis",
        "heading_structure": "Hierarchical H2 main sections and H3 subheadings",
        "main_content_structure": "Architectural tradeoffs, data insights, and bulleted checklists",
        "conclusion_structure": "Executive recap, actionable takeaways, and CTA",
        "call_to_action": "Schedule an architectural security review.",
        "preferred_writing_style": "Authoritative and concise",
        "custom_rules": [
            "Always use active voice.",
            "Include at least one actionable takeaway per section."
        ]
    }
    resp = requests.put(f"{BASE_URL}/api/v1/company/blog-format", json=format_data, headers=editor_hdr)
    assert resp.status_code == 200, f"Editor format creation failed: {resp.text}"
    new_fmt = resp.json()
    version_num = new_fmt["version"]
    assert new_fmt["is_active"] is True
    print(f" [PASS] Editor created & activated Global Blog Format Version {version_num}.")

    # 2.1 Create Custom Topic
    unique_topic_title = f"Zero Trust 2026: The Death of the Enterprise VPN ({datetime.now().strftime('%H%M%S')})"
    topic_data = {
        "title": unique_topic_title,
        "angle": "Why perimeter firewalls fail in modern multi-cloud distributed environments",
        "rationale": "High search volume among CISOs and direct alignment with company security offerings",
        "primary_keyword": "zero trust cloud security",
        "target_audience": "Enterprise CISOs and Security Architects"
    }
    resp = requests.post(f"{BASE_URL}/api/v1/company/topics/custom", json=topic_data, headers=editor_hdr)
    assert resp.status_code == 201, f"Editor custom topic creation failed: {resp.text}"
    topic = resp.json()
    topic_id = topic["id"]
    print(f" [PASS] Editor created topic candidate ID {topic_id} ('{topic['title']}').")

    # 2.2 Select Topic
    resp = requests.post(f"{BASE_URL}/api/v1/company/topics/{topic_id}/select", headers=editor_hdr)
    assert resp.status_code == 200, f"Editor topic selection failed: {resp.text}"
    print(f" [PASS] Editor transitioned topic {topic_id} to status SELECTED.")

    # 2.3 Synthesize Blog Draft via LLM
    print(" [INFO] Triggering multi-phase AI blog synthesis engine...")
    gen_data = {
        "topic_candidate_id": topic_id,
        "editor_instruction": "Keep paragraphs punchy, cite multi-cloud resilience, and provide an implementation checklist."
    }
    resp = requests.post(f"{BASE_URL}/api/v1/blogs/generate", json=gen_data, headers=editor_hdr)
    assert resp.status_code == 201, f"Blog synthesis failed: {resp.text}"
    blog = resp.json()
    blog_id = blog["id"]
    print(f" [PASS] Blog ID {blog_id} generated successfully!")
    print(f"        Title: '{blog['title']}'")
    print(f"        Status: {blog['status']}")

    # 2.4 Run Phase 7 SEO & Format Validation
    resp = requests.post(f"{BASE_URL}/api/v1/blogs/{blog_id}/validate", headers=editor_hdr)
    assert resp.status_code == 200, f"Validation failed: {resp.text}"
    val_report = resp.json()
    print(f" [PASS] Phase 7 Validation executed: passed={val_report['passed']}")
    print(f"        Errors: {len(val_report['errors'])}, Warnings: {len(val_report['warnings'])}")

    # 2.5 Conversational AI Revision (Editor Chat)
    print(" [INFO] Testing Conversational AI Revision (Phase 8)...")
    rev_resp = requests.get(f"{BASE_URL}/api/v1/blogs/{blog_id}/revisions", headers=editor_hdr)
    assert rev_resp.status_code == 200, f"Revision listing failed: {rev_resp.text}"
    rev_list = rev_resp.json()
    base_rev_id = rev_list[-1]["id"] if rev_list else 0

    chat_prompt = {
        "message": "Please tighten the introduction and add an actionable takeaway bullet point.",
        "base_revision_id": base_rev_id
    }
    resp = requests.post(f"{BASE_URL}/api/v1/blogs/{blog_id}/chat", json=chat_prompt, headers=editor_hdr)
    assert resp.status_code in (200, 201), f"AI Chat revision failed: {resp.text}"
    print(" [PASS] Editor chat revision executed and created new revision snapshot.")

    # 2.6 Submit for Review (Enforce Separation of Duties)
    sub_data = {
        "submission_note": "Article completed with ZTNA implementation checklist. Ready for editorial review."
    }
    resp = requests.post(f"{BASE_URL}/api/v1/blogs/{blog_id}/submit-for-review", json=sub_data, headers=editor_hdr)
    assert resp.status_code == 201, f"Submit for review failed: {resp.text}"
    review_info = resp.json()
    review_id = review_info["id"]
    print(f" [PASS] Blog {blog_id} submitted for review! Review ID: {review_id}, status: {review_info['status']}")

    # Verify Editor cannot self-approve (Separation of Duties)
    resp = requests.post(
        f"{BASE_URL}/api/v1/blogs/{blog_id}/reviews/{review_id}/decide",
        json={"decision": "approve", "reviewer_comment": "Self-approval attempt"},
        headers=editor_hdr
    )
    assert resp.status_code == 403, f"Editor self-approval was NOT blocked! Status: {resp.status_code}"
    print(" [PASS] Verified Separation of Duties: Editor self-approval correctly blocked with HTTP 403.")

    # -------------------------------------------------------------
    # 3. REVIEWER WORKFLOW
    # -------------------------------------------------------------
    log_step("3. REVIEWER: Inspect Pending Queue & Render Decision")
    reviewer_token = login("reviewer@test.com")
    reviewer_hdr = auth_headers(reviewer_token)

    # 3.1 Check Pending Queue
    resp = requests.get(f"{BASE_URL}/api/v1/blogs/reviews/pending", headers=reviewer_hdr)
    assert resp.status_code == 200, f"Pending queue retrieval failed: {resp.text}"
    pending_items = resp.json()
    matched = [p for p in pending_items if p["blog_id"] == blog_id]
    assert len(matched) > 0, f"Blog {blog_id} not found in pending review queue!"
    print(f" [PASS] Reviewer identified Blog {blog_id} in pending review queue.")

    # 3.2 Render Approval Decision
    decision_data = {
        "decision": "approve",
        "reviewer_comment": "Excellent technical depth and brand alignment. Approved for scheduling."
    }
    resp = requests.post(
        f"{BASE_URL}/api/v1/blogs/{blog_id}/reviews/{review_id}/decide",
        json=decision_data,
        headers=reviewer_hdr
    )
    assert resp.status_code == 200, f"Reviewer decision failed: {resp.text}"
    print(f" [PASS] Reviewer approved Blog {blog_id}. Blog status is now APPROVED.")

    # Verify blog status is approved
    resp = requests.get(f"{BASE_URL}/api/v1/blogs/{blog_id}", headers=reviewer_hdr)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    print(" [PASS] Confirmed blog status transitioned to 'approved'.")

    # -------------------------------------------------------------
    # 4. SCHEDULING WORKFLOW
    # -------------------------------------------------------------
    log_step("4. SCHEDULING: Schedule Publication for Approved Blog")
    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    schedule_data = {
        "local_scheduled_time": future_time.strftime("%Y-%m-%dT10:00:00"),
        "timezone": "UTC"
    }
    resp = requests.post(f"{BASE_URL}/api/v1/blogs/{blog_id}/schedules", json=schedule_data, headers=admin_hdr)
    assert resp.status_code == 201, f"Scheduling failed: {resp.text}"
    schedule_info = resp.json()
    print(f" [PASS] Blog scheduled successfully! Schedule ID: {schedule_info['id']}, Scheduled At (UTC): {schedule_info['scheduled_at_utc']}")

    # 4.1 Verify schedule listing
    resp = requests.get(f"{BASE_URL}/api/v1/blogs/{blog_id}/schedules", headers=admin_hdr)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    print(f" [PASS] Verified publication schedule listed under Blog {blog_id}.")

    log_step("ALL E2E WORKFLOW TESTS PASSED CLEANLY WITH ZERO ERRORS!")

if __name__ == "__main__":
    run_e2e()
