// Role definitions
export type UserRole = "company_admin" | "reviewer" | "editor";

export interface User {
  user_id: number;
  name: string;
  email: string;
  role: UserRole;
  company_id: number;
}

export interface LoginResponse {
  access_token: string;
  user_id: number;
  role: UserRole;
  company_id: number;
  requires_password_setup: boolean;
}

// Company Info & AI Profile
export interface CompanyInfo {
  id: number;
  name: string;
  description: string | null;
  logo_url: string | null;
  company_type: string | null;
  industry: string | null;
  country_region: string | null;
  company_email: string | null;
  notification_email: string | null;
}

export interface CompanyDashboardData {
  company: CompanyInfo;
  user: {
    id: number;
    name: string;
    email: string;
    role: string;
  };
}

export interface CompanyAIProfile {
  id: number;
  company_id: number;
  products_services: string | null;
  target_audience: string | null;
  preferred_writing_style: string | null;
  brand_voice: string | null;
  marketing_goals: string | null;
  company_guidelines: string | null;
  upcoming_projects: string | null;
  partner_companies: string | null;
  achievements: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanySettings {
  company_id: number;
  notification_email: string;
  blog_generation_enabled: boolean;
  publishing_enabled: boolean;
}

// Global Blog Format
export interface BlogFormatDefinition {
  title_structure: string;
  introduction_structure: string;
  heading_structure: string;
  main_content_structure: string;
  conclusion_structure: string;
  call_to_action?: string | null;
  preferred_writing_style?: string | null;
  required_sections: string[];
  optional_sections: string[];
  seo_guidelines?: Record<string, unknown> | null;
  custom_rules: string[];
}

export interface BlogFormat {
  id: number;
  company_id: number;
  version: number;
  format_definition: BlogFormatDefinition;
  is_active: boolean;
  created_by?: number | null;
  created_at: string;
  updated_at: string;
}

export interface BlogFormatListResponse {
  total_versions: number;
  active_version: number | null;
  formats: BlogFormat[];
}

// Knowledge & RAG
export interface KnowledgeDocument {
  id: number;
  company_id: number;
  title: string | null;
  original_filename: string;
  content_type: string;
  description: string | null;
  status: "PENDING" | "PROCESSING" | "READY" | "FAILED";
  processing_error: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentListResponse {
  total: number;
  documents: KnowledgeDocument[];
}

export interface RetrievedChunk {
  chunk_id: number;
  document_id: number;
  title: string | null;
  chunk_index: number;
  content: string;
  similarity_score: number;
}

export interface KnowledgeRetrievalResponse {
  query: string;
  total_results: number;
  results: RetrievedChunk[];
}

// Memory
export type MemoryType = "SEMANTIC" | "EPISODIC" | "PROCEDURAL";
export type MemoryStatus = "CANDIDATE" | "ACTIVE" | "SUPERSEDED" | "ARCHIVED";
export type MemorySource =
  | "COMPANY_PROFILE"
  | "EDITOR_CHAT"
  | "REVIEWER_FEEDBACK"
  | "EXPLICIT_USER"
  | "SYSTEM_CONFIRMED";
export type MemoryConfidence = "HIGH" | "MEDIUM" | "LOW";

export interface CompanyMemory {
  id: number;
  company_id: number;
  memory_type: MemoryType;
  content: string;
  source: MemorySource;
  confidence: MemoryConfidence;
  importance: number;
  status: MemoryStatus;
  superseded_by_id?: number | null;
  metadata_payload?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  last_accessed_at?: string | null;
}

export interface CompanyMemoryListResponse {
  total: number;
  memories: CompanyMemory[];
}

export interface RetrievedMemoryItem {
  id: number;
  company_id: number;
  memory_type: MemoryType;
  content: string;
  source: MemorySource;
  confidence: MemoryConfidence;
  importance: number;
  status: MemoryStatus;
  similarity_score: number;
}

export interface MemoryConflictResolutionResponse {
  company_id: number;
  conflicts_detected: number;
  structured_profile_precedence_applied: boolean;
  summary: string;
  active_memory_count: number;
}

export interface MemoryRetrievalResponse {
  query: string;
  total_results: number;
  memories: RetrievedMemoryItem[];
}

// Topics
export type TopicStatus = "suggested" | "selected" | "rejected" | "used" | "expired";

export interface TopicCandidate {
  id: number;
  company_id: number;
  title: string;
  angle: string;
  rationale: string;
  target_audience?: string | null;
  primary_keyword: string;
  relevance_score: number;
  freshness_score: number;
  final_score: number;
  status: TopicStatus;
  created_by_user_id?: number | null;
  selected_by_user_id?: number | null;
  selected_at?: string | null;
  rejected_by_user_id?: number | null;
  rejected_at?: string | null;
  created_at: string;
  updated_at: string;
}

// Blogs
export type BlogStatus =
  | "draft"
  | "pending_review"
  | "changes_requested"
  | "approved"
  | "scheduled"
  | "publishing"
  | "published"
  | "failed"
  | "cancelled";

export interface BlogDraftSection {
  heading: string;
  level: number;
  content: string;
}

export interface StructuredBlogDraft {
  seo_title: string;
  meta_description: string;
  primary_keyword: string;
  h1_title: string;
  introduction: string;
  sections: BlogDraftSection[];
  conclusion: string;
  call_to_action: string;
}

export interface BlogSummary {
  id: number;
  company_id: number;
  topic_candidate_id: number;
  title: string;
  primary_keyword: string | null;
  status: BlogStatus;
  created_at: string;
  updated_at: string;
}

export interface BlogDetail extends BlogSummary {
  slug: string | null;
  seo_title: string | null;
  meta_description: string | null;
  format_version: number | null;
  generation_metadata?: Record<string, unknown> | null;
  content_json: StructuredBlogDraft;
  content_markdown: string;
}

// SEO & Format Validation
export interface ValidationFinding {
  rule: string;
  message: string;
  field?: string | null;
  severity: "error" | "warning";
  details?: Record<string, unknown> | null;
}

export interface SeoValidationReport {
  seo_title_valid: boolean;
  seo_title_length: number;
  meta_description_valid: boolean;
  meta_description_length: number;
  primary_keyword: string | null;
  keyword_in_seo_title: boolean;
  keyword_in_introduction: boolean;
  keyword_in_h2: boolean;
  slug_valid: boolean;
  slug_issues: string[];
  keyword_stuffing_warning: boolean;
  keyword_density: number | null;
  findings: ValidationFinding[];
}

export interface FormatValidationReport {
  baseline_sections_valid: boolean;
  h1_title_valid: boolean;
  introduction_valid: boolean;
  conclusion_valid: boolean;
  sections_valid: boolean;
  heading_hierarchy_valid: boolean;
  duplicate_headings: string[];
  company_format_checked: boolean;
  company_format_version: number | null;
  company_sections_valid: boolean;
  missing_company_sections: string[];
  findings: ValidationFinding[];
}

export interface BlogValidationResponse {
  blog_id: number;
  company_id: number;
  passed: boolean;
  errors: ValidationFinding[];
  warnings: ValidationFinding[];
  recommendations: string[];
  seo_report: SeoValidationReport;
  format_report: FormatValidationReport;
  validated_at: string;
}

// Chat & Revisions
export interface BlogChatMessage {
  id: number;
  thread_id: number;
  sender_type: string;
  sender_id?: number | null;
  message_type: string;
  content: string;
  client_message_id?: string | null;
  message_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface BlogChatThread {
  id: number;
  company_id: number;
  blog_id: number;
  editor_id: number;
  status: string;
  created_at: string;
  updated_at: string;
  closed_at?: string | null;
  messages: BlogChatMessage[];
}

export interface BlogRevisionSummary {
  id: number;
  company_id: number;
  blog_id: number;
  revision_number: number;
  revision_summary: string;
  editor_id?: number | null;
  seo_title?: string | null;
  primary_keyword?: string | null;
  restored_from_revision_id?: number | null;
  created_at: string;
}

export interface BlogRevisionDetail extends BlogRevisionSummary {
  thread_id?: number | null;
  message_id?: number | null;
  content_json: StructuredBlogDraft;
  content_markdown: string;
  meta_description?: string | null;
  validation_report?: BlogValidationResponse | null;
}

export interface BlogChatResponse {
  thread_id: number;
  user_message: BlogChatMessage;
  assistant_message: BlogChatMessage;
  revision?: BlogRevisionSummary | null;
  blog?: BlogDetail | null;
  validation_report?: BlogValidationResponse | null;
}

// Reviews
export type ReviewDecision = "approve" | "request_changes" | "reject";

export interface BlogReview {
  id: number;
  company_id: number;
  blog_id: number;
  submitted_revision_id: number;
  reviewer_id?: number | null;
  status: string;
  submission_note?: string | null;
  feedback?: string | null;
  reviewer_comment?: string | null;
  submitted_at: string;
  decided_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BlogReviewDetail extends BlogReview {
  submitted_revision_number?: number | null;
  submitted_by_user_id?: number | null;
  blog_title?: string | null;
}

export interface PendingReviewItem {
  review_id: number;
  blog_id: number;
  blog_title: string;
  submitted_revision_id: number;
  submitted_revision_number: number;
  submitted_by_user_id?: number | null;
  submission_note?: string | null;
  submitted_at: string;
  status: string;
}

// Scheduling
export interface BlogSchedule {
  id: number;
  company_id: number;
  blog_id: number;
  target_revision_id: number;
  scheduled_at_utc: string;
  local_scheduled_time: string;
  timezone: string;
  status: string; // SCHEDULED, QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED
  attempt_count: number;
  max_attempts: number;
  reschedule_count: number;
  failure_code?: string | null;
  last_error?: string | null;
  created_by_user_id: number;
  cancelled_by_user_id?: number | null;
  cancelled_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BlogScheduleEvent {
  id: number;
  schedule_id: number;
  company_id: number;
  event_type: string;
  actor_user_id?: number | null;
  previous_scheduled_at_utc?: string | null;
  new_scheduled_at_utc?: string | null;
  previous_local_scheduled_time?: string | null;
  new_local_scheduled_time?: string | null;
  previous_timezone?: string | null;
  new_timezone?: string | null;
  reason?: string | null;
  created_at: string;
}

export interface BlogPublicationJob {
  id: number;
  schedule_id: number;
  company_id: number;
  blog_id: number;
  revision_id: number;
  attempt_number: number;
  idempotency_key: string;
  status: string;
  worker_id?: string | null;
  was_delayed: boolean;
  started_at?: string | null;
  lease_until?: string | null;
  completed_at?: string | null;
  error_details?: string | null;
  external_reference?: string | null;
  created_at: string;
}

export interface BlogScheduleDetail extends BlogSchedule {
  events: BlogScheduleEvent[];
  publication_jobs: BlogPublicationJob[];
}

// WordPress
export interface WordPressConnection {
  id: number;
  company_id: number;
  site_url: string;
  username: string;
  status: string; // ACTIVE, INACTIVE
  default_post_status: "publish" | "draft";
  masked_credential: string;
  last_tested_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WordPressTestResponse {
  success: boolean;
  site_url: string;
  authenticated_user?: string | null;
  can_publish?: boolean | null;
  error_message?: string | null;
}

// Team Member
export interface TeamMember {
  id: number;
  name: string;
  email: string;
  status: string;
}
