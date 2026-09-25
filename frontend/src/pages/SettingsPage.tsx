import React, { useEffect, useState } from "react";
import { companyApi } from "../api/company";
import { CompanySettings, TeamMember } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { StatusBadge } from "../components/ui/StatusBadge";
import {
  Settings,
  Mail,
  Lock,
  Users,
  Shield,
  AlertCircle,
  Save,
  Key,
} from "lucide-react";

export const SettingsPage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();

  const [settings, setSettings] = useState<CompanySettings | null>(null);
  const [notificationEmail, setNotificationEmail] = useState("");
  const [isUpdatingEmail, setIsUpdatingEmail] = useState(false);

  // Change password state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Team lists
  const [reviewers, setReviewers] = useState<TeamMember[]>([]);
  const [editors, setEditors] = useState<TeamMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const isAdmin = role === "company_admin";

  const loadData = async () => {
    if (!isAdmin) return;
    setIsLoading(true);
    try {
      const [settingsData, reviewersData, editorsData] = await Promise.all([
        companyApi.getSettings().catch(() => null),
        companyApi.getReviewers().catch(() => ({ reviewers: [] })),
        companyApi.getEditors().catch(() => ({ editors: [] })),
      ]);

      if (settingsData) {
        setSettings(settingsData);
        setNotificationEmail(settingsData.notification_email || "");
      }
      setReviewers(reviewersData.reviewers || []);
      setEditors(editorsData.editors || []);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [isAdmin]);

  const handleUpdateEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!notificationEmail.trim()) return;
    setIsUpdatingEmail(true);

    try {
      await companyApi.updateNotificationEmail(notificationEmail.trim());
      success("Settings Saved", "Company notification email updated.");
      await loadData();
    } catch (err: unknown) {
      toastError(
        "Update Failed",
        err instanceof Error ? err.message : "Failed to update notification email."
      );
    } finally {
      setIsUpdatingEmail(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentPassword || !newPassword || !confirmPassword) return;

    if (newPassword !== confirmPassword) {
      toastError("Validation Error", "New passwords do not match.");
      return;
    }

    if (newPassword.length < 8) {
      toastError("Validation Error", "New password must be at least 8 characters.");
      return;
    }

    setIsChangingPassword(true);
    try {
      await companyApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      success("Password Changed", "Company admin password has been changed successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      toastError(
        "Password Change Failed",
        err instanceof Error ? err.message : "Failed to change admin password."
      );
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Company Settings &amp; Governance
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Enterprise administration, notification routing, admin security, and editorial team roster.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Notification Routing & Admin Password */}
        <div className="space-y-6">
          {/* Notification Email Settings */}
          <Card>
            <CardHeader
              title="Editorial Notifications"
              description="Destination email for publication alerts and review queue notices"
            />
            <CardContent>
              <form onSubmit={handleUpdateEmail} className="space-y-4">
                <Input
                  label="Notification Email Address"
                  type="email"
                  placeholder="editor-team@company.com"
                  value={notificationEmail}
                  onChange={(e) => setNotificationEmail(e.target.value)}
                  required
                />
                <Button
                  type="submit"
                  size="sm"
                  variant="primary"
                  isLoading={isUpdatingEmail}
                  leftIcon={<Save className="w-3.5 h-3.5" />}
                >
                  Save Notification Email
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Change Admin Password */}
          <Card>
            <CardHeader
              title="Admin Security &amp; Password"
              description="Rotate Company Admin authentication credentials"
            />
            <CardContent>
              <form onSubmit={handleChangePassword} className="space-y-4">
                <Input
                  label="Current Password"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                />
                <Input
                  label="New Password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  helperText="Must be at least 8 characters and different from temporary password."
                />
                <Input
                  label="Confirm New Password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
                <Button
                  type="submit"
                  size="sm"
                  variant="dark"
                  isLoading={isChangingPassword}
                  leftIcon={<Key className="w-3.5 h-3.5" />}
                >
                  Update Admin Password
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Team Roster (Reviewers & Editors) */}
        <div className="space-y-6">
          {/* Reviewers List */}
          <Card>
            <CardHeader
              title={`Human Reviewers Roster (${reviewers.length})`}
              description="Authorized to approve, reject, or request changes on blog drafts"
            />
            <CardContent className="p-0">
              {reviewers.length === 0 ? (
                <p className="p-4 text-xs text-muted">No reviewers registered.</p>
              ) : (
                <div className="divide-y divide-border">
                  {reviewers.map((rev) => (
                    <div
                      key={rev.id}
                      className="p-3.5 flex items-center justify-between text-xs"
                    >
                      <div>
                        <p className="font-semibold text-near-black">{rev.name}</p>
                        <p className="text-muted text-[11px]">{rev.email}</p>
                      </div>
                      <StatusBadge status={rev.status} size="sm" />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Editors List */}
          <Card>
            <CardHeader
              title={`Content Editors Roster (${editors.length})`}
              description="Authorized to generate drafts, use Editor Chat, and submit reviews"
            />
            <CardContent className="p-0">
              {editors.length === 0 ? (
                <p className="p-4 text-xs text-muted">No editors registered.</p>
              ) : (
                <div className="divide-y divide-border">
                  {editors.map((ed) => (
                    <div
                      key={ed.id}
                      className="p-3.5 flex items-center justify-between text-xs"
                    >
                      <div>
                        <p className="font-semibold text-near-black">{ed.name}</p>
                        <p className="text-muted text-[11px]">{ed.email}</p>
                      </div>
                      <StatusBadge status={ed.status} size="sm" />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
