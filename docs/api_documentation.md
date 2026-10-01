# DailyBlog AI - API Documentation

The DailyBlog AI backend is built with FastAPI and implements ~55 RESTful endpoints. The API enforces strict JWT Bearer authentication, Role-Based Access Control (RBAC), and Tenant Isolation (`company_id` derived securely from the authenticated user).

## Core API Modules

### 1. Authentication & Registration
- `POST /api/v1/auth/login`: Authenticate and receive JWT token.
- `POST /api/v1/auth/set-permanent-password`: Activate account after admin approval.
- `POST /api/v1/registration/company`: Start Company Admin onboarding.
- `POST /api/v1/registration/reviewer`: Start Reviewer onboarding.
- `POST /api/v1/registration/editor`: Start Editor onboarding.
- `POST /api/v1/registration/*/otp/verify`: Verify email via OTP.
- `POST /api/v1/registration/*/captcha/verify`: Prevent automated registration.

### 2. Access Requests (Governance)
- `GET /api/v1/access-requests`: List pending requests for the logged-in admin/reviewer.
- `PATCH /api/v1/access-requests/{id}/decision`: Accept/Reject an access request (generates temporary password).

### 3. Company & AI Context
- `GET /api/v1/company/settings`: Retrieve application settings.
- `GET/PUT /api/v1/company/ai-profile`: Manage the Company AI Context (brand voice, audience, industry).
- `GET/POST /api/v1/company/blog-format`: Manage standard blog formats (Title + X Headings + CTA).

### 4. Knowledge & Memory (RAG)
- `POST /api/v1/knowledge/documents`: Upload and vectorize a PDF/DOCX/TXT file for RAG.
- `POST /api/v1/knowledge/search`: Perform semantic search using `pgvector` cosine distance.
- `GET/POST /api/v1/company/memory`: Manage episodic and semantic memories injected into LLM context.

### 5. Topic Intelligence
- `POST /api/v1/company/topics/generate`: Use AI to generate SEO-optimized content topics based on RAG context.
- `POST /api/v1/company/topics/{id}/select`: Convert a topic candidate into a draft blog.

### 6. Blog Generation & Editing
- `POST /api/v1/blogs/generate`: Instruct the AI to generate a complete blog draft (JSON AST + Markdown).
- `GET /api/v1/blogs`: List blogs in the workspace.
- `POST /api/v1/blogs/{id}/chat`: Send editor feedback to the AI and generate a new BlogRevision.
- `GET /api/v1/blogs/{id}/revisions`: View the immutable revision history of the blog.
- `POST /api/v1/blogs/{id}/validate`: Run Phase 7 deterministic SEO and format validation.

### 7. Review & Approval
- `POST /api/v1/blogs/{id}/submit-for-review`: Submit a draft for human review (must pass validation).
- `GET /api/v1/blogs/reviews/pending`: Shared queue of pending reviews for Reviewers.
- `POST /api/v1/blogs/{id}/reviews/{id}/decide`: Render a decision (Approve, Request Changes, Reject).

### 8. Scheduling & Publishing
- `POST /api/v1/blogs/{id}/schedules`: Schedule an approved blog for publication (Timezone-aware).
- `POST /api/v1/schedules/{id}/reschedule`: Update the publication time.
- `POST /api/v1/schedules/{id}/cancel`: Cancel a scheduled publication.
- `POST /api/v1/integrations/wordpress`: Configure CMS credentials (AES-256-GCM encrypted).

## Security Measures
- **Tenant Isolation:** No endpoint accepts `company_id` in the request body/path. It is exclusively derived from the JWT.
- **SSRF Protection:** Outbound requests (e.g., WordPress publication) use strict DNS resolution to block private/loopback networks.
- **Row-Level Locks:** `SELECT FOR UPDATE` is heavily utilized to prevent race conditions during blog state transitions and scheduling.
