import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { blogsApi } from "../api/blogs";
import { reviewsApi } from "../api/reviews";
import { schedulesApi } from "../api/schedules";
import {
  BlogDetail,
  BlogSchedule,
  BlogValidationResponse,
} from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/StatusBadge";
import { ValidationPanel } from "../components/domain/ValidationPanel";
import { ScheduleModal } from "../components/domain/ScheduleModal";
import { ReviewDecisionModal } from "../components/domain/ReviewDecisionModal";
import {
  ArrowLeft,
  Edit3,
  CheckSquare,
  Calendar,
  History,
  AlertCircle,
  FileText,
  RotateCcw,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";

export const BlogDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const blogId = Number(id);

  const { role } = useAuth();
  const { success, error: toastError } = useToast();
  const navigate = useNavigate();

  const [blog, setBlog] = useState<BlogDetail | null>(null);
  const [validation, setValidation] = useState<BlogValidationResponse | null>(null);
  const [schedules, setSchedules] = useState<BlogSchedule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isValidating, setIsValidating] = useState(false);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [isWithdrawing, setIsWithdrawing] = useState(false);
  const [isScheduleOpen, setIsScheduleOpen] = useState(false);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [isDecidingReview, setIsDecidingReview] = useState(false);

  const isEditor = role === "editor";
  const canReview = role === "reviewer" || role === "company_admin";

  const loadBlogData = async () => {
    if (!blogId) return;
    setIsLoading(true);
    try {
      const blogData = await blogsApi.getBlog(blogId);
      setBlog(blogData);

      // Attempt to load latest validation
      try {
        const valData = await blogsApi.getValidation(blogId);
        setValidation(valData);
      } catch {
        // Validation might not have run yet
      }

      // If approved or scheduled, check schedules
      try {
        const scheds = await schedulesApi.listBlogSchedules(blogId);
        setSchedules(scheds);
      } catch {
        // Ignore schedule listing failure if none
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
    loadBlogData();
  }, [blogId]);

  const handleValidate = async () => {
    setIsValidating(true);
    try {
      const val = await blogsApi.validateBlog(blogId);
      setValidation(val);
      success("Validation Executed", val.passed ? "All SEO and Format checks passed." : "Validation returned findings.");
    } catch (err: unknown) {
      toastError(
        "Validation Failed",
        err instanceof Error ? err.message : "Failed to run validation."
      );
    } finally {
      setIsValidating(false);
    }
  };

  const handleSubmitForReview = async () => {
    setIsSubmittingReview(true);
    try {
      await reviewsApi.submitForReview(blogId);
      success("Submitted for Review", "Phase 7 validation gating passed; draft submitted.");
      await loadBlogData();
    } catch (err: unknown) {
      toastError(
        "Submission Gated",
        err instanceof Error ? err.message : "Failed to submit for review."
      );
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const handleWithdrawReview = async () => {
    setIsWithdrawing(true);
    try {
      await reviewsApi.withdrawReview(blogId);
      success("Review Withdrawn", "Review cycle marked withdrawn; blog returned to draft.");
      await loadBlogData();
    } catch (err: unknown) {
      toastError(
        "Withdrawal Failed",
        err instanceof Error ? err.message : "Failed to withdraw review."
      );
    } finally {
      setIsWithdrawing(false);
    }
  };

  const handleDecisionSubmit = async (payload: {
    decision: any;
    feedback?: string;
    reviewer_comment?: string;
  }) => {
    setIsDecidingReview(true);
    try {
      const history = await reviewsApi.getReviewHistory(blogId);
      const pendingRev = history.find((r) => r.status === "pending") || history[0];
      if (pendingRev) {
        await reviewsApi.decideReview(blogId, pendingRev.id, payload);
        success("Review Decided", `Review decision '${payload.decision}' successfully processed.`);
        setIsReviewModalOpen(false);
        await loadBlogData();
      } else {
        toastError("Error", "No pending review cycle found for this blog.");
      }
    } catch (err: unknown) {
      toastError(
        "Decision Error",
        err instanceof Error ? err.message : "Failed to record review decision."
      );
    } finally {
      setIsDecidingReview(false);
    }
  };

  const handleScheduleSubmit = async (data: {
    local_scheduled_time: string;
    timezone: string;
    target_revision_id?: number;
  }) => {
    await schedulesApi.createSchedule(blogId, data);
    success("Publication Scheduled", `Scheduled for ${data.local_scheduled_time} (${data.timezone}).`);
    await loadBlogData();
  };

  if (isLoading) {
    return (
      <div className="p-8 space-y-4">
        <div className="h-6 bg-gray-200 animate-pulse rounded w-1/4" />
        <div className="h-40 bg-gray-200 animate-pulse rounded w-full" />
      </div>
    );
  }

  if (!blog) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-10 h-10 text-primary-dark mx-auto mb-3" />
        <h2 className="text-base font-semibold text-near-black">Blog Not Found</h2>
        <p className="text-xs text-muted mt-1 mb-4">
          The requested blog draft does not exist or belongs to another tenant.
        </p>
        <Button size="sm" variant="secondary" onClick={() => navigate("/blogs")}>
          Return to Blogs
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Navigation & Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => navigate("/blogs")}
            leftIcon={<ArrowLeft className="w-4 h-4" />}
          >
            Blogs
          </Button>
          <div className="h-4 w-px bg-border" />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-near-black tracking-tight line-clamp-1">
                {blog.title}
              </h1>
              <StatusBadge status={blog.status} size="sm" />
            </div>
            <p className="text-xs text-muted mt-0.5">
              Created {new Date(blog.created_at).toLocaleString()} • Primary Keyword:{" "}
              <strong className="text-near-black font-mono">
                {blog.primary_keyword || "—"}
              </strong>
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          {isEditor && (
            <Link to={`/blogs/${blog.id}/editor`}>
              <Button
                size="sm"
                variant="dark"
                leftIcon={<Edit3 className="w-3.5 h-3.5 text-primary" />}
              >
                Open Editor
              </Button>
            </Link>
          )}

          <Link to={`/blogs/${blog.id}/revisions`}>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<History className="w-3.5 h-3.5" />}
            >
              Revisions
            </Button>
          </Link>

          <Button
            size="sm"
            variant="outline"
            onClick={handleValidate}
            isLoading={isValidating}
            leftIcon={<ShieldCheck className="w-3.5 h-3.5" />}
          >
            Run Validation
          </Button>

          {isEditor &&
            (blog.status === "draft" || blog.status === "changes_requested") && (
              <Button
                size="sm"
                variant="primary"
                onClick={handleSubmitForReview}
                isLoading={isSubmittingReview}
                leftIcon={<CheckSquare className="w-3.5 h-3.5" />}
              >
                Submit Review
              </Button>
            )}

          {canReview && blog.status === "pending_review" && (
            <Button
              size="sm"
              variant="primary"
              onClick={() => setIsReviewModalOpen(true)}
              leftIcon={<CheckSquare className="w-3.5 h-3.5" />}
            >
              Review / Approve
            </Button>
          )}

          {(isEditor || role === "company_admin") &&
            blog.status === "pending_review" && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleWithdrawReview}
                isLoading={isWithdrawing}
                leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
              >
                Withdraw Review
              </Button>
            )}

          {blog.status === "approved" && (
            <Button
              size="sm"
              variant="primary"
              onClick={() => setIsScheduleOpen(true)}
              leftIcon={<Calendar className="w-3.5 h-3.5" />}
            >
              Schedule Publication
            </Button>
          )}
        </div>
      </div>

      {/* Grid: Article Preview & Metadata (2 columns) + Validation (1 column) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Article Details & Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* SEO Metadata Card */}
          <Card>
            <CardHeader
              title="SEO Metadata & Search Snippet"
              description="Phase 7 validated SERP attributes"
            />
            <CardContent className="space-y-3">
              <div className="p-3 bg-background border border-border rounded text-xs space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                  SEO Title
                </p>
                <p className="text-sm font-semibold text-near-black">
                  {blog.seo_title || blog.title}
                </p>
                <p className="text-[11px] text-muted font-mono">
                  Slug: /{blog.slug || "auto-generated"}
                </p>
                <p className="text-xs text-muted leading-relaxed pt-1">
                  {blog.meta_description || "No meta description specified."}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Rendered Content Card */}
          <Card>
            <CardHeader
              title="Article Content Preview"
              description="Generated AST and Markdown representation"
            />
            <CardContent className="prose max-w-none text-near-black">
              <div className="space-y-4">
                <h1 className="text-2xl font-bold tracking-tight text-near-black border-b border-border pb-3">
                  {blog.content_json?.h1_title || blog.title}
                </h1>

                {blog.content_json?.introduction && (
                  <div className="p-4 bg-background border-l-2 border-primary rounded text-sm text-near-black leading-relaxed italic">
                    {blog.content_json.introduction}
                  </div>
                )}

                {blog.content_json?.sections?.map((sec, idx) => (
                  <div key={idx} className="space-y-2 pt-2">
                    <h2 className="text-lg font-bold text-near-black">
                      {sec.heading}
                    </h2>
                    <p className="text-sm text-near-black leading-relaxed whitespace-pre-wrap">
                      {sec.content}
                    </p>
                  </div>
                ))}

                {blog.content_json?.conclusion && (
                  <div className="pt-4 border-t border-border space-y-2">
                    <h3 className="text-base font-bold text-near-black">
                      Conclusion
                    </h3>
                    <p className="text-sm text-near-black leading-relaxed whitespace-pre-wrap">
                      {blog.content_json.conclusion}
                    </p>
                  </div>
                )}

                {blog.content_json?.call_to_action && (
                  <div className="p-4 bg-surface border border-primary-border rounded-lg text-xs font-semibold text-primary-dark">
                    <strong>Call to Action:</strong> {blog.content_json.call_to_action}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Validation Panel & Publication Schedule */}
        <div className="space-y-6">
          <ValidationPanel validation={validation} isLoading={isValidating} />

          {/* Publication Schedule Summary */}
          {schedules.length > 0 && (
            <Card>
              <CardHeader
                title="Publication Schedules"
                description="Target publication jobs for this blog"
              />
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {schedules.map((sched) => (
                    <div key={sched.id} className="p-4 space-y-1 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-near-black">
                          Schedule #{sched.id}
                        </span>
                        <StatusBadge status={sched.status} size="sm" />
                      </div>
                      <p className="text-muted text-[11px]">
                        Target Time: {sched.local_scheduled_time} ({sched.timezone})
                      </p>
                      <p className="text-muted text-[11px]">
                        Target Revision: #{sched.target_revision_id}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Schedule Modal */}
      <ScheduleModal
        isOpen={isScheduleOpen}
        onClose={() => setIsScheduleOpen(false)}
        blogId={blog.id}
        blogTitle={blog.title}
        onSubmit={handleScheduleSubmit}
      />

      {/* Review Decision Modal */}
      {isReviewModalOpen && (
        <ReviewDecisionModal
          isOpen={isReviewModalOpen}
          onClose={() => setIsReviewModalOpen(false)}
          blogTitle={blog.title}
          revisionNumber={blog.content_json?.format_version ?? 1}
          onSubmit={handleDecisionSubmit}
          isLoading={isDecidingReview}
        />
      )}
    </div>
  );
};
