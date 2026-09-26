import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { reviewsApi } from "../api/reviews";
import { PendingReviewItem, ReviewDecision } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { ReviewDecisionModal } from "../components/domain/ReviewDecisionModal";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/StatusBadge";
import { EmptyState } from "../components/ui/EmptyState";
import {
  CheckSquare,
  CheckCircle2,
  RefreshCw,
  XCircle,
  Clock,
  Eye,
  AlertCircle,
  Shield,
} from "lucide-react";

export const ReviewsPage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();

  const [pendingReviews, setPendingReviews] = useState<PendingReviewItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedReview, setSelectedReview] = useState<PendingReviewItem | null>(null);
  const [isDeciding, setIsDeciding] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const canDecide = role === "reviewer" || role === "company_admin";

  const loadPendingReviews = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      if (canDecide) {
        const data = await reviewsApi.listPendingReviews(0, 50);
        setPendingReviews(data);
      } else {
        // If user is Editor, pending review queue is restricted to Reviewer/Admin
        setPendingReviews([]);
      }
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to load pending reviews."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPendingReviews();
  }, [role]);

  const handleDecisionSubmit = async (payload: {
    decision: ReviewDecision;
    feedback?: string;
    reviewer_comment?: string;
  }) => {
    if (!selectedReview) return;
    setIsDeciding(true);

    try {
      await reviewsApi.decideReview(
        selectedReview.blog_id,
        selectedReview.review_id,
        payload
      );

      const decisionLabels = {
        approve: "Blog draft approved for publication scheduling.",
        request_changes: "Feedback injected into Editor Chat thread.",
        reject: "Blog draft rejected.",
      };

      success("Review Decided", decisionLabels[payload.decision]);
      setSelectedReview(null);
      await loadPendingReviews();
    } catch (err: unknown) {
      toastError(
        "Decision Error",
        err instanceof Error ? err.message : "Failed to submit review decision."
      );
    } finally {
      setIsDeciding(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <CheckSquare className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Editorial Governance &amp; Review Queue
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 9 Human Reviewer Workflow. Enforces Separation of Duties (SoD) and deterministic Phase 7 format/SEO gating before publication.
          </p>
        </div>

        {!canDecide && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-background border border-border rounded text-xs text-muted">
            <Shield className="w-3.5 h-3.5" />
            <span>Reviewer / Admin role required to decide review queue</span>
          </div>
        )}
      </div>

      {errorMessage && (
        <div className="p-4 bg-primary-light border border-primary-border rounded-lg text-xs text-primary-dark flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Pending Reviews Queue Table */}
      <Card>
        <CardHeader
          title={`Shared Reviewer Queue (${pendingReviews.length} Pending)`}
          description="FIFO ordered submissions awaiting human editorial decision"
        />
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 space-y-3">
              <div className="h-4 bg-gray-200 animate-pulse rounded w-3/4" />
              <div className="h-4 bg-gray-200 animate-pulse rounded w-1/2" />
            </div>
          ) : pendingReviews.length === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="w-6 h-6" />}
              title="You're all caught up."
              description="No blog drafts are currently waiting in the editorial review queue."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-background border-b border-border text-[11px] font-semibold uppercase tracking-wider text-muted">
                  <tr>
                    <th className="py-3 px-4">Blog Title</th>
                    <th className="py-3 px-4">Submitted Revision</th>
                    <th className="py-3 px-4">Author Note</th>
                    <th className="py-3 px-4">Submitted Time</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {pendingReviews.map((item) => (
                    <tr
                      key={item.review_id}
                      className="hover:bg-background/80 transition-colors"
                    >
                      <td className="py-3 px-4 font-semibold text-near-black">
                        <Link
                          to={`/blogs/${item.blog_id}`}
                          className="hover:text-primary transition-colors block line-clamp-1"
                        >
                          {item.blog_title}
                        </Link>
                      </td>
                      <td className="py-3 px-4 font-mono">
                        <span className="px-2 py-0.5 bg-background border border-border rounded text-[11px]">
                          v{item.submitted_revision_number} (Snapshot #{item.submitted_revision_id})
                        </span>
                      </td>
                      <td className="py-3 px-4 text-muted max-w-xs truncate">
                        {item.submission_note || "—"}
                      </td>
                      <td className="py-3 px-4 text-muted whitespace-nowrap">
                        {new Date(item.submitted_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={item.status} size="sm" />
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            to={`/blogs/${item.blog_id}`}
                            className="p-1.5 text-muted hover:text-near-black hover:bg-gray-100 rounded transition-colors text-xs font-medium"
                          >
                            Inspect
                          </Link>

                          {canDecide && (
                            <Button
                              size="sm"
                              variant="primary"
                              onClick={() => setSelectedReview(item)}
                              leftIcon={<CheckSquare className="w-3.5 h-3.5" />}
                            >
                              Review
                            </Button>
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

      {/* Review Decision Modal */}
      {selectedReview && (
        <ReviewDecisionModal
          isOpen={!!selectedReview}
          onClose={() => setSelectedReview(null)}
          blogTitle={selectedReview.blog_title}
          revisionNumber={selectedReview.submitted_revision_number}
          onSubmit={handleDecisionSubmit}
          isLoading={isDeciding}
        />
      )}
    </div>
  );
};
