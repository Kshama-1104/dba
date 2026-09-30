import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Button } from "../ui/Button";
import { Calendar, Clock, Globe2 } from "lucide-react";

export interface ScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  blogId: number;
  blogTitle: string;
  targetRevisionId?: number;
  onSubmit: (data: {
    local_scheduled_time: string;
    timezone: string;
    target_revision_id?: number;
  }) => Promise<void>;
  isLoading?: boolean;
}

const COMMON_TIMEZONES = [
  { value: "UTC", label: "UTC (Coordinated Universal Time)" },
  { value: "Asia/Kolkata", label: "Asia/Kolkata (IST +05:30)" },
  { value: "America/New_York", label: "America/New_York (EST/EDT -05:00)" },
  { value: "America/Chicago", label: "America/Chicago (CST/CDT -06:00)" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles (PST/PDT -08:00)" },
  { value: "Europe/London", label: "Europe/London (GMT/BST +00:00)" },
  { value: "Europe/Paris", label: "Europe/Paris (CET/CEST +01:00)" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo (JST +09:00)" },
  { value: "Australia/Sydney", label: "Australia/Sydney (AEST/AEDT +10:00)" },
];

export const ScheduleModal: React.FC<ScheduleModalProps> = ({
  isOpen,
  onClose,
  blogTitle,
  targetRevisionId,
  onSubmit,
  isLoading = false,
}) => {
  // Tomorrow at 09:00 AM as a default suggestion
  const getDefaultDate = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}T09:00`;
  };

  const [dateTime, setDateTime] = useState<string>(getDefaultDate());
  const [timezone, setTimezone] = useState<string>("UTC");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dateTime) {
      setError("Please specify scheduled date and time.");
      return;
    }
    setError(null);

    try {
      // Backend expects wall clock format: YYYY-MM-DDTHH:MM:SS
      const formattedTime = dateTime.length === 16 ? `${dateTime}:00` : dateTime;
      await onSubmit({
        local_scheduled_time: formattedTime,
        timezone,
        target_revision_id: targetRevisionId,
      });
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to create publication schedule.");
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Schedule Blog Publication"
      description={`Schedule automated publishing for: "${blogTitle}"`}
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {targetRevisionId && (
          <div className="p-3 bg-background border border-border rounded text-xs flex items-center justify-between">
            <span className="text-muted">Target Approved Revision:</span>
            <span className="font-mono font-semibold text-near-black">
              Snapshot #{targetRevisionId}
            </span>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-1.5 flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-primary" />
            <span>Local Scheduled Date &amp; Time</span>
          </label>
          <Input
            type="datetime-local"
            value={dateTime}
            onChange={(e) => setDateTime(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-1.5 flex items-center gap-1.5">
            <Globe2 className="w-3.5 h-3.5 text-primary" />
            <span>Target IANA Timezone</span>
          </label>
          <Select
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            options={COMMON_TIMEZONES}
          />
          <p className="text-[11px] text-muted mt-1 leading-relaxed">
            The publication worker converts this wall-clock time against the specified canonical IANA timezone.
          </p>
        </div>

        {error && (
          <div className="p-3 bg-primary-light border border-primary-border rounded text-xs text-primary-dark">
            {error}
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
            variant="primary"
            size="sm"
            isLoading={isLoading}
            leftIcon={<Clock className="w-3.5 h-3.5" />}
          >
            Confirm Schedule
          </Button>
        </div>
      </form>
    </Modal>
  );
};
