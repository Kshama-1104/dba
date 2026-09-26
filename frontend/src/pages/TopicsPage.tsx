import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { topicsApi } from "../api/topics";
import { TopicCandidate, TopicStatus } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { TopicCard } from "../components/domain/TopicCard";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { Input } from "../components/ui/Input";
import { Textarea } from "../components/ui/Textarea";
import { Modal } from "../components/ui/Modal";
import { EmptyState } from "../components/ui/EmptyState";
import { Sparkles, Plus, AlertCircle, Shield, Filter } from "lucide-react";

export const TopicsPage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();
  const navigate = useNavigate();

  const [topics, setTopics] = useState<TopicCandidate[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Generate Modal state
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [focusTheme, setFocusTheme] = useState("");
  const [targetKeyword, setTargetKeyword] = useState("");

  // Custom Topic Modal state
  const [isCustomModalOpen, setIsCustomModalOpen] = useState(false);
  const [customTitle, setCustomTitle] = useState("");
  const [customAngle, setCustomAngle] = useState("");
  const [customRationale, setCustomRationale] = useState("");
  const [customKeyword, setCustomKeyword] = useState("");
  const [customAudience, setCustomAudience] = useState("");
  const [isSubmittingCustom, setIsSubmittingCustom] = useState(false);

  const isEditor = role === "editor";

  const loadTopics = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await topicsApi.listTopics(
        statusFilter !== "ALL" ? (statusFilter as TopicStatus) : undefined
      );
      setTopics(data);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Failed to load topic candidates."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTopics();
  }, [statusFilter]);

  const handleSelectTopic = async (topicId: number) => {
    if (!isEditor) return;
    setActionLoadingId(topicId);
    try {
      await topicsApi.selectTopic(topicId);
      success("Topic Selected", "Topic transitioned to SELECTED. You may now generate a blog draft.");
      await loadTopics();
    } catch (err: unknown) {
      toastError(
        "Selection Failed",
        err instanceof Error ? err.message : "Failed to select topic."
      );
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleRejectTopic = async (topicId: number) => {
    if (!isEditor) return;
    setActionLoadingId(topicId);
    try {
      await topicsApi.rejectTopic(topicId);
      success("Topic Rejected", "Topic marked as REJECTED and will not be re-suggested.");
      await loadTopics();
    } catch (err: unknown) {
      toastError(
        "Rejection Failed",
        err instanceof Error ? err.message : "Failed to reject topic."
      );
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isEditor) return;
    setIsGenerating(true);
    try {
      const candidates = await topicsApi.generateTopics({
        focus_theme: focusTheme.trim() || undefined,
        target_keyword: targetKeyword.trim() || undefined,
      });
      success(
        "Topics Generated",
        `Generated ${candidates.length} AI topic candidates based on company knowledge and RAG context.`
      );
      setIsGenerateModalOpen(false);
      setFocusTheme("");
      setTargetKeyword("");
      await loadTopics();
    } catch (err: unknown) {
      toastError(
        "Generation Failed",
        err instanceof Error ? err.message : "Failed to generate topic candidates."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCreateCustom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isEditor) return;
    setIsSubmittingCustom(true);
    try {
      await topicsApi.createCustomTopic({
        title: customTitle.trim(),
        angle: customAngle.trim(),
        rationale: customRationale.trim(),
        primary_keyword: customKeyword.trim(),
        target_audience: customAudience.trim() || undefined,
      });
      success("Topic Created", "Custom topic candidate created with status SUGGESTED.");
      setIsCustomModalOpen(false);
      setCustomTitle("");
      setCustomAngle("");
      setCustomRationale("");
      setCustomKeyword("");
      setCustomAudience("");
      await loadTopics();
    } catch (err: unknown) {
      toastError(
        "Creation Failed",
        err instanceof Error ? err.message : "Failed to create custom topic."
      );
    } finally {
      setIsSubmittingCustom(false);
    }
  };

  const handleGenerateBlog = (topicId: number) => {
    navigate(`/blogs?generateTopicId=${topicId}`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Topic Intelligence &amp; Idea Discovery
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 5 candidate discovery. Assembles company AI profile, RAG knowledge, long-term memory, and freshness scores to generate high-intent blog ideas.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {!isEditor ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-background border border-border rounded text-xs text-muted">
              <Shield className="w-3.5 h-3.5" />
              <span>View-only (Editor role required to generate/select topics)</span>
            </div>
          ) : (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setIsCustomModalOpen(true)}
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                Custom Topic
              </Button>
              <Button
                size="sm"
                variant="primary"
                onClick={() => setIsGenerateModalOpen(true)}
                leftIcon={<Sparkles className="w-3.5 h-3.5" />}
              >
                Generate AI Topics
              </Button>
            </>
          )}
        </div>
      </div>

      {errorMessage && (
        <div className="p-4 bg-primary-light border border-primary-border rounded-lg text-xs text-primary-dark flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center justify-between bg-surface p-4 border border-border rounded-lg shadow-subtle">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted">
          <Filter className="w-4 h-4 text-primary" />
          <span>Filter Status:</span>
        </div>
        <div className="w-48">
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            options={[
              { label: "All Candidates", value: "ALL" },
              { label: "Suggested", value: "suggested" },
              { label: "Selected", value: "selected" },
              { label: "Rejected", value: "rejected" },
              { label: "Used in Blog", value: "used" },
            ]}
          />
        </div>
      </div>

      {/* Topics Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="p-6 bg-surface border border-border rounded-lg space-y-3"
            >
              <div className="h-4 bg-gray-200 animate-pulse rounded w-1/3" />
              <div className="h-6 bg-gray-200 animate-pulse rounded w-3/4" />
              <div className="h-16 bg-gray-200 animate-pulse rounded w-full" />
            </div>
          ))}
        </div>
      ) : topics.length === 0 ? (
        <EmptyState
          icon={<Sparkles className="w-6 h-6" />}
          title="No AI topics have been generated for this company yet."
          description="Click 'Generate AI Topics' to trigger synthesis across your corporate knowledge base."
          actionLabel={isEditor ? "Generate AI Topics" : undefined}
          onAction={isEditor ? () => setIsGenerateModalOpen(true) : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {topics.map((topic) => (
            <TopicCard
              key={topic.id}
              topic={topic}
              onSelect={handleSelectTopic}
              onReject={handleRejectTopic}
              onGenerateBlog={handleGenerateBlog}
              isActionLoading={actionLoadingId === topic.id}
            />
          ))}
        </div>
      )}

      {/* Generate AI Topics Modal */}
      <Modal
        isOpen={isGenerateModalOpen}
        onClose={() => setIsGenerateModalOpen(false)}
        title="Generate AI Topic Candidates"
        description="Assembles Phase 1 AI profile, Phase 3 knowledge vectors, Phase 4 memory, and historical deduplication to propose high-relevance topics."
        maxWidth="md"
      >
        <form onSubmit={handleGenerate} className="space-y-4">
          <Input
            label="Optional Focus Theme"
            placeholder="e.g. Zero-Trust Security Architecture in Fintech"
            value={focusTheme}
            onChange={(e) => setFocusTheme(e.target.value)}
            helperText="Guide the topic synthesis toward a specific quarterly or campaign theme."
          />

          <Input
            label="Optional Target Primary Keyword"
            placeholder="e.g. multi-cloud access governance"
            value={targetKeyword}
            onChange={(e) => setTargetKeyword(e.target.value)}
            helperText="Optional target keyword to anchor relevance scores."
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsGenerateModalOpen(false)}
              disabled={isGenerating}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isGenerating}
              leftIcon={<Sparkles className="w-3.5 h-3.5" />}
            >
              Synthesize 3–5 Candidates
            </Button>
          </div>
        </form>
      </Modal>

      {/* Create Custom Topic Modal */}
      <Modal
        isOpen={isCustomModalOpen}
        onClose={() => setIsCustomModalOpen(false)}
        title="Supply Custom Topic Candidate"
        description="Allows an Editor to supply a bespoke topic candidate with deduplication safeguards."
        maxWidth="md"
      >
        <form onSubmit={handleCreateCustom} className="space-y-4">
          <Input
            label="Topic Title"
            placeholder="e.g. The Strategic Playbook for AI Pipeline Security"
            value={customTitle}
            onChange={(e) => setCustomTitle(e.target.value)}
            required
          />

          <Input
            label="Primary Keyword"
            placeholder="e.g. ai pipeline security"
            value={customKeyword}
            onChange={(e) => setCustomKeyword(e.target.value)}
            required
          />

          <Textarea
            label="Narrative Angle"
            placeholder="e.g. Contrast legacy firewalls with zero-trust model monitoring."
            value={customAngle}
            onChange={(e) => setCustomAngle(e.target.value)}
            rows={2}
            required
          />

          <Textarea
            label="Editorial Rationale"
            placeholder="e.g. Addresses executive buyer anxiety around regulatory compliance."
            value={customRationale}
            onChange={(e) => setCustomRationale(e.target.value)}
            rows={2}
            required
          />

          <Input
            label="Target Audience (Optional)"
            placeholder="e.g. Enterprise Chief Security Officers"
            value={customAudience}
            onChange={(e) => setCustomAudience(e.target.value)}
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsCustomModalOpen(false)}
              disabled={isSubmittingCustom}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmittingCustom}
            >
              Add Custom Candidate
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
