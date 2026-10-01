import React from "react";
import { useNavigate } from "react-router-dom";
import { BlogSummary } from "../../types";
import { Card, CardHeader, CardContent } from "../ui/Card";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { EmptyState } from "../ui/EmptyState";
import { Sparkles, Edit3, AlertCircle, FileText } from "lucide-react";

interface EditorDashboardProps {
  blogs: BlogSummary[];
  userName: string;
}

export const EditorDashboard: React.FC<EditorDashboardProps> = ({ blogs, userName }) => {
  const navigate = useNavigate();
  
  const drafts = blogs.filter(b => b.status === "draft");
  const changesRequested = blogs.filter(b => b.status === "changes_requested");
  const pendingReview = blogs.filter(b => b.status === "pending_review");
  const scheduled = blogs.filter(b => b.status === "scheduled");

  return (
    <div className="space-y-6">
      {/* Editor Welcome */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-gradient-to-r from-surface to-background p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <h1 className="text-2xl font-bold text-near-black tracking-tight">Editor Workspace</h1>
          <p className="text-sm text-muted mt-1">
            Welcome back, <strong>{userName}</strong>. Ready to create some engaging content?
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button size="lg" variant="dark" leftIcon={<Sparkles className="w-4 h-4 text-primary" />} onClick={() => navigate("/topics")}>
            Discover Topics
          </Button>
        </div>
      </div>

      {changesRequested.length > 0 && (
        <div className="p-4 bg-primary-light border-l-4 border-primary border-t border-r border-b rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-3 text-primary-dark">
            <AlertCircle className="w-6 h-6" />
            <div>
              <p className="text-sm font-bold">{changesRequested.length} draft(s) require your attention</p>
              <p className="text-xs">Reviewers have requested changes before these can be approved.</p>
            </div>
          </div>
          <Button size="sm" variant="primary" onClick={() => navigate("/blogs")}>View Feedback</Button>
        </div>
      )}

      {/* Editor Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-5 flex items-center gap-4">
            <div className="p-3 bg-gray-100 rounded-full"><Edit3 className="w-5 h-5 text-gray-600" /></div>
            <div>
              <p className="text-xs uppercase font-semibold text-muted tracking-wider">In Draft</p>
              <p className="text-2xl font-bold font-mono">{drafts.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5 flex items-center gap-4">
            <div className="p-3 bg-yellow-100 rounded-full"><AlertCircle className="w-5 h-5 text-yellow-600" /></div>
            <div>
              <p className="text-xs uppercase font-semibold text-muted tracking-wider">Revisions</p>
              <p className="text-2xl font-bold font-mono">{changesRequested.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5 flex items-center gap-4">
            <div className="p-3 bg-blue-100 rounded-full"><FileText className="w-5 h-5 text-blue-600" /></div>
            <div>
              <p className="text-xs uppercase font-semibold text-muted tracking-wider">In Review</p>
              <p className="text-2xl font-bold font-mono">{pendingReview.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5 flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-full"><Sparkles className="w-5 h-5 text-green-600" /></div>
            <div>
              <p className="text-xs uppercase font-semibold text-muted tracking-wider">Scheduled</p>
              <p className="text-2xl font-bold font-mono">{scheduled.length}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Active Work */}
      <Card>
        <CardHeader title="Your Active Drafts" description="Pick up where you left off" />
        <CardContent className="p-0">
          {drafts.length === 0 && changesRequested.length === 0 ? (
            <EmptyState
              icon={<Edit3 className="w-6 h-6" />}
              title="No active drafts"
              description="Start by selecting a topic from the Topic Intelligence board."
              actionLabel="Go to Topics"
              onAction={() => navigate("/topics")}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-background border-b border-border text-[11px] font-semibold uppercase tracking-wider text-muted">
                  <tr>
                    <th className="py-3 px-4">Title</th>
                    <th className="py-3 px-4">Keyword</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {[...changesRequested, ...drafts].map((blog) => (
                    <tr key={blog.id} className="hover:bg-background/80 transition-colors">
                      <td className="py-3 px-4 font-medium text-near-black truncate max-w-[200px]">{blog.title}</td>
                      <td className="py-3 px-4 text-muted font-mono">{blog.primary_keyword || "—"}</td>
                      <td className="py-3 px-4"><StatusBadge status={blog.status} size="sm" /></td>
                      <td className="py-3 px-4 text-right">
                        <Button size="sm" variant="outline" onClick={() => navigate(`/blogs/${blog.id}`)}>Edit</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
