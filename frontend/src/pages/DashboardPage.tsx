import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { blogsApi } from "../api/blogs";
import { reviewsApi } from "../api/reviews";
import { BlogSummary, PendingReviewItem } from "../types";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/StatusBadge";
import { EmptyState } from "../components/ui/EmptyState";
import { AccessRequestsPanel } from "../components/domain/AccessRequestsPanel";
import {
  FileText,
  CheckSquare,
  Sparkles,
  Calendar,
  ArrowRight,
  TrendingUp,
  AlertCircle,
  Clock,
} from "lucide-react";

import { AdminDashboard } from "../components/dashboard/AdminDashboard";
import { EditorDashboard } from "../components/dashboard/EditorDashboard";
import { ReviewerDashboard } from "../components/dashboard/ReviewerDashboard";

export const DashboardPage: React.FC = () => {
  const { user, role, company } = useAuth();
  
  const [blogs, setBlogs] = useState<BlogSummary[]>([]);
  const [pendingReviews, setPendingReviews] = useState<PendingReviewItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadDashboardData() {
      setIsLoading(true);
      setError(null);
      try {
        const blogsData = await blogsApi.listBlogs({ limit: 50 });
        if (isMounted) {
          setBlogs(blogsData);
        }

        if (role === "company_admin" || role === "reviewer") {
          try {
            const pendingData = await reviewsApi.listPendingReviews(0, 10);
            if (isMounted) {
              setPendingReviews(pendingData);
            }
          } catch {
            // Ignore if reviews call fails or empty
          }
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load dashboard metrics."
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadDashboardData();
    return () => {
      isMounted = false;
    };
  }, [role]);

  if (isLoading) {
    return <div className="p-8 text-center text-muted">Loading dashboard...</div>;
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 text-red-600 border border-red-200 rounded-lg">
        {error}
      </div>
    );
  }

  const userName = user?.name || user?.email || "User";
  const companyName = company?.name || `Company #${user?.company_id}`;

  if (role === "editor") {
    return <EditorDashboard blogs={blogs} userName={userName} />;
  }

  if (role === "reviewer") {
    return <ReviewerDashboard blogs={blogs} pendingReviews={pendingReviews} userName={userName} />;
  }

  // Default to Admin
  return <AdminDashboard blogs={blogs} companyName={companyName} />;
};

