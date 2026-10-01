import React from "react";
import { useNavigate } from "react-router-dom";
import { BlogSummary, PendingReviewItem } from "../../types";
import { Card, CardHeader, CardContent } from "../ui/Card";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { EmptyState } from "../ui/EmptyState";
import { CheckSquare, ArrowRight, Clock, CheckCircle } from "lucide-react";

interface ReviewerDashboardProps {
  blogs: BlogSummary[];
  pendingReviews: PendingReviewItem[];
  userName: string;
}

export const ReviewerDashboard: React.FC<ReviewerDashboardProps> = ({ 
  blogs, 
  pendingReviews,
  userName 
}) => {
  const navigate = useNavigate();
  
  const approved = blogs.filter(b => b.status === "approved" || b.status === "scheduled" || b.status === "published");

  return (
    <div className="space-y-6">
      {/* Reviewer Welcome */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-gradient-to-br from-surface to-background p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <h1 className="text-2xl font-bold text-near-black tracking-tight">Governance Workspace</h1>
          <p className="text-sm text-muted mt-1">
            Welcome back, <strong>{userName}</strong>. Ensure content meets our standards before it goes live.
          </p>
        </div>
      </div>

      {pendingReviews.length > 0 && (
        <div className="p-5 bg-surface border-l-4 border-primary border-t border-r border-b rounded-lg shadow-subtle flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary-light text-primary-dark rounded-full">
              <Clock className="w-6 h-6" />
            </div>
            <div>
              <p className="text-lg font-bold text-near-black">
                {pendingReviews.length} blog{pendingReviews.length > 1 ? "s" : ""} waiting for approval
              </p>
              <p className="text-sm text-muted">
                Review submissions, verify Phase 7 validation, and approve or request changes.
              </p>
            </div>
          </div>
          <Button
            size="lg"
            variant="primary"
            onClick={() => navigate("/reviews")}
            rightIcon={<ArrowRight className="w-4 h-4" />}
          >
            Start Reviewing
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Pending Reviews List */}
        <Card className="flex flex-col h-full">
          <CardHeader 
            title="Pending Queue" 
            description="Content needing your attention right now"
            action={
              <Button size="sm" variant="outline" onClick={() => navigate("/reviews")}>
                View All
              </Button>
            }
          />
          <CardContent className="flex-1 p-0">
            {pendingReviews.length === 0 ? (
              <EmptyState
                icon={<CheckCircle className="w-8 h-8 text-green-500" />}
                title="All caught up!"
                description="There are no blogs waiting for your review at the moment."
              />
            ) : (
              <div className="divide-y divide-border">
                {pendingReviews.map((review) => (
                  <div key={review.review_id} className="p-4 hover:bg-background/50 transition-colors flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-near-black truncate max-w-[200px] sm:max-w-[300px]">
                        {review.blog_title}
                      </p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-muted">
                        <span>By User #{review.submitted_by_user_id ?? "Unknown"}</span>
                        <span>•</span>
                        <span>{new Date(review.submitted_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <Button 
                      size="sm" 
                      variant="dark" 
                      onClick={() => navigate("/reviews")}
                    >
                      Review
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recently Approved */}
        <Card className="flex flex-col h-full">
          <CardHeader title="Recently Approved" description="Your past approvals" />
          <CardContent className="flex-1 p-0">
            {approved.length === 0 ? (
              <div className="p-8 text-center text-muted text-sm">
                No approved content yet.
              </div>
            ) : (
              <div className="divide-y divide-border">
                {approved.slice(0, 5).map((blog) => (
                  <div key={blog.id} className="p-4 flex items-center justify-between">
                    <p className="font-medium text-sm text-near-black truncate max-w-[250px]">{blog.title}</p>
                    <StatusBadge status={blog.status} size="sm" />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lifecycle Workflow Progression Card */}
      <Card>
        <CardHeader
          title="Publishing Pipeline Status"
          description="Where we are in the flow"
        />
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-center text-xs">
            <div className="p-3 bg-background border border-border rounded opacity-50">
              <span className="block font-semibold text-near-black mb-1">1. Topics</span>
            </div>
            <div className="p-3 bg-background border border-border rounded opacity-50">
              <span className="block font-semibold text-near-black mb-1">2. Synthesis</span>
            </div>
            <div className="p-3 bg-background border border-border rounded opacity-50">
              <span className="block font-semibold text-near-black mb-1">3. Validation</span>
            </div>
            <div className="p-3 bg-primary-light border border-primary rounded ring-1 ring-primary">
              <span className="block font-bold text-primary-dark mb-1">4. Review</span>
              <span className="text-[11px] text-primary-dark">Your Domain</span>
            </div>
            <div className="p-3 bg-background border border-border rounded">
              <span className="block font-semibold text-near-black mb-1">5. Scheduling</span>
            </div>
            <div className="p-3 bg-background border border-border rounded">
              <span className="block font-semibold text-near-black mb-1">6. Publish</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
