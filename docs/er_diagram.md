# DailyBlog AI - Entity Relationship Diagram

This document contains the Entity Relationship (ER) diagram for the DailyBlog AI database architecture, mapped from the 19 SQLAlchemy models and 17 Alembic migrations.

## Core Domain Model

```mermaid
erDiagram
    Company ||--o{ User : "has many"
    Company ||--o| CompanySettings : "has one"
    Company ||--o| CompanyAIProfile : "has one"
    Company ||--o{ BlogFormat : "defines"
    Company ||--o{ TopicCandidate : "generates"
    Company ||--o{ Blog : "owns"
    Company ||--o{ KnowledgeDocument : "ingests"
    Company ||--o{ CompanyMemory : "retains"
    Company ||--o{ WordPressConnection : "configures"

    User ||--o{ AccessRequest : "approves/requests"
    
    KnowledgeDocument ||--o{ KnowledgeChunk : "splits into"
    KnowledgeChunk ||--o| KnowledgeEmbedding : "vectorized as"

    TopicCandidate ||--o| Blog : "becomes"
    Blog ||--o| BlogChatThread : "has one"
    BlogChatThread ||--o{ BlogChatMessage : "contains"
    BlogChatThread ||--o{ BlogRevision : "tracks"
    Blog ||--o{ BlogRevision : "has history of"
    Blog ||--o{ BlogReview : "undergoes"
    BlogRevision ||--o{ BlogReview : "submitted as"

    Blog ||--o{ BlogSchedule : "scheduled via"
    BlogRevision ||--o{ BlogSchedule : "published as"
    BlogSchedule ||--o{ BlogScheduleEvent : "audit trail"
    BlogSchedule ||--o{ BlogPublicationJob : "executed via"

    WordPressConnection ||--o{ WordPressPublicationRecord : "publishes"
    BlogPublicationJob ||--o| WordPressPublicationRecord : "results in"
```

## Description of Key Entities

*   **Company (Tenant):** The root of the multi-tenant architecture. Every domain model carries a `company_id` foreign key for strict data isolation.
*   **User:** Contains role-based access control (RBAC) via `UserRole` enum (`COMPANY_ADMIN`, `EDITOR`, `REVIEWER`).
*   **CompanyAIProfile:** Stores brand voice, audience, industry, and marketing goals for the LLM context generation.
*   **KnowledgeDocument / KnowledgeChunk / KnowledgeEmbedding:** The RAG pipeline storage using `pgvector` (384-dimensional embeddings).
*   **Blog / BlogRevision / BlogReview:** The core editorial workflow. Revisions are immutable, append-only records. Reviews enforce Separation of Duties (SoD).
*   **BlogSchedule:** Timezone-aware publication scheduling.
*   **WordPressConnection:** Stores AES-256-GCM encrypted credentials for WordPress integration.
