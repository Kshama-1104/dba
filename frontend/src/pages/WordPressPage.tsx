import React, { useEffect, useState } from "react";
import { wordpressApi } from "../api/wordpress";
import { WordPressConnection, WordPressTestResponse } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Modal } from "../components/ui/Modal";
import { ConfirmModal } from "../components/ui/ConfirmModal";
import { EmptyState } from "../components/ui/EmptyState";
import { StatusBadge } from "../components/ui/StatusBadge";
import {
  Globe,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Shield,
  Key,
  Radio,
  Lock,
  RefreshCw,
  Trash2,
} from "lucide-react";

export const WordPressPage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();

  const [connection, setConnection] = useState<WordPressConnection | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Connect / Update Modal state
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [siteUrl, setSiteUrl] = useState("");
  const [username, setUsername] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [postStatus, setPostStatus] = useState<"publish" | "draft">("publish");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Test Connection state
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<WordPressTestResponse | null>(null);

  // Disconnect Confirmation state
  const [isDisconnectOpen, setIsDisconnectOpen] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  const isAdmin = role === "company_admin";
  const canTest = role === "company_admin" || role === "editor";

  const loadConnection = async () => {
    setIsLoading(true);
    try {
      const data = await wordpressApi.getConnection();
      setConnection(data);
    } catch {
      setConnection(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadConnection();
  }, []);

  const handleOpenConnect = () => {
    setIsEditing(false);
    setSiteUrl("");
    setUsername("");
    setAppPassword("");
    setPostStatus("publish");
    setIsConnectModalOpen(true);
  };

  const handleOpenEdit = () => {
    if (!connection) return;
    setIsEditing(true);
    setSiteUrl(connection.site_url);
    setUsername(connection.username);
    setAppPassword(""); // Never prefill password
    setPostStatus(connection.default_post_status);
    setIsConnectModalOpen(true);
  };

  const handleConnectOrUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    setIsSubmitting(true);

    try {
      if (isEditing) {
        await wordpressApi.update({
          site_url: siteUrl.trim() || undefined,
          username: username.trim() || undefined,
          application_password: appPassword.trim() || undefined,
          default_post_status: postStatus,
        });
        success("Connection Updated", "WordPress settings and Application Password rotated.");
      } else {
        await wordpressApi.connect({
          site_url: siteUrl.trim(),
          username: username.trim(),
          application_password: appPassword.trim(),
          default_post_status: postStatus,
        });
        success("WordPress Connected", "Site connection registered and credentials encrypted.");
      }
      setIsConnectModalOpen(false);
      await loadConnection();
    } catch (err: unknown) {
      toastError(
        "Connection Error",
        err instanceof Error ? err.message : "Failed to configure WordPress connection."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTestConnection = async () => {
    if (!canTest) return;
    setIsTesting(true);
    setTestResult(null);

    try {
      const result = await wordpressApi.testConnection();
      setTestResult(result);
      if (result.success) {
        success(
          "Test Succeeded",
          `Authenticated as "${result.authenticated_user}". Publishing capability confirmed.`
        );
      } else {
        toastError("Test Failed", result.error_message || "Connection check rejected.");
      }
      await loadConnection();
    } catch (err: unknown) {
      toastError(
        "Reachability Error",
        err instanceof Error ? err.message : "Target WordPress endpoint unreachable."
      );
    } finally {
      setIsTesting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!isAdmin) return;
    setIsDisconnecting(true);

    try {
      await wordpressApi.disconnect();
      success("Disconnected", "WordPress connection and encrypted credentials permanently purged.");
      setIsDisconnectOpen(false);
      setConnection(null);
      setTestResult(null);
    } catch (err: unknown) {
      toastError(
        "Disconnect Failed",
        err instanceof Error ? err.message : "Failed to disconnect site."
      );
    } finally {
      setIsDisconnecting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              WordPress Publishing Integration
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 11 production publishing target. Publishes scheduled blogs via standard REST API with Application Password authentication and encrypted storage.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {!isAdmin && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-background border border-border rounded text-xs text-muted">
              <Shield className="w-3.5 h-3.5" />
              <span>Admin role required to configure credentials</span>
            </div>
          )}

          {isAdmin && !connection && (
            <Button
              size="sm"
              variant="primary"
              onClick={handleOpenConnect}
              leftIcon={<Globe className="w-3.5 h-3.5" />}
            >
              Connect WordPress
            </Button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="p-8 bg-surface border border-border rounded-lg space-y-3">
          <div className="h-5 bg-gray-200 animate-pulse rounded w-1/3" />
          <div className="h-24 bg-gray-200 animate-pulse rounded w-full" />
        </div>
      ) : !connection ? (
        <EmptyState
          icon={<Globe className="w-6 h-6" />}
          title="Connect your WordPress site to publish approved blogs."
          description="Enables automated publishing of approved blogs directly to your WordPress CMS via REST API."
          actionLabel={isAdmin ? "Connect WordPress Site" : undefined}
          onAction={isAdmin ? handleOpenConnect : undefined}
        />
      ) : (
        <div className="space-y-6">
          {/* Connection Overview Card */}
          <Card>
            <CardHeader
              title={
                <div className="flex items-center gap-2.5">
                  <span>Target CMS Instance</span>
                  <StatusBadge status={connection.status} size="sm" />
                </div>
              }
              description="Application Passwords are cryptographically encrypted at rest"
              action={
                <div className="flex items-center gap-2">
                  {canTest && (
                    <Button
                      size="sm"
                      variant="dark"
                      onClick={handleTestConnection}
                      isLoading={isTesting}
                      leftIcon={<RefreshCw className="w-3.5 h-3.5 text-primary" />}
                    >
                      Test Connection
                    </Button>
                  )}

                  {isAdmin && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleOpenEdit}
                      >
                        Edit / Rotate Key
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setIsDisconnectOpen(true)}
                        leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                      >
                        Disconnect
                      </Button>
                    </>
                  )}
                </div>
              }
            />
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
                <div className="p-3 bg-background border border-border rounded space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                    Site Base URL
                  </p>
                  <p className="font-semibold text-near-black font-mono truncate">
                    {connection.site_url}
                  </p>
                </div>

                <div className="p-3 bg-background border border-border rounded space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                    Username
                  </p>
                  <p className="font-semibold text-near-black font-mono truncate">
                    {connection.username}
                  </p>
                </div>

                <div className="p-3 bg-background border border-border rounded space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                    Application Password
                  </p>
                  <p className="font-mono text-near-black tracking-widest text-sm">
                    {connection.masked_credential}
                  </p>
                </div>

                <div className="p-3 bg-background border border-border rounded space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                    Default Post Status
                  </p>
                  <p className="font-semibold text-near-black uppercase font-mono">
                    {connection.default_post_status}
                  </p>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-border flex flex-wrap items-center justify-between text-xs text-muted">
                <span>
                  Last reachability test:{" "}
                  {connection.last_tested_at
                    ? new Date(connection.last_tested_at).toLocaleString()
                    : "Not tested yet"}
                </span>
                {connection.last_error && (
                  <span className="text-primary-dark font-medium truncate max-w-md">
                    Last failure: {connection.last_error}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Test Connection Results Card */}
          {testResult && (
            <Card>
              <CardHeader
                title="Live Connection Test Diagnostic"
                description="Simulated reachability and capability verification — no post is published"
              />
              <CardContent>
                <div
                  className={`p-4 rounded border text-xs flex items-start gap-3 ${
                    testResult.success
                      ? "bg-surface border-border text-near-black"
                      : "bg-primary-light border-primary-border text-primary-dark"
                  }`}
                >
                  {testResult.success ? (
                    <CheckCircle2 className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-5 h-5 text-primary-dark flex-shrink-0 mt-0.5" />
                  )}
                  <div className="space-y-1">
                    <p className="font-bold text-sm">
                      {testResult.success
                        ? "Connection Verification Succeeded"
                        : "Connection Verification Failed"}
                    </p>
                    <p className="leading-relaxed">
                      Target URL:{" "}
                      <span className="font-mono font-medium">
                        {testResult.site_url}
                      </span>
                    </p>
                    {testResult.authenticated_user && (
                      <p className="leading-relaxed">
                        Authenticated User:{" "}
                        <span className="font-mono font-medium">
                          {testResult.authenticated_user}
                        </span>
                      </p>
                    )}
                    {testResult.can_publish !== undefined && (
                      <p className="leading-relaxed">
                        Publishing Capability:{" "}
                        <span className="font-semibold">
                          {testResult.can_publish ? "VERIFIED" : "UNAUTHORIZED"}
                        </span>
                      </p>
                    )}
                    {testResult.error_message && (
                      <p className="mt-2 text-primary-dark font-mono">
                        Error: {testResult.error_message}
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Connect / Edit Modal */}
      <Modal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        title={isEditing ? "Update WordPress Integration" : "Connect WordPress Site"}
        description="Requires WordPress 5.6+ with Application Passwords enabled. Uses WordPress Core REST API."
        maxWidth="md"
      >
        <form onSubmit={handleConnectOrUpdate} className="space-y-4">
          <Input
            label="WordPress Site URL"
            placeholder="https://example.com"
            value={siteUrl}
            onChange={(e) => setSiteUrl(e.target.value)}
            required
            helperText="Must start with https:// (or http:// in dev)"
          />

          <Input
            label="WordPress Username"
            placeholder="admin_editor"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />

          <Input
            label={isEditing ? "New Application Password (Leave blank to keep current)" : "Application Password"}
            type="password"
            placeholder="xxxx xxxx xxxx xxxx"
            value={appPassword}
            onChange={(e) => setAppPassword(e.target.value)}
            required={!isEditing}
            helperText="Generate in WordPress: Users → Profile → Application Passwords."
          />

          <Select
            label="Default Post Status"
            value={postStatus}
            onChange={(e) => setPostStatus(e.target.value as "publish" | "draft")}
            options={[
              { label: "Publish Immediately", value: "publish" },
              { label: "Save as WordPress Draft", value: "draft" },
            ]}
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsConnectModalOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
            >
              {isEditing ? "Update Connection" : "Save Connection"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Disconnect Confirmation Modal */}
      <ConfirmModal
        isOpen={isDisconnectOpen}
        onClose={() => setIsDisconnectOpen(false)}
        onConfirm={handleDisconnect}
        title="Disconnect WordPress Site"
        message="Are you sure you want to disconnect this WordPress instance? Encrypted credentials will be permanently purged and automated blog publications will halt."
        confirmLabel="Disconnect Site"
        confirmVariant="primary"
        isLoading={isDisconnecting}
      />
    </div>
  );
};
