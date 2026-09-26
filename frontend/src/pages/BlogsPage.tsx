import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { blogsApi } from "../api/blogs";
import { topicsApi } from "../api/topics";
import { reviewsApi } from "../api/reviews";
import { BlogStatus, BlogSummary, TopicCandidate } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { Textarea } from "../components/ui/Textarea";
import { StatusBadge } from "../components/ui/StatusBadge";
import { Modal } from "../components/ui/Modal";
import { EmptyState } from "../components/ui/EmptyState";
import {
  FileText,
  Sparkles,
  Edit3,
  CheckSquare,
  Calendar,
  AlertCircle,
  Clock,
  Filter,
} from "lucide-react";

export const BlogsPage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [blogs, setBlogs] = useState<BlogSummary[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Generate Blog Modal state
  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [selectedTopics, setSelectedTopics] = useState<TopicCandidate[]>([]);
  const [targetTopicId, setTargetTopicId] = useState<string>("");
  const [editorInstruction, setEditorInstruction] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  // Submit for Review state
  const [submittingBlogId, setSubmittingBlogId] = useState<number | null>(null);

  const isEditor = role === "editor";
  const canReview = role === "reviewer" || role === "company_admin";

  const loadBlogs = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await blogsApi.listBlogs({
        status: statusFilter !== "ALL" ? (statusFilter as BlogStatus) : undefined,
        limit: 50,
      });
      setBlogs(data);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to load blog drafts."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadBlogs();
  }, [statusFilter]);

  // Handle URL query parameter `generateTopicId`
  useEffect(() => {
    const topicParam = searchParams.get("generateTopicId");
    if (topicParam) {
      setTargetTopicId(topicParam);
      setIsGenerateOpen(true);
    }
  }, [searchParams]);

  // Load selected topics when opening generate modal
  const openGenerateModal = async () => {
    if (!isEditor) return;
    setIsGenerateOpen(true);
    try {
      const candidates = await topicsApi.listTopics("selected");
      setSelectedTopics(candidates);
      if (candidates.length > 0 && !targetTopicId) {
        setTargetTopicId(String(candidates[0].id));
      }
    } catch {
      // Fallback
    }
  };

  const handleGenerateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetTopicId || !isEditor) return;
    setIsGenerating(true);

    try {
      const blogDetail = await blogsApi.generateBlog({
        topic_candidate_id: Number(targetTopicId),
        editor_instruction: editorInstruction.trim() || undefined,
      });
      success(
        "Blog Generated",
        `Draft "${blogDetail.title}" created with deterministic SEO and format baseline.`
      );
      setIsGenerateOpen(false);
      navigate(`/blogs/${blogDetail.id}/editor`);
    } catch (err: unknown) {
      toastError(
        "Generation Failed",
        err instanceof Error ? err.message : "Failed to generate blog draft."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSubmitForReview = async (blogId: number) => {
    setSubmittingBlogId(blogId);
    try {
      await reviewsApi.submitForReview(blogId);
      success("Submitted for Review", "Phase 7 validation passed; review cycle submitted.");
      await loadBlogs();
    } catch (err: unknown) {
      toastError(
        "Submission Gated",
        err instanceof Error
          ? err.message
          : "Failed to submit for review. Check Phase 7 validation."
      );
    } finally {
      setSubmittingBlogId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Blog Content Management
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 6 structured blog drafts. Generated from confirmed topics through RAG grounding, memory precedence, and deterministic validation.
          </p>
        </div>

        {isEditor && (
          <Button
            size="sm"
            variant="primary"
            onClick={openGenerateModal}
            leftIcon={<Sparkles className="w-3.5 h-3.5" />}
          >
            Generate New Blog
          </Button>
        )}
      </div>

      {errorMessage && (
        <div className="p-4 bg-primary-light border border-primary-border rounded-lg text-xs text-primary-dark flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center justify-between bg-surface p-4 border border-border rounded-lg shadow-subtle">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted">
          <Filter className="w-4 h-4 text-primary" />
          <span>Filter Status:</span>
        </div>
        <div className="w-56">
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            options={[
              { label: "All Statuses", value: "ALL" },
              { label: "Draft", value: "draft" },
              { label: "Pending Review", value: "pending_review" },
              { label: "Changes Requested", value: "changes_requested" },
              { label: "Approved", value: "approved" },
              { label: "Scheduled", value: "scheduled" },
              { label: "Publishing", value: "publishing" },
              { label: "Published", value: "published" },
              { label: "Failed", value: "failed" },
            ]}
          />
        </div>
      </div>

      {/* Blogs Table */}
      <Card>
        <CardHeader
          title={`Corporate Content Articles (${blogs.length})`}
          description="Tenant-isolated editorial catalog"
        />
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 space-y-3">
              <div className="h-4 bg-gray-200 animate-pulse rounded w-3/4" />
              <div className="h-4 bg-gray-200 animate-pulse rounded w-1/2" />
            </div>
          ) : blogs.length === 0 ? (
            <EmptyState
              icon={<FileText className="w-6 h-6" />}
              title="No blogs match the current status filter."
              description="Confirm topic candidates or initiate generation to produce enterprise articles."
              actionLabel={isEditor ? "Generate Blog" : undefined}
              onAction={isEditor ? openGenerateModal : undefined}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-background border-b border-border text-[11px] font-semibold uppercase tracking-wider text-muted">
                  <tr>
                    <th className="py-3 px-4">Title</th>
                    <th className="py-3 px-4">Primary Keyword</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Created At</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {blogs.map((blog) => (
                    <tr
                      key={blog.id}
                      className="hover:bg-background/80 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <Link
                          to={`/blogs/${blog.id}`}
                          className="font-semibold text-near-black hover:text-primary transition-colors block line-clamp-1"
                        >
                          {blog.title}
                        </Link>
                      </td>
                      <td className="py-3 px-4 text-muted font-mono">
                        {blog.primary_keyword || "—"}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={blog.status} size="sm" />
                      </td>
                      <td className="py-3 px-4 text-muted whitespace-nowrap">
                        {new Date(blog.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            to={`/blogs/${blog.id}`}
                            className="p-1.5 text-muted hover:text-near-black hover:bg-gray-100 rounded transition-colors text-xs font-medium"
                            title="View blog details"
                          >
                            Overview
                          </Link>

                          {isEditor && (
                            <Link
                              to={`/blogs/${blog.id}/editor`}
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-surface border border-border hover:border-gray-400 rounded text-xs font-semibold text-near-black transition-colors"
                              title="Open structured article editor"
                            >
                              <Edit3 className="w-3.5 h-3.5 text-primary" />
                              Editor
                            </Link>
                          )}

                          {isEditor &&
                            (blog.status === "draft" ||
                              blog.status === "changes_requested") && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleSubmitForReview(blog.id)}
                                isLoading={submittingBlogId === blog.id}
                                leftIcon={<CheckSquare className="w-3.5 h-3.5" />}
                              >
                                Submit Review
                              </Button>
                            )}

                          {blog.status === "approved" && (
                            <Link
                              to={`/schedule?blogId=${blog.id}`}
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-primary text-white rounded text-xs font-semibold hover:bg-primary-dark transition-colors"
                              title="Schedule publication"
                            >
                              <Calendar className="w-3.5 h-3.5" />
                              Schedule
                            </Link>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Generate Blog Modal */}
      <Modal
        isOpen={isGenerateOpen}
        onClose={() => setIsGenerateOpen(false)}
        title="Generate Structured Blog Draft"
        description="Phase 6 synthesis: multi-source context assembly, structural outline planning, draft synthesis, and Phase 7 validation gating."
        maxWidth="lg"
      >
        <form onSubmit={handleGenerateSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-1.5">
              Select Confirmed Topic Candidate (Status: Selected)
            </label>
            {selectedTopics.length > 0 ? (
              <Select
                value={targetTopicId}
                onChange={(e) => setTargetTopicId(e.target.value)}
                options={selectedTopics.map((t) => ({
                  label: `${t.title} [Keyword: ${t.primary_keyword}]`,
                  value: t.id,
                }))}
                required
              />
            ) : (
              <div className="p-3 bg-background border border-border rounded text-xs text-muted flex items-center justify-between">
                <span>No topics currently in &quot;SELECTED&quot; state.</span>
                <Link
                  to="/topics"
                  className="font-semibold text-primary hover:underline"
                >
                  Go to Topics &rarr;
                </Link>
              </div>
            )}
          </div>

          <Textarea
            label="Optional Editor Instruction"
            placeholder="e.g. Emphasize multi-cloud resilience and cite customer case studies..."
            value={editorInstruction}
            onChange={(e) => setEditorInstruction(e.target.value)}
            rows={3}
            helperText="Provides steering instructions for the article planning phase."
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsGenerateOpen(false)}
              disabled={isGenerating}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isGenerating}
              disabled={!targetTopicId}
              leftIcon={<Sparkles className="w-3.5 h-3.5" />}
            >
              {isGenerating ? "Synthesizing Draft..." : "Generate Blog Draft"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
