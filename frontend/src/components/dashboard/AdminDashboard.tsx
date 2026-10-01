import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { BlogSummary } from "../../types";
import { Card, CardHeader, CardContent } from "../ui/Card";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { EmptyState } from "../ui/EmptyState";
import { AccessRequestsPanel } from "../domain/AccessRequestsPanel";
import { ArrowRight, FileText, Settings, Users, Activity } from "lucide-react";

interface AdminDashboardProps {
  blogs: BlogSummary[];
  companyName: string;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ blogs, companyName }) => {
  const navigate = useNavigate();
  
  const counts = {
    total: blogs.length,
    drafts: blogs.filter(b => b.status === "draft").length,
    pendingReview: blogs.filter(b => b.status === "pending_review").length,
    approved: blogs.filter(b => b.status === "approved").length,
    scheduled: blogs.filter(b => b.status === "scheduled").length,
    published: blogs.filter(b => b.status === "published").length,
  };

  return (
    <div className="space-y-6">
      {/* Admin Welcome */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-near-black tracking-tight">System Overview</h1>
            <span className="text-[10px] px-2 py-0.5 bg-red-100 text-red-800 border border-red-200 rounded font-mono uppercase font-bold">
              ADMINISTRATOR
            </span>
          </div>
          <p className="text-sm text-muted mt-1">
            Managing automated content and workspace settings for <strong>{companyName}</strong>.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button size="sm" variant="outline" leftIcon={<Settings className="w-4 h-4" />} onClick={() => navigate("/settings")}>
            Settings
          </Button>
          <Button size="sm" variant="outline" leftIcon={<Users className="w-4 h-4" />}>
            Manage Team
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 bg-surface border border-border rounded-lg shadow-subtle text-center">
              <p className="text-xs font-semibold uppercase text-muted tracking-wide">Total Content</p>
              <p className="text-3xl font-bold mt-2">{counts.total}</p>
            </div>
            <div className="p-4 bg-surface border border-border rounded-lg shadow-subtle text-center">
              <p className="text-xs font-semibold uppercase text-primary tracking-wide">Pending Review</p>
              <p className="text-3xl font-bold mt-2 text-primary">{counts.pendingReview}</p>
            </div>
            <div className="p-4 bg-surface border border-border rounded-lg shadow-subtle text-center">
              <p className="text-xs font-semibold uppercase text-muted tracking-wide">Scheduled</p>
              <p className="text-3xl font-bold mt-2">{counts.scheduled}</p>
            </div>
            <div className="p-4 bg-surface border border-border rounded-lg shadow-subtle text-center">
              <p className="text-xs font-semibold uppercase text-green-600 tracking-wide">Published</p>
              <p className="text-3xl font-bold mt-2 text-green-600">{counts.published}</p>
            </div>
          </div>

          {/* Access Requests */}
          <AccessRequestsPanel />

          {/* Recent Blogs */}
          <Card>
            <CardHeader
              title="Recent Activity"
              action={<Button size="sm" variant="ghost" onClick={() => navigate("/blogs")}>View All</Button>}
            />
            <CardContent className="p-0">
              {blogs.length === 0 ? (
                <EmptyState
                  icon={<Activity className="w-6 h-6" />}
                  title="No content activity yet"
                  description="Your team hasn't created any blogs."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-background border-b border-border text-[11px] font-semibold uppercase tracking-wider text-muted">
                      <tr>
                        <th className="py-3 px-4">Title</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {blogs.slice(0, 5).map((blog) => (
                        <tr key={blog.id} className="hover:bg-background/80 transition-colors">
                          <td className="py-3 px-4 font-medium text-near-black">
                            <Link to={`/blogs/${blog.id}`} className="hover:text-primary transition-colors line-clamp-1">
                              {blog.title}
                            </Link>
                          </td>
                          <td className="py-3 px-4"><StatusBadge status={blog.status} size="sm" /></td>
                          <td className="py-3 px-4 text-muted whitespace-nowrap">
                            {new Date(blog.created_at).toLocaleDateString()}
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

        {/* System Health / Status */}
        <div className="space-y-6">
          <Card>
            <CardHeader title="System Status" />
            <CardContent className="p-4 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-near-black">API Connection</span>
                <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div> Online
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-near-black">WordPress Integration</span>
                <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div> Connected
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-near-black">Auto-Publisher</span>
                <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div> Active
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader title="Admin Actions" />
            <CardContent className="p-4 space-y-2">
              <Button variant="outline" className="w-full justify-start text-sm" onClick={() => navigate("/wordpress")}>Configure WordPress</Button>
              <Button variant="outline" className="w-full justify-start text-sm" onClick={() => navigate("/schedule")}>Manage Schedule</Button>
              <Button variant="outline" className="w-full justify-start text-sm text-red-600 border-red-200 hover:bg-red-50">View Error Logs</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
