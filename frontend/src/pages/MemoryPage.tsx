import React, { useEffect, useState } from "react";
import { memoryApi } from "../api/memory";
import {
  CompanyMemory,
  MemoryConfidence,
  MemorySource,
  MemoryStatus,
  MemoryType,
  RetrievedMemoryItem,
} from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { Textarea } from "../components/ui/Textarea";
import { StatusBadge } from "../components/ui/StatusBadge";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { ConfirmModal } from "../components/ui/ConfirmModal";
import {
  Brain,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Trash2,
  Sparkles,
  GitFork,
  AlertCircle,
  Tag,
} from "lucide-react";

export const MemoryPage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();

  const [memories, setMemories] = useState<CompanyMemory[]>([]);
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Memory Modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newType, setNewType] = useState<MemoryType>("SEMANTIC");
  const [newContent, setNewContent] = useState("");
  const [newImportance, setNewImportance] = useState(3);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Resolve conflicts state
  const [isResolving, setIsResolving] = useState(false);

  // Delete modal state
  const [memoryToDelete, setMemoryToDelete] = useState<CompanyMemory | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Retrieval search state
  const [query, setQuery] = useState("");
  const [retrievedItems, setRetrievedItems] = useState<RetrievedMemoryItem[]>([]);
  const [isRetrieving, setIsRetrieving] = useState(false);

  const canMutate = role === "company_admin" || role === "editor";
  const isAdmin = role === "company_admin";

  const loadMemories = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await memoryApi.listMemories({
        memory_type: typeFilter !== "ALL" ? (typeFilter as MemoryType) : undefined,
        status: statusFilter !== "ALL" ? (statusFilter as MemoryStatus) : undefined,
      });
      setMemories(resp.memories);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load company memories."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadMemories();
  }, [typeFilter, statusFilter]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim() || !canMutate) return;
    setIsSubmitting(true);

    try {
      await memoryApi.createMemory({
        memory_type: newType,
        content: newContent.trim(),
        importance: newImportance,
        source: "EXPLICIT_USER",
        confidence: "HIGH",
        status: "ACTIVE",
      });
      success("Memory Recorded", "Durable company memory stored with vector embedding.");
      setIsCreateOpen(false);
      setNewContent("");
      await loadMemories();
    } catch (err: unknown) {
      toastError(
        "Save Failed",
        err instanceof Error ? err.message : "Failed to create memory."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResolveConflicts = async () => {
    if (!canMutate) return;
    setIsResolving(true);
    try {
      const result = await memoryApi.resolveConflicts();
      success(
        "Conflict Resolution Complete",
        `${result.summary} (${result.conflicts_detected} conflicts processed)`
      );
      await loadMemories();
    } catch (err: unknown) {
      toastError(
        "Resolution Failed",
        err instanceof Error ? err.message : "Failed to resolve memory conflicts."
      );
    } finally {
      setIsResolving(false);
    }
  };

  const handleDelete = async () => {
    if (!memoryToDelete || !canMutate) return;
    setIsDeleting(true);
    try {
      await memoryApi.deleteMemory(memoryToDelete.id, isAdmin);
      success(
        "Memory Updated",
        isAdmin ? "Memory permanently removed." : "Memory archived."
      );
      setMemoryToDelete(null);
      await loadMemories();
    } catch (err: unknown) {
      toastError(
        "Action Failed",
        err instanceof Error ? err.message : "Failed to archive memory."
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setIsRetrieving(true);

    try {
      const resp = await memoryApi.retrieve({
        query: query.trim(),
        top_k: 4,
      });
      setRetrievedItems(resp.memories);
    } catch (err: unknown) {
      toastError(
        "Retrieval Failed",
        err instanceof Error ? err.message : "Failed to retrieve memories."
      );
    } finally {
      setIsRetrieving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Company Long-Term Memory
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 4 persistent memory store. Maintains Semantic facts, Episodic editorial history, and Procedural preferences with precedence rules.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {canMutate && (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={handleResolveConflicts}
                isLoading={isResolving}
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
                title="Enforce Company Profile precedence over memories"
              >
                Resolve Profile Conflicts
              </Button>
              <Button
                size="sm"
                variant="primary"
                onClick={() => setIsCreateOpen(true)}
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                Record Memory
              </Button>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-primary-light border border-primary-border rounded-lg text-xs text-primary-dark flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Semantic Memory Search Verification */}
      <Card>
        <CardHeader
          title="Memory Semantic Retrieval Verification"
          description="Test cosine distance retrieval against active episodic, procedural, and semantic memories"
        />
        <CardContent className="space-y-4">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              placeholder="Search relevant company memories (e.g. preferred CTA style, technical terminology)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 px-3 py-2 text-xs bg-surface border border-border rounded text-near-black focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
            <Button
              type="submit"
              variant="dark"
              size="md"
              isLoading={isRetrieving}
              disabled={!query.trim()}
              leftIcon={<Search className="w-4 h-4" />}
            >
              Search
            </Button>
          </form>

          {retrievedItems.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              {retrievedItems.map((item) => (
                <div
                  key={item.id}
                  className="p-3 bg-background border border-border rounded text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-near-black uppercase font-mono">
                      {item.memory_type}
                    </span>
                    <span className="text-primary font-mono font-semibold">
                      {(item.similarity_score * 100).toFixed(1)}% match
                    </span>
                  </div>
                  <p className="text-muted leading-relaxed line-clamp-3">
                    {item.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Memory List with Filter Tabs */}
      <Card>
        <CardHeader
          title={`Durable Memories (${memories.length})`}
          description="Chronological company memory ledger"
          action={
            <div className="flex items-center gap-2">
              <Select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                options={[
                  { label: "All Types", value: "ALL" },
                  { label: "Semantic", value: "SEMANTIC" },
                  { label: "Episodic", value: "EPISODIC" },
                  { label: "Procedural", value: "PROCEDURAL" },
                ]}
                className="text-xs py-1"
              />
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                options={[
                  { label: "All Statuses", value: "ALL" },
                  { label: "Active", value: "ACTIVE" },
                  { label: "Candidate", value: "CANDIDATE" },
                  { label: "Superseded", value: "SUPERSEDED" },
                  { label: "Archived", value: "ARCHIVED" },
                ]}
                className="text-xs py-1"
              />
            </div>
          }
        />
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 space-y-3">
              <div className="h-4 bg-gray-200 animate-pulse rounded w-3/4" />
              <div className="h-4 bg-gray-200 animate-pulse rounded w-1/2" />
            </div>
          ) : memories.length === 0 ? (
            <EmptyState
              icon={<Brain className="w-6 h-6" />}
              title="No company memories match filter."
              description="Record organizational facts, editorial preferences, or recurring style choices."
              actionLabel={canMutate ? "Record Memory" : undefined}
              onAction={canMutate ? () => setIsCreateOpen(true) : undefined}
            />
          ) : (
            <div className="divide-y divide-border">
              {memories.map((mem) => (
                <div
                  key={mem.id}
                  className="p-4 hover:bg-background/60 transition-colors flex flex-col sm:flex-row sm:items-start justify-between gap-4"
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[10px] font-mono font-semibold px-2 py-0.5 bg-background border border-border rounded text-near-black uppercase">
                        {mem.memory_type}
                      </span>
                      <StatusBadge status={mem.status} size="sm" />
                      <span className="text-[11px] text-muted font-mono">
                        Importance: {mem.importance}/5
                      </span>
                      <span className="text-[11px] text-muted">
                        Source: {mem.source.replace(/_/g, " ")}
                      </span>
                    </div>

                    <p className="text-xs text-near-black leading-relaxed pt-1">
                      {mem.content}
                    </p>

                    <div className="text-[11px] text-muted flex items-center gap-3 pt-1">
                      <span>Recorded: {new Date(mem.created_at).toLocaleDateString()}</span>
                      {mem.superseded_by_id && (
                        <span className="text-primary flex items-center gap-1 font-mono">
                          <GitFork className="w-3 h-3" />
                          Superseded by #{mem.superseded_by_id}
                        </span>
                      )}
                    </div>
                  </div>

                  {canMutate && mem.status === "ACTIVE" && (
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button
                        onClick={() => setMemoryToDelete(mem)}
                        className="p-1.5 text-muted hover:text-near-black hover:bg-gray-100 rounded transition-colors"
                        title={isAdmin ? "Delete permanently" : "Archive memory"}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Record Memory Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Record Durable Company Memory"
        description="Persists verified facts or editorial procedures with automated credential safety checking."
        maxWidth="md"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Select
            label="Memory Category"
            value={newType}
            onChange={(e) => setNewType(e.target.value as MemoryType)}
            options={[
              {
                label: "Semantic (Stable facts, market positioning, terminology)",
                value: "SEMANTIC",
              },
              {
                label: "Procedural (Writing preferences, CTA styles, editorial habits)",
                value: "PROCEDURAL",
              },
              {
                label: "Episodic (Historical events, past campaign decisions)",
                value: "EPISODIC",
              },
            ]}
          />

          <Textarea
            label="Memory Content"
            placeholder="e.g. Always refer to our multi-tenant feature as 'Dedicated Isolation Engine'. Keep conclusions focused on booking an architectural demo."
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            rows={4}
            required
            helperText="Sensitive data guards: API keys, tokens, and credentials are automatically rejected."
          />

          <Select
            label="Importance Rating"
            value={newImportance}
            onChange={(e) => setNewImportance(Number(e.target.value))}
            options={[
              { label: "1 — Minor contextual detail", value: 1 },
              { label: "2 — Low priority preference", value: 2 },
              { label: "3 — Standard operational guideline", value: 3 },
              { label: "4 — High importance rule", value: 4 },
              { label: "5 — Critical brand constraint", value: 5 },
            ]}
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsCreateOpen(false)}
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
              Save Memory
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete / Archive Confirmation Modal */}
      <ConfirmModal
        isOpen={!!memoryToDelete}
        onClose={() => setMemoryToDelete(null)}
        onConfirm={handleDelete}
        title={isAdmin ? "Delete Memory" : "Archive Memory"}
        message={
          isAdmin
            ? "Are you sure you want to permanently delete this memory item and its vector embedding?"
            : "Are you sure you want to soft-archive this memory? It will no longer participate in blog synthesis retrieval."
        }
        confirmLabel={isAdmin ? "Hard Delete" : "Archive Memory"}
        confirmVariant="primary"
        isLoading={isDeleting}
      />
    </div>
  );
};
