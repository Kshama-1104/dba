import React, { useEffect, useState } from "react";
import { knowledgeApi } from "../api/knowledge";
import { KnowledgeDocument, RetrievedChunk } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { StatusBadge } from "../components/ui/StatusBadge";
import { EmptyState } from "../components/ui/EmptyState";
import { ConfirmModal } from "../components/ui/ConfirmModal";
import { Modal } from "../components/ui/Modal";
import {
  BookOpen,
  Upload,
  Trash2,
  Search,
  FileText,
  AlertCircle,
  Database,
  Layers,
} from "lucide-react";

export const KnowledgePage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();

  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docTitle, setDocTitle] = useState("");
  const [docDescription, setDocDescription] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  // Delete modal state
  const [docToDelete, setDocToDelete] = useState<KnowledgeDocument | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // RAG Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<RetrievedChunk[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const canMutate = role === "company_admin" || role === "editor";

  const loadDocuments = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await knowledgeApi.listDocuments();
      setDocuments(resp.documents);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load company knowledge documents."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !canMutate) return;

    setIsUploading(true);
    try {
      await knowledgeApi.uploadDocument(
        selectedFile,
        docTitle.trim() || undefined,
        docDescription.trim() || undefined
      );
      success("Document Ingested", `"${selectedFile.name}" uploaded and chunked with pgvector embeddings.`);
      setIsUploadOpen(false);
      setSelectedFile(null);
      setDocTitle("");
      setDocDescription("");
      await loadDocuments();
    } catch (err: unknown) {
      toastError(
        "Upload Failed",
        err instanceof Error ? err.message : "Failed to ingest document."
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!docToDelete || !canMutate) return;
    setIsDeleting(true);
    try {
      await knowledgeApi.deleteDocument(docToDelete.id);
      success("Document Removed", `"${docToDelete.original_filename}" and its chunks were deleted.`);
      setDocToDelete(null);
      await loadDocuments();
    } catch (err: unknown) {
      toastError(
        "Delete Failed",
        err instanceof Error ? err.message : "Failed to delete knowledge document."
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const resp = await knowledgeApi.retrieve({
        query: searchQuery.trim(),
        top_k: 4,
      });
      setSearchResults(resp.results);
    } catch (err: unknown) {
      toastError(
        "Retrieval Failed",
        err instanceof Error ? err.message : "Failed to retrieve relevant chunks."
      );
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Company Knowledge Base &amp; RAG
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 3 grounded vector store. Ingested documents (PDF, DOCX, TXT) are chunked and vectorized for semantic retrieval during blog generation.
          </p>
        </div>

        {canMutate && (
          <Button
            size="sm"
            variant="primary"
            onClick={() => setIsUploadOpen(true)}
            leftIcon={<Upload className="w-3.5 h-3.5" />}
          >
            Upload Document
          </Button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-primary-light border border-primary-border rounded-lg text-xs text-primary-dark flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Semantic Retrieval Playground */}
      <Card>
        <CardHeader
          title="Semantic Retrieval Verification (RAG Engine)"
          description="Test cosine similarity search against active company knowledge embeddings"
        />
        <CardContent className="space-y-4">
          <form onSubmit={handleSearch} className="flex gap-2">
            <Input
              type="text"
              placeholder="Enter search query (e.g. enterprise pricing model, deployment steps)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1"
            />
            <Button
              type="submit"
              variant="dark"
              size="md"
              isLoading={isSearching}
              disabled={!searchQuery.trim()}
              leftIcon={<Search className="w-4 h-4" />}
            >
              Retrieve
            </Button>
          </form>

          {searchResults.length > 0 && (
            <div className="space-y-2 pt-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">
                Top Relevant Ingested Chunks ({searchResults.length})
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {searchResults.map((chunk) => (
                  <div
                    key={chunk.chunk_id}
                    className="p-3 bg-background border border-border rounded text-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-near-black truncate">
                        {chunk.title || `Doc #${chunk.document_id}`}
                      </span>
                      <span className="text-primary font-mono font-semibold">
                        {(chunk.similarity_score * 100).toFixed(1)}% match
                      </span>
                    </div>
                    <p className="text-muted leading-relaxed line-clamp-4">
                      {chunk.content}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Documents Table */}
      <Card>
        <CardHeader
          title={`Ingested Reference Documents (${documents.length})`}
          description="Tenant-isolated vector collections"
        />
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 space-y-3">
              <div className="h-4 bg-gray-200 animate-pulse rounded w-3/4" />
              <div className="h-4 bg-gray-200 animate-pulse rounded w-1/2" />
            </div>
          ) : documents.length === 0 ? (
            <EmptyState
              icon={<Database className="w-6 h-6" />}
              title="No documents ingested into company knowledge base yet."
              description="Upload PDF, DOCX, or TXT documentation to provide factual grounding for blog generation."
              actionLabel={canMutate ? "Upload Document" : undefined}
              onAction={canMutate ? () => setIsUploadOpen(true) : undefined}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-background border-b border-border text-[11px] font-semibold uppercase tracking-wider text-muted">
                  <tr>
                    <th className="py-3 px-4">Title / Filename</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Chunks</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Ingested At</th>
                    {canMutate && <th className="py-3 px-4 text-right">Action</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {documents.map((doc) => (
                    <tr
                      key={doc.id}
                      className="hover:bg-background/80 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted flex-shrink-0" />
                          <div>
                            <p className="font-semibold text-near-black">
                              {doc.title || doc.original_filename}
                            </p>
                            {doc.title && (
                              <p className="text-[11px] text-muted">
                                {doc.original_filename}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-muted font-mono text-[11px]">
                        {doc.content_type}
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center gap-1 font-mono text-near-black font-semibold">
                          <Layers className="w-3.5 h-3.5 text-primary" />
                          {doc.chunk_count}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={doc.status} size="sm" />
                        {doc.processing_error && (
                          <span
                            title={doc.processing_error}
                            className="block text-[10px] text-primary-dark truncate max-w-xs mt-0.5"
                          >
                            {doc.processing_error}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-muted whitespace-nowrap">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      {canMutate && (
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => setDocToDelete(doc)}
                            className="p-1.5 text-muted hover:text-near-black hover:bg-gray-100 rounded transition-colors"
                            title="Delete document"
                            aria-label={`Delete ${doc.original_filename}`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
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

      {/* Upload Modal */}
      <Modal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        title="Upload Knowledge Document"
        description="Synchronous ingestion extracts text, generates 384-dimensional dense vector embeddings, and stores chunks under strict company isolation."
        maxWidth="md"
      >
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-1.5">
              Select Document File (PDF, DOCX, TXT)
            </label>
            <input
              type="file"
              accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              required
              className="w-full text-xs text-muted file:mr-3 file:py-2 file:px-3 file:rounded file:border file:border-border file:text-xs file:font-semibold file:bg-surface file:text-near-black hover:file:bg-background"
            />
          </div>

          <Input
            label="Custom Title (Optional)"
            placeholder="e.g. Enterprise Security Architecture Whitepaper"
            value={docTitle}
            onChange={(e) => setDocTitle(e.target.value)}
          />

          <Input
            label="Description (Optional)"
            placeholder="Brief overview of document contents"
            value={docDescription}
            onChange={(e) => setDocDescription(e.target.value)}
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsUploadOpen(false)}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isUploading}
              disabled={!selectedFile}
            >
              {isUploading ? "Ingesting..." : "Ingest Document"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={!!docToDelete}
        onClose={() => setDocToDelete(null)}
        onConfirm={handleDelete}
        title="Delete Knowledge Document"
        message={`Are you sure you want to delete "${docToDelete?.original_filename}"? All associated ${docToDelete?.chunk_count ?? 0} vector chunks and embeddings will be permanently purged.`}
        confirmLabel="Delete Document"
        confirmVariant="primary"
        isLoading={isDeleting}
      />
    </div>
  );
};
