import React, { useEffect, useState } from "react";
import { blogFormatApi } from "../api/blogFormat";
import { BlogFormat, BlogFormatDefinition } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { FormatViewer } from "../components/domain/FormatViewer";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Textarea } from "../components/ui/Textarea";
import { Modal } from "../components/ui/Modal";
import { FileCode2, History, Plus, Check, Shield } from "lucide-react";

export const BlogFormatPage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();

  const [activeFormat, setActiveFormat] = useState<BlogFormat | null>(null);
  const [versions, setVersions] = useState<BlogFormat[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<BlogFormat | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActivating, setIsActivating] = useState(false);

  // New version modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formState, setFormState] = useState({
    title_structure: "Compelling, brand-aligned H1 headline",
    introduction_structure: "Hook, problem articulation, thesis statement",
    heading_structure: "Hierarchical H2 and H3 sections organizing core arguments",
    main_content_structure: "Educational body sections, bullet points, data callouts",
    conclusion_structure: "Summary synthesis, closing thoughts, brand CTA",
    call_to_action: "Explore how DailyBlog AI scales enterprise content generation.",
    custom_rules: "Always use active voice.\nInclude at least one actionable takeaway per section.",
  });

  const isEditor = role === "editor";

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [activeResp, versionsResp] = await Promise.all([
        blogFormatApi.getActiveFormat().catch(() => null),
        blogFormatApi.listVersions().catch(() => null),
      ]);

      if (activeResp) {
        setActiveFormat(activeResp);
        setSelectedVersion(activeResp);
      }
      if (versionsResp) {
        setVersions(versionsResp.formats);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleActivate = async (versionNumber: number) => {
    if (!isEditor) return;
    setIsActivating(true);
    try {
      const activated = await blogFormatApi.activateVersion(versionNumber);
      setActiveFormat(activated);
      setSelectedVersion(activated);
      await loadData();
      success("Format Activated", `Global Blog Format v${versionNumber} is now active.`);
    } catch (err: unknown) {
      toastError(
        "Activation Failed",
        err instanceof Error ? err.message : "Failed to activate format version."
      );
    } finally {
      setIsActivating(false);
    }
  };

  const handleCreateVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isEditor) return;
    setIsSubmitting(true);

    try {
      const customRulesArray = formState.custom_rules
        .split("\n")
        .map((r) => r.trim())
        .filter(Boolean);

      const created = await blogFormatApi.updateFormat({
        title_structure: formState.title_structure,
        introduction_structure: formState.introduction_structure,
        heading_structure: formState.heading_structure,
        main_content_structure: formState.main_content_structure,
        conclusion_structure: formState.conclusion_structure,
        call_to_action: formState.call_to_action,
        custom_rules: customRulesArray,
      });

      setActiveFormat(created);
      setSelectedVersion(created);
      setIsModalOpen(false);
      await loadData();
      success("New Version Created", `Format v${created.version} successfully published and activated.`);
    } catch (err: unknown) {
      toastError(
        "Creation Failed",
        err instanceof Error ? err.message : "Failed to create new format version."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <FileCode2 className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Company Global Blog Format
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 2 architectural format contract (Level 2). Enforces immutable baseline sections and editorial guidelines across all drafts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {!isEditor ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-background border border-border rounded text-xs text-muted">
              <Shield className="w-3.5 h-3.5" />
              <span>View-only (Editor role required to create/activate formats)</span>
            </div>
          ) : (
            <Button
              size="sm"
              variant="primary"
              onClick={() => setIsModalOpen(true)}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              New Format Version
            </Button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="p-8 bg-surface border border-border rounded-lg space-y-4">
          <div className="h-5 bg-gray-200 animate-pulse rounded w-1/3" />
          <div className="h-40 bg-gray-200 animate-pulse rounded w-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Format Display (2 columns) */}
          <div className="lg:col-span-2">
            {selectedVersion ? (
              <FormatViewer
                definition={selectedVersion.format_definition}
                version={selectedVersion.version}
                isActive={selectedVersion.is_active}
                action={
                  isEditor && !selectedVersion.is_active ? (
                    <Button
                      size="sm"
                      variant="dark"
                      onClick={() => handleActivate(selectedVersion.version)}
                      isLoading={isActivating}
                      leftIcon={<Check className="w-3.5 h-3.5 text-primary" />}
                    >
                      Activate v{selectedVersion.version}
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <Card>
                <CardHeader
                  title="No Format Configured"
                  description="Create an initial global format version to enforce structural standards."
                />
              </Card>
            )}
          </div>

          {/* Version History Sidebar (1 column) */}
          <div className="space-y-4">
            <Card>
              <CardHeader
                title="Version Audit History"
                description="Immutable chronological snapshots"
              />
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {versions.length === 0 ? (
                    <p className="p-4 text-xs text-muted">No historical versions.</p>
                  ) : (
                    versions.map((ver) => {
                      const isSelected = selectedVersion?.version === ver.version;
                      return (
                        <button
                          key={ver.id}
                          onClick={() => setSelectedVersion(ver)}
                          className={`w-full p-4 text-left flex items-center justify-between transition-colors ${
                            isSelected
                              ? "bg-background border-l-2 border-primary"
                              : "hover:bg-background/60"
                          }`}
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-semibold text-near-black">
                                Version {ver.version}
                              </span>
                              {ver.is_active && (
                                <span className="text-[10px] px-1.5 py-0.2 bg-black text-white rounded font-mono font-medium">
                                  ACTIVE
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-muted block mt-0.5">
                              {new Date(ver.created_at).toLocaleDateString()}
                            </span>
                          </div>
                          <History className="w-4 h-4 text-muted" />
                        </button>
                      );
                    })
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* New Format Version Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create Global Blog Format Version"
        description="Creates an immutable new version and approves it as the active format."
        maxWidth="2xl"
      >
        <form onSubmit={handleCreateVersion} className="space-y-4">
          <Input
            label="Title Structure (H1)"
            value={formState.title_structure}
            onChange={(e) =>
              setFormState((p) => ({ ...p, title_structure: e.target.value }))
            }
            required
          />

          <Input
            label="Introduction Structure"
            value={formState.introduction_structure}
            onChange={(e) =>
              setFormState((p) => ({
                ...p,
                introduction_structure: e.target.value,
              }))
            }
            required
          />

          <Input
            label="Heading Structure (H2/H3)"
            value={formState.heading_structure}
            onChange={(e) =>
              setFormState((p) => ({ ...p, heading_structure: e.target.value }))
            }
            required
          />

          <Input
            label="Main Content Body Structure"
            value={formState.main_content_structure}
            onChange={(e) =>
              setFormState((p) => ({
                ...p,
                main_content_structure: e.target.value,
              }))
            }
            required
          />

          <Input
            label="Conclusion Structure"
            value={formState.conclusion_structure}
            onChange={(e) =>
              setFormState((p) => ({
                ...p,
                conclusion_structure: e.target.value,
              }))
            }
            required
          />

          <Input
            label="Default Call-To-Action (CTA)"
            value={formState.call_to_action}
            onChange={(e) =>
              setFormState((p) => ({ ...p, call_to_action: e.target.value }))
            }
          />

          <Textarea
            label="Custom Editorial Rules (One per line)"
            value={formState.custom_rules}
            onChange={(e) =>
              setFormState((p) => ({ ...p, custom_rules: e.target.value }))
            }
            rows={3}
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsModalOpen(false)}
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
              Publish &amp; Activate Version
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
