import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def print_step(step_name):
    print(f"\n{'='*50}\nSTEP: {step_name}\n{'='*50}")

def get_token(email, password="password123"):
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print(f"Failed to login as {email}: {resp.text}")
        sys.exit(1)
    print(f"[OK] Logged in successfully as {email}")
    return resp.json()["access_token"]

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def main():
    print("Starting E2E API Workflow Test...")

    # 1. ADMIN WORKFLOW
    print_step("ADMIN: Configure Company Context")
    admin_token = get_token("admin@test.com")
    headers = auth_headers(admin_token)

    # Set Company Context
    ctx_resp = requests.put(f"{BASE_URL}/api/v1/company/ai-profile", json={
        "profile_context": "B2B Cybersecurity firm specializing in zero-trust architecture.",
        "target_audience": "Enterprise CISOs, IT Directors, and Compliance Officers."
    }, headers=headers)
    assert ctx_resp.status_code == 200, f"Context fail: {ctx_resp.text}"
    print("[OK] Company AI Context saved.")

    # 2. EDITOR WORKFLOW
    print_step("EDITOR: Configuration, Topic Creation and Blog Synthesis")
    editor_token = get_token("editor@test.com")
    headers = auth_headers(editor_token)

    # Set Blog Format
    fmt_resp = requests.put(f"{BASE_URL}/api/v1/company/blog-format", json={
        "brand_voice": "Authoritative, professional, clear, and reassuring.",
        "format_rules": "Use H2 headers. Keep paragraphs short. Include a conclusion."
    }, headers=headers)
    assert fmt_resp.status_code == 200, f"Format fail: {fmt_resp.text}"
    print("[OK] Blog Format saved.")

    # Create Custom Topic
    topic_resp = requests.post(f"{BASE_URL}/api/v1/company/topics/custom", json={
        "title": "Why VPNs are Dead in 2024",
        "angle": "Contrast legacy VPNs with modern Zero Trust.",
        "rationale": "High search volume and addresses executive pain points.",
        "primary_keyword": "zero trust vs vpn",
        "target_audience": "CISOs"
    }, headers=headers)
    assert topic_resp.status_code == 201, f"Topic fail: {topic_resp.text}"
    topic = topic_resp.json()
    topic_id = topic["id"]
    print(f"[OK] Created custom topic: '{topic['title']}' (ID: {topic_id})")

    # Select Topic
    select_resp = requests.post(f"{BASE_URL}/api/v1/company/topics/{topic_id}/select", headers=headers)
    assert select_resp.status_code == 200, f"Select fail: {select_resp.text}"
    print("[OK] Topic state changed to SELECTED.")

    # Generate Blog (Calls LLM)
    print("[WAIT] Triggering AI Blog Synthesis (This calls Google Gemini, please wait 10-20 seconds)...")
    start_time = time.time()
    blog_resp = requests.post(f"{BASE_URL}/api/v1/blogs/generate", json={
        "topic_candidate_id": topic_id,
        "editor_instruction": "Make sure to emphasize the shift to remote work."
    }, headers=headers)
    if blog_resp.status_code != 200:
        print(f"[ERROR] Blog Generation Failed: {blog_resp.text}")
        sys.exit(1)
    blog = blog_resp.json()
    blog_id = blog["id"]
    duration = round(time.time() - start_time, 2)
    print(f"[OK] Blog Draft generated successfully in {duration} seconds!")
    print(f"[INFO] Title: {blog['title']}")
    print(f"[INFO] Preview: {blog['content'][:150]}...")

    # Submit for Review
    submit_resp = requests.post(f"{BASE_URL}/api/v1/blogs/{blog_id}/submit-for-review", headers=headers)
    assert submit_resp.status_code == 201, f"Submit review fail: {submit_resp.text}"
    review_data = submit_resp.json()
    review_id = review_data["id"]
    print(f"[OK] Draft submitted for review (Review ID: {review_id}).")

    # 3. REVIEWER WORKFLOW
    print_step("REVIEWER: Governance and Approval")
    reviewer_token = get_token("reviewer@test.com")
    headers = auth_headers(reviewer_token)

    # Approve Blog
    approve_resp = requests.post(f"{BASE_URL}/api/v1/blogs/{blog_id}/reviews/{review_id}/decide", json={
        "status": "approved",
        "feedback": "Excellent technical depth and perfectly aligns with our zero-trust narrative."
    }, headers=headers)
    assert approve_resp.status_code == 200, f"Approve fail: {approve_resp.text}"
    print(f"[OK] Blog (ID: {blog_id}) officially APPROVED by Reviewer.")

    # Check Final Status
    final_resp = requests.get(f"{BASE_URL}/api/v1/blogs/{blog_id}", headers=headers)
    final_blog = final_resp.json()
    print(f"[OK] Final Blog Status verified as: {final_blog['status']}")

    print_step("END-TO-END WORKFLOW COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
