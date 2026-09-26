import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { chatApi } from "../api/chat";
import { blogsApi } from "../api/blogs";
import {
  BlogDetail,
  BlogRevisionDetail,
  BlogRevisionSummary,
} from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { ConfirmModal } from "../components/ui/ConfirmModal";
import {
  ArrowLeft,
  History,
  RotateCcw,
  Eye,
  GitCommit,
  Sparkles,
  AlertCircle,
} from "lucide-react";

export const BlogRevisionsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const blogId = Number(id);

  const { role } = useAuth();
  const { success, error: toastError } = useToast();
  const navigate = useNavigate();

  const [blog, setBlog] = useState<BlogDetail | null>(null);
  const [revisions, setRevisions] = useState<BlogRevisionSummary[]>([]);
  const [selectedRevision, setSelectedRevision] = useState<BlogRevisionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  // Restore Modal state
  const [revisionToRestore, setRevisionToRestore] = useState<BlogRevisionSummary | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);

  const isEditor = role === "editor";

  const loadData = async () => {
    if (!blogId) return;
    setIsLoading(true);
    try {
      const [blogData, revList] = await Promise.all([
        blogsApi.getBlog(blogId),
        chatApi.listRevisions(blogId),
      ]);
      setBlog(blogData);
      setRevisions(revList);
    } catch (err: unknown) {
      toastError(
        "Load Failed",
        err instanceof Error ? err.message : "Failed to load revisions."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [blogId]);

  const handleViewDetail = async (revisionId: number) => {
    setIsLoadingDetail(true);
    try {
      const detail = await chatApi.getRevisionDetail(blogId, revisionId);
      setSelectedRevision(detail);
    } catch (err: unknown) {
      toastError(
        "Load Failed",
        err instanceof Error ? err.message : "Failed to load snapshot details."
      );
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleConfirmRestore = async () => {
    if (!revisionToRestore || !isEditor) return;
    setIsRestoring(true);
    try {
      const newRev = await chatApi.restoreRevision(
        blogId,
        revisionToRestore.id,
        `Rollback to revision v${revisionToRestore.revision_number}`
      );
      success(
        "Revision Restored",
        `Created new snapshot v${newRev.revision_number} restored from v${revisionToRestore.revision_number}. Historical revisions preserved.`
      );
      setRevisionToRestore(null);
      await loadData();
    } catch (err: unknown) {
      toastError(
        "Restore Failed",
        err instanceof Error ? err.message : "Failed to restore revision snapshot."
      );
    } finally {
      setIsRestoring(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => navigate(`/blogs/${blogId}`)}
            leftIcon={<ArrowLeft className="w-4 h-4" />}
          >
            Overview
          </Button>
          <div className="h-4 w-px bg-border" />
          <div>
            <div className="flex items-center gap-2">
              <History className="w-5 h-5 text-primary" />
              <h1 className="text-lg font-bold text-near-black tracking-tight">
                Revision History &amp; Snapshots
              </h1>
            </div>
            <p className="text-xs text-muted mt-0.5">
              Draft: <strong className="text-near-black">{blog?.title || `Blog #${blogId}`}</strong>
            </p>
          </div>
        </div>

        {isEditor && (
          <Link to={`/blogs/${blogId}/editor`}>
            <Button size="sm" variant="dark">
              Open Editor
            </Button>
          </Link>
        )}
      </div>

      {/* Revisions Timeline List */}
      <Card>
        <CardHeader
          title={`Immutable Snapshot History (${revisions.length} Revisions)`}
          description="Every AI refinement or restore operation creates an immutable snapshot (V_N+1). Historical revisions are never deleted."
        />
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 space-y-3">
              <div className="h-4 bg-gray-200 animate-pulse rounded w-3/4" />
              <div className="h-4 bg-gray-200 animate-pulse rounded w-1/2" />
            </div>
          ) : revisions.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted">
              No historical revisions found for this draft.
            </div>
          ) : (
            <div className="divide-y divide-border">
              {revisions.map((rev) => (
                <div
                  key={rev.id}
                  className="p-5 hover:bg-background/60 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="flex items-start gap-3.5">
                    <div className="w-8 h-8 rounded-full bg-near-black text-white flex items-center justify-center font-mono font-bold text-xs flex-shrink-0 mt-0.5">
                      v{rev.revision_number}
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-near-black">
                          {rev.seo_title || `Revision Snapshot #${rev.id}`}
                        </span>
                        {rev.restored_from_revision_id && (
                          <span className="text-[10px] px-1.5 py-0.2 bg-primary-light text-primary-dark border border-primary-border rounded font-mono">
                            Restored from #{rev.restored_from_revision_id}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted leading-relaxed">
                        {rev.revision_summary || "Automated draft snapshot"}
                      </p>
                      <p className="text-[11px] text-muted font-mono">
                        Saved: {new Date(rev.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleViewDetail(rev.id)}
                      leftIcon={<Eye className="w-3.5 h-3.5" />}
                    >
                      View Snapshot
                    </Button>

                    {isEditor && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setRevisionToRestore(rev)}
                        leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                        title="Restore this revision as a new snapshot"
                      >
                        Restore
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Snapshot Preview Modal */}
      <Modal
        isOpen={!!selectedRevision}
        onClose={() => setSelectedRevision(null)}
        title={
          selectedRevision
            ? `Revision Snapshot v${selectedRevision.revision_number} Detail`
            : "Snapshot Detail"
        }
        description="Complete immutable content snapshot and Phase 7 validation audit"
        maxWidth="3xl"
      >
        {selectedRevision && (
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
            <div className="p-3 bg-background border border-border rounded text-xs space-y-1">
              <p className="font-semibold text-near-black">
                {selectedRevision.seo_title}
              </p>
              <p className="text-muted text-[11px]">
                Summary: {selectedRevision.revision_summary}
              </p>
              <p className="text-muted text-[11px] font-mono">
                Captured: {new Date(selectedRevision.created_at).toLocaleString()}
              </p>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
                Structured Content
              </h4>
              <div className="p-4 bg-background border border-border rounded text-xs space-y-4">
                <h2 className="text-lg font-bold text-near-black">
                  {selectedRevision.content_json?.h1_title}
                </h2>
                {selectedRevision.content_json?.introduction && (
                  <p className="text-muted italic border-l-2 border-primary pl-2">
                    {selectedRevision.content_json.introduction}
                  </p>
                )}
                {selectedRevision.content_json?.sections?.map((s, idx) => (
                  <div key={idx} className="space-y-1 pt-2">
                    <h3 className="font-bold text-near-black">{s.heading}</h3>
                    <p className="text-near-black whitespace-pre-wrap">{s.content}</p>
                  </div>
                ))}
                {selectedRevision.content_json?.conclusion && (
                  <div className="pt-2 border-t border-border">
                    <h4 className="font-bold text-near-black">Conclusion</h4>
                    <p className="text-near-black">
                      {selectedRevision.content_json.conclusion}
                    </p>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center justify-end pt-4 border-t border-border">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedRevision(null)}
              >
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Restore Confirmation Modal */}
      <ConfirmModal
        isOpen={!!revisionToRestore}
        onClose={() => setRevisionToRestore(null)}
        onConfirm={handleConfirmRestore}
        title="Restore Revision Snapshot"
        message={`Are you sure you want to restore revision v${revisionToRestore?.revision_number}? This will losslessly create an immutable new revision (v${revisions.length}) with content from v${revisionToRestore?.revision_number}. All prior revisions are strictly preserved.`}
        confirmLabel="Restore Snapshot"
        confirmVariant="primary"
        isLoading={isRestoring}
      />
    </div>
  );
};
