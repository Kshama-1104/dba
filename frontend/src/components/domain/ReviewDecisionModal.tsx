import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Textarea } from "../ui/Textarea";
import { Button } from "../ui/Button";
import { ReviewDecision } from "../../types";
import { CheckCircle2, RefreshCw, XCircle, AlertCircle } from "lucide-react";

export interface ReviewDecisionModalProps {
  isOpen: boolean;
  onClose: () => void;
  blogTitle: string;
  revisionNumber: number;
  onSubmit: (decision: {
    decision: ReviewDecision;
    feedback?: string;
    reviewer_comment?: string;
  }) => Promise<void>;
  isLoading?: boolean;
}

export const ReviewDecisionModal: React.FC<ReviewDecisionModalProps> = ({
  isOpen,
  onClose,
  blogTitle,
  revisionNumber,
  onSubmit,
  isLoading = false,
}) => {
  const [decision, setDecision] = useState<ReviewDecision>("approve");
  const [feedback, setFeedback] = useState("");
  const [reviewerComment, setReviewerComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (decision === "request_changes" && !feedback.trim()) {
      setError("Editorial feedback is mandatory when requesting changes.");
      return;
    }

    if (decision === "reject" && !feedback.trim() && !reviewerComment.trim()) {
      setError("Reviewer feedback or comment is mandatory when rejecting a draft.");
      return;
    }

    try {
      await onSubmit({
        decision,
        feedback: feedback.trim() || undefined,
        reviewer_comment: reviewerComment.trim() || feedback.trim() || undefined,
      });
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to record review decision.");
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Editorial Review Decision"
      description={`Draft: "${blogTitle}" (Revision v${revisionNumber})`}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Decision Selector */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-2">
            Select Decision
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <button
              type="button"
              onClick={() => setDecision("approve")}
              className={`p-3 rounded-lg border text-left flex items-start gap-2.5 transition-all ${
                decision === "approve"
                  ? "bg-near-black text-white border-black"
                  : "bg-surface text-near-black border-border hover:border-gray-400"
              }`}
            >
              <CheckCircle2
                className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                  decision === "approve" ? "text-primary" : "text-muted"
                }`}
              />
              <div>
                <p className="text-xs font-semibold">Approve</p>
                <p
                  className={`text-[10px] mt-0.5 leading-tight ${
                    decision === "approve" ? "text-gray-300" : "text-muted"
                  }`}
                >
                  Ready for scheduling &amp; publishing
                </p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setDecision("request_changes")}
              className={`p-3 rounded-lg border text-left flex items-start gap-2.5 transition-all ${
                decision === "request_changes"
                  ? "bg-near-black text-white border-black"
                  : "bg-surface text-near-black border-border hover:border-gray-400"
              }`}
            >
              <RefreshCw
                className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                  decision === "request_changes"
                    ? "text-primary"
                    : "text-muted"
                }`}
              />
              <div>
                <p className="text-xs font-semibold">Request Changes</p>
                <p
                  className={`text-[10px] mt-0.5 leading-tight ${
                    decision === "request_changes"
                      ? "text-gray-300"
                      : "text-muted"
                  }`}
                >
                  Inject feedback into Editor Chat
                </p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setDecision("reject")}
              className={`p-3 rounded-lg border text-left flex items-start gap-2.5 transition-all ${
                decision === "reject"
                  ? "bg-near-black text-white border-black"
                  : "bg-surface text-near-black border-border hover:border-gray-400"
              }`}
            >
              <XCircle
                className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                  decision === "reject" ? "text-primary" : "text-muted"
                }`}
              />
              <div>
                <p className="text-xs font-semibold">Reject</p>
                <p
                  className={`text-[10px] mt-0.5 leading-tight ${
                    decision === "reject" ? "text-gray-300" : "text-muted"
                  }`}
                >
                  Reject draft lifecycle
                </p>
              </div>
            </button>
          </div>
        </div>

        {/* Feedback / Comment Field */}
        <div>
          <Textarea
            label={
              decision === "request_changes"
                ? "Revision Feedback (Mandatory)"
                : decision === "reject"
                ? "Rejection Reason / Feedback (Mandatory)"
                : "Feedback / Comment"
            }
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder={
              decision === "request_changes"
                ? "Specify necessary edits (e.g. rewrite section 2 with concrete figures, expand conclusion)..."
                : decision === "reject"
                ? "Specify why this article cannot proceed..."
                : "e.g. Excellent technical depth and brand alignment. Approved for publishing."
            }
            rows={3}
          />
          <p className="text-[11px] text-muted mt-1 leading-relaxed">
            {decision === "request_changes"
              ? "This feedback is automatically injected into the Phase 8 Editor Chat for the author."
              : decision === "reject"
              ? "Provides audit context on why the blog did not meet standards."
              : "Reviewer approval feedback recorded with the review decision."}
          </p>
        </div>

        {error && (
          <div className="p-3 bg-primary-light border border-primary-border rounded text-xs text-primary-dark flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant={decision === "approve" ? "dark" : "primary"}
            size="sm"
            isLoading={isLoading}
          >
            Submit Decision
          </Button>
        </div>
      </form>
    </Modal>
  );
};
