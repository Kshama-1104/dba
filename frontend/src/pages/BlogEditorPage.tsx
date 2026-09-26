import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { blogsApi } from "../api/blogs";
import { chatApi } from "../api/chat";
import { reviewsApi } from "../api/reviews";
import {
  BlogChatMessage,
  BlogDetail,
  BlogRevisionSummary,
  BlogValidationResponse,
  StructuredBlogDraft,
} from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { EditorChatPanel } from "../components/domain/EditorChatPanel";
import { ValidationPanel } from "../components/domain/ValidationPanel";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/StatusBadge";
import {
  ArrowLeft,
  CheckSquare,
  History,
  ShieldCheck,
  FileText,
  AlertCircle,
  Eye,
  Sliders,
  Sparkles,
} from "lucide-react";

export const BlogEditorPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const blogId = Number(id);

  const { role } = useAuth();
  const { success, error: toastError } = useToast();
  const navigate = useNavigate();

  const [blog, setBlog] = useState<BlogDetail | null>(null);
  const [messages, setMessages] = useState<BlogChatMessage[]>([]);
  const [revisions, setRevisions] = useState<BlogRevisionSummary[]>([]);
  const [validation, setValidation] = useState<BlogValidationResponse | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [activeTab, setActiveTab] = useState<"editor" | "validation">("editor");

  const isEditor = role === "editor";

  const loadData = async () => {
    if (!blogId) return;
    setIsLoading(true);
    try {
      const [blogData, chatThread, revList] = await Promise.all([
        blogsApi.getBlog(blogId),
        chatApi.getChatHistory(blogId).catch(() => ({ messages: [] })),
        chatApi.listRevisions(blogId).catch(() => []),
      ]);

      setBlog(blogData);
      setMessages(chatThread.messages || []);
      setRevisions(revList || []);

      // Load validation
      try {
        const valData = await blogsApi.getValidation(blogId);
        setValidation(valData);
      } catch {
        // Validation might not be loaded yet
      }
    } catch (err: unknown) {
      toastError(
        "Load Failed",
        err instanceof Error ? err.message : "Failed to load blog draft."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [blogId]);

  // Conversational Edit Handler (Phase 8)
  const handleSendChatMessage = async (messageText: string) => {
    if (!blog) return;
    setIsChatLoading(true);

    try {
      // Find latest revision id from revisions list or default to 0
      const latestRev = revisions.length > 0 ? revisions[revisions.length - 1] : null;
      const baseRevId = latestRev ? latestRev.id : 0;

      const resp = await chatApi.sendMessage(blogId, {
        message: messageText,
        base_revision_id: baseRevId,
        client_message_id: `msg-${Date.now()}`,
      });

      // Update chat messages
      setMessages((prev) => [...prev, resp.user_message, resp.assistant_message]);

      // If backend returned updated blog & revision, update state atomically
      if (resp.blog) {
        setBlog(resp.blog);
      }
      if (resp.revision) {
        setRevisions((prev) => [...prev, resp.revision!]);
      }
      if (resp.validation_report) {
        setValidation(resp.validation_report);
      }

      success(
        "Revision Applied",
        `Revision v${resp.revision?.revision_number ?? "updated"} created and validated.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Conversational revision failed.";
      toastError("Revision Gated", msg);
      throw err;
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleValidate = async () => {
    setIsValidating(true);
    try {
      const val = await blogsApi.validateBlog(blogId);
      setValidation(val);
      success("Validation Executed", val.passed ? "All SEO & Format checks passed." : "Findings detected.");
    } catch (err: unknown) {
      toastError(
        "Validation Failed",
        err instanceof Error ? err.message : "Failed to run validation."
      );
    } finally {
      setIsValidating(false);
    }
  };

  const handleSubmitReview = async () => {
    setIsSubmittingReview(true);
    try {
      await reviewsApi.submitForReview(blogId);
      success("Submitted for Review", "Phase 7 validation passed; blog submitted to reviewer queue.");
      navigate(`/blogs/${blogId}`);
    } catch (err: unknown) {
      toastError(
        "Submission Gated",
        err instanceof Error ? err.message : "Failed to submit for review."
      );
    } finally {
      setIsSubmittingReview(false);
    }
  };

  // Compute live word count
  const draftContent: StructuredBlogDraft | undefined = blog?.content_json;
  const calculateWordCount = (): number => {
    if (!draftContent) return 0;
    const text = [
      draftContent.h1_title,
      draftContent.introduction,
      ...(draftContent.sections || []).map((s) => `${s.heading} ${s.content}`),
      draftContent.conclusion,
      draftContent.call_to_action,
    ].join(" ");
    return text.trim().split(/\s+/).filter(Boolean).length;
  };

  if (isLoading) {
    return (
      <div className="p-8 space-y-4">
        <div className="h-6 bg-gray-200 animate-pulse rounded w-1/4" />
        <div className="h-80 bg-gray-200 animate-pulse rounded w-full" />
      </div>
    );
  }

  if (!blog) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-10 h-10 text-primary-dark mx-auto mb-3" />
        <h2 className="text-base font-semibold text-near-black">Draft Not Found</h2>
        <Button size="sm" variant="secondary" onClick={() => navigate("/blogs")} className="mt-3">
          Return to Blogs
        </Button>
      </div>
    );
  }

  const latestRevision = revisions.length > 0 ? revisions[revisions.length - 1] : null;

  return (
    <div className="space-y-6">
      {/* Top Navigation & Status Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-4 border border-border rounded-lg shadow-subtle">
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => navigate(`/blogs/${blog.id}`)}
            leftIcon={<ArrowLeft className="w-4 h-4" />}
          >
            Overview
          </Button>
          <div className="h-4 w-px bg-border" />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-near-black tracking-tight line-clamp-1">
                {blog.title}
              </h1>
              <StatusBadge status={blog.status} size="sm" />
            </div>
            <p className="text-[11px] text-muted">
              Revision:{" "}
              <strong className="text-near-black font-mono">
                v{latestRevision?.revision_number ?? 0}
              </strong>{" "}
              • Words:{" "}
              <strong className="text-near-black font-mono">
                {calculateWordCount()}
              </strong>{" "}
              • Primary Keyword:{" "}
              <strong className="text-near-black font-mono">
                {blog.primary_keyword || "—"}
              </strong>
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleValidate}
            isLoading={isValidating}
            leftIcon={<ShieldCheck className="w-3.5 h-3.5" />}
          >
            Validate
          </Button>

          <Link to={`/blogs/${blog.id}/revisions`}>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<History className="w-3.5 h-3.5" />}
            >
              Revision History
            </Button>
          </Link>

          {isEditor &&
            (blog.status === "draft" || blog.status === "changes_requested") && (
              <Button
                size="sm"
                variant="primary"
                onClick={handleSubmitReview}
                isLoading={isSubmittingReview}
                leftIcon={<CheckSquare className="w-3.5 h-3.5" />}
              >
                Submit for Review
              </Button>
            )}
        </div>
      </div>

      {/* Editor Main Grid: Structured Article Editor (Left) & Chat Assistant (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Structured Article Editor (7 columns) */}
        <div className="lg:col-span-7 space-y-6">
          {/* SEO Metadata Box */}
          <div className="p-4 bg-surface border border-border rounded-lg shadow-subtle space-y-3">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-primary" />
                SEO Metadata &amp; SERP Target
              </span>
              <span className="text-[11px] text-muted font-mono">
                {draftContent?.primary_keyword ? `Target: ${draftContent.primary_keyword}` : "No keyword"}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-muted block mb-1">
                  SEO Title
                </label>
                <div className="p-2.5 bg-background border border-border rounded font-medium text-near-black">
                  {draftContent?.seo_title || blog.title}
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-muted block mb-1">
                  Primary Keyword
                </label>
                <div className="p-2.5 bg-background border border-border rounded font-mono text-near-black">
                  {draftContent?.primary_keyword || blog.primary_keyword || "—"}
                </div>
              </div>
            </div>

            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted block mb-1">
                Meta Description
              </label>
              <div className="p-2.5 bg-background border border-border rounded text-xs text-muted leading-relaxed">
                {draftContent?.meta_description || "No meta description specified."}
              </div>
            </div>
          </div>

          {/* Structured Article Sections */}
          <div className="p-6 bg-surface border border-border rounded-lg shadow-subtle space-y-6">
            {/* H1 Title */}
            <div className="space-y-1">
              <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-primary px-1.5 py-0.5 bg-primary-light rounded border border-primary-border inline-block">
                H1 Title
              </span>
              <h2 className="text-2xl font-bold tracking-tight text-near-black pt-1">
                {draftContent?.h1_title || blog.title}
              </h2>
            </div>

            {/* Introduction */}
            <div className="space-y-1 pt-2 border-t border-border">
              <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-muted px-1.5 py-0.5 bg-background border border-border rounded inline-block">
                Introduction
              </span>
              <p className="text-xs text-near-black leading-relaxed whitespace-pre-wrap p-3.5 bg-background/50 border-l-2 border-primary rounded-r">
                {draftContent?.introduction || "No introduction."}
              </p>
            </div>

            {/* Body Sections */}
            {draftContent?.sections?.map((section, idx) => (
              <div key={idx} className="space-y-2 pt-4 border-t border-border">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-muted px-1.5 py-0.5 bg-background border border-border rounded">
                    H{section.level} Section {idx + 1}
                  </span>
                  <h3 className="text-base font-bold text-near-black">
                    {section.heading}
                  </h3>
                </div>
                <p className="text-xs text-near-black leading-relaxed whitespace-pre-wrap pl-1">
                  {section.content}
                </p>
              </div>
            ))}

            {/* Conclusion */}
            <div className="space-y-2 pt-4 border-t border-border">
              <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-muted px-1.5 py-0.5 bg-background border border-border rounded inline-block">
                Conclusion
              </span>
              <p className="text-xs text-near-black leading-relaxed whitespace-pre-wrap pl-1">
                {draftContent?.conclusion || "No conclusion."}
              </p>
            </div>

            {/* CTA */}
            {draftContent?.call_to_action && (
              <div className="p-3.5 bg-primary-light border border-primary-border rounded text-xs text-primary-dark font-medium">
                <strong className="block text-[11px] uppercase tracking-wider mb-0.5">
                  Call to Action Directive:
                </strong>
                {draftContent.call_to_action}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: AI Co-Author Chat & Validation (5 columns) */}
        <div className="lg:col-span-5 space-y-6 sticky top-20">
          <div className="flex border-b border-border gap-4 text-xs font-semibold uppercase tracking-wider">
            <button
              onClick={() => setActiveTab("editor")}
              className={`pb-2 border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === "editor"
                  ? "border-primary text-near-black"
                  : "border-transparent text-muted hover:text-near-black"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-primary" />
              <span>AI Assistant Chat</span>
            </button>
            <button
              onClick={() => setActiveTab("validation")}
              className={`pb-2 border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === "validation"
                  ? "border-primary text-near-black"
                  : "border-transparent text-muted hover:text-near-black"
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-primary" />
              <span>SEO &amp; Format Validation</span>
              {validation && (
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                    validation.passed
                      ? "bg-black text-white"
                      : "bg-primary-light text-primary-dark"
                  }`}
                >
                  {validation.passed ? "PASS" : "FAIL"}
                </span>
              )}
            </button>
          </div>

          {activeTab === "editor" ? (
            <EditorChatPanel
              messages={messages}
              onSendMessage={handleSendChatMessage}
              isLoading={isChatLoading}
              latestRevisionNumber={latestRevision?.revision_number}
              onViewRevisions={() => navigate(`/blogs/${blog.id}/revisions`)}
              readOnly={!isEditor}
            />
          ) : (
            <ValidationPanel validation={validation} isLoading={isValidating} />
          )}
        </div>
      </div>
    </div>
  );
};
