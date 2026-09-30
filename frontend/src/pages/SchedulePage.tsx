import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { blogsApi } from "../api/blogs";
import { schedulesApi } from "../api/schedules";
import { BlogSchedule, BlogSummary } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { ScheduleModal } from "../components/domain/ScheduleModal";
import { ConfirmModal } from "../components/ui/ConfirmModal";
import { Modal } from "../components/ui/Modal";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/StatusBadge";
import { EmptyState } from "../components/ui/EmptyState";
import {
  Calendar,
  Clock,
  RotateCcw,
  XCircle,
  Globe2,
  AlertCircle,
  Shield,
  Plus,
} from "lucide-react";

export const SchedulePage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();
  const [searchParams] = useSearchParams();

  const [approvedBlogs, setApprovedBlogs] = useState<BlogSummary[]>([]);
  const [schedules, setSchedules] = useState<
    (BlogSchedule & { blogTitle?: string })[]
  >([]);
  const [isLoading, setIsLoading] = useState(true);

  // New Schedule Modal state
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [selectedBlogForSchedule, setSelectedBlogForSchedule] = useState<BlogSummary | null>(null);

  // Reschedule Modal state
  const [scheduleToReschedule, setScheduleToReschedule] = useState<BlogSchedule | null>(null);
  const [newTime, setNewTime] = useState("");
  const [newTimezone, setNewTimezone] = useState("UTC");
  const [isRescheduling, setIsRescheduling] = useState(false);

  // Cancel Schedule Modal state
  const [scheduleToCancel, setScheduleToCancel] = useState<BlogSchedule | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [isCancelling, setIsCancelling] = useState(false);

  const canMutate = role === "company_admin" || role === "editor" || role === "reviewer";

  const loadData = async () => {
    setIsLoading(true);
    try {
      // 1. Fetch approved blogs
      const allBlogs = await blogsApi.listBlogs({ limit: 100 });
      const approved = allBlogs.filter(
        (b) => b.status === "approved" || b.status === "scheduled" || b.status === "published"
      );
      setApprovedBlogs(approved);

      // 2. Fetch schedules for these blogs
      const blogSchedulesPromises = approved.map(async (b) => {
        try {
          const list = await schedulesApi.listBlogSchedules(b.id);
          return list.map((s) => ({ ...s, blogTitle: b.title }));
        } catch {
          return [];
        }
      });

      const nestedSchedules = await Promise.all(blogSchedulesPromises);
      const flattened = nestedSchedules.flat();
      flattened.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setSchedules(flattened);

      // Check query param blogId
      const targetBlogId = searchParams.get("blogId");
      if (targetBlogId) {
        const match = approved.find((b) => b.id === Number(targetBlogId));
        if (match) {
          setSelectedBlogForSchedule(match);
          setIsScheduleModalOpen(true);
        }
      }
    } catch (err: unknown) {
      toastError(
        "Load Failed",
        err instanceof Error ? err.message : "Failed to load publication schedules."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateSchedule = async (data: {
    local_scheduled_time: string;
    timezone: string;
    target_revision_id?: number;
  }) => {
    if (!selectedBlogForSchedule) return;
    try {
      await schedulesApi.createSchedule(selectedBlogForSchedule.id, data);
      success("Schedule Created", `Publication job created for ${data.local_scheduled_time} (${data.timezone}).`);
      setIsScheduleModalOpen(false);
      await loadData();
    } catch (err: unknown) {
      toastError(
        "Scheduling Failed",
        err instanceof Error ? err.message : "Failed to schedule blog."
      );
      throw err;
    }
  };

  const handleReschedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduleToReschedule || !newTime) return;
    setIsRescheduling(true);

    try {
      const formattedTime = newTime.length === 16 ? `${newTime}:00` : newTime;
      await schedulesApi.reschedule(scheduleToReschedule.id, {
        local_scheduled_time: formattedTime,
        timezone: newTimezone || undefined,
      });
      success("Rescheduled", `Publication rescheduled to ${formattedTime}.`);
      setScheduleToReschedule(null);
      await loadData();
    } catch (err: unknown) {
      toastError(
        "Reschedule Failed",
        err instanceof Error ? err.message : "Failed to reschedule publication."
      );
    } finally {
      setIsRescheduling(false);
    }
  };

  const handleCancelSchedule = async () => {
    if (!scheduleToCancel) return;
    setIsCancelling(true);

    try {
      await schedulesApi.cancelSchedule(
        scheduleToCancel.id,
        cancelReason.trim() || undefined
      );
      success("Schedule Cancelled", "Publication schedule marked as CANCELLED.");
      setScheduleToCancel(null);
      setCancelReason("");
      await loadData();
    } catch (err: unknown) {
      toastError(
        "Cancellation Failed",
        err instanceof Error ? err.message : "Failed to cancel publication schedule."
      );
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Publication Schedule &amp; Calendar
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 10 deterministic publication queue. Handles IANA timezone conversions, worker leases, idempotent execution, and audit events.
          </p>
        </div>

        {canMutate && approvedBlogs.length > 0 && (
          <Button
            size="sm"
            variant="primary"
            onClick={() => {
              setSelectedBlogForSchedule(approvedBlogs[0]);
              setIsScheduleModalOpen(true);
            }}
            leftIcon={<Plus className="w-3.5 h-3.5" />}
          >
            Schedule Approved Blog
          </Button>
        )}
      </div>

      {/* Schedules Table */}
      <Card>
        <CardHeader
          title={`Publication Queue (${schedules.length})`}
          description="All scheduled, queued, running, and historical publication jobs"
        />
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 space-y-3">
              <div className="h-4 bg-gray-200 animate-pulse rounded w-3/4" />
              <div className="h-4 bg-gray-200 animate-pulse rounded w-1/2" />
            </div>
          ) : schedules.length === 0 ? (
            <EmptyState
              icon={<Calendar className="w-6 h-6" />}
              title="No publications are currently scheduled."
              description="Approved blogs can be scheduled with canonical IANA timezone precision."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-background border-b border-border text-[11px] font-semibold uppercase tracking-wider text-muted">
                  <tr>
                    <th className="py-3 px-4">Blog Title</th>
                    <th className="py-3 px-4">Target Revision</th>
                    <th className="py-3 px-4">Local Scheduled Time</th>
                    <th className="py-3 px-4">Timezone</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Attempts</th>
                    {canMutate && <th className="py-3 px-4 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {schedules.map((sched) => (
                    <tr
                      key={sched.id}
                      className="hover:bg-background/80 transition-colors"
                    >
                      <td className="py-3 px-4 font-semibold text-near-black">
                        <Link
                          to={`/blogs/${sched.blog_id}`}
                          className="hover:text-primary transition-colors block line-clamp-1"
                        >
                          {sched.blogTitle || `Blog #${sched.blog_id}`}
                        </Link>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px]">
                        Snapshot #{sched.target_revision_id}
                      </td>
                      <td className="py-3 px-4 font-mono font-medium text-near-black whitespace-nowrap">
                        {sched.local_scheduled_time}
                      </td>
                      <td className="py-3 px-4 text-muted font-mono">
                        {sched.timezone}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={sched.status} size="sm" />
                        {sched.last_error && (
                          <span
                            title={sched.last_error}
                            className="block text-[10px] text-primary-dark truncate max-w-xs mt-0.5"
                          >
                            {sched.last_error}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono text-muted">
                        {sched.attempt_count} / {sched.max_attempts}
                      </td>
                      {canMutate && (
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {sched.status === "SCHEDULED" && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    setScheduleToReschedule(sched);
                                    setNewTime(sched.local_scheduled_time.slice(0, 16));
                                    setNewTimezone(sched.timezone);
                                  }}
                                  leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                                >
                                  Reschedule
                                </Button>

                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setScheduleToCancel(sched)}
                                  leftIcon={<XCircle className="w-3.5 h-3.5" />}
                                >
                                  Cancel
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Schedule Creation Modal */}
      {selectedBlogForSchedule && (
        <ScheduleModal
          isOpen={isScheduleModalOpen}
          onClose={() => setIsScheduleModalOpen(false)}
          blogId={selectedBlogForSchedule.id}
          blogTitle={selectedBlogForSchedule.title}
          onSubmit={handleCreateSchedule}
        />
      )}

      {/* Reschedule Modal */}
      <Modal
        isOpen={!!scheduleToReschedule}
        onClose={() => setScheduleToReschedule(null)}
        title="Reschedule Publication Job"
        description={`Schedule #${scheduleToReschedule?.id} for "${scheduleToReschedule?.blog_id}"`}
        maxWidth="md"
      >
        <form onSubmit={handleReschedule} className="space-y-4">
          <Input
            type="datetime-local"
            label="New Local Wall-Clock Time"
            value={newTime}
            onChange={(e) => setNewTime(e.target.value)}
            required
          />

          <Input
            label="Canonical IANA Timezone"
            value={newTimezone}
            onChange={(e) => setNewTimezone(e.target.value)}
            required
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setScheduleToReschedule(null)}
              disabled={isRescheduling}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isRescheduling}
            >
              Confirm Reschedule
            </Button>
          </div>
        </form>
      </Modal>

      {/* Cancel Confirmation Modal */}
      <Modal
        isOpen={!!scheduleToCancel}
        onClose={() => setScheduleToCancel(null)}
        title="Cancel Publication Schedule"
        description={`Are you sure you want to cancel publication for Schedule #${scheduleToCancel?.id}?`}
        maxWidth="md"
      >
        <div className="space-y-4">
          <Input
            label="Optional Cancellation Reason"
            placeholder="e.g. Content superseded or holding for press embargo"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setScheduleToCancel(null)}
              disabled={isCancelling}
            >
              Back
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={handleCancelSchedule}
              isLoading={isCancelling}
            >
              Confirm Cancellation
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
