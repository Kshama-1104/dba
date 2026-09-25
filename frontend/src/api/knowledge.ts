import { apiClient } from "./client";
import {
  KnowledgeDocument,
  KnowledgeDocumentListResponse,
  KnowledgeRetrievalResponse,
} from "../types";

export interface KnowledgeRetrievalPayload {
  query: string;
  top_k?: number;
  document_ids?: number[];
}

export const knowledgeApi = {
  listDocuments: () =>
    apiClient.get<KnowledgeDocumentListResponse>(
      "/api/v1/company/knowledge/documents"
    ),

  getDocument: (id: number) =>
    apiClient.get<KnowledgeDocument>(
      `/api/v1/company/knowledge/documents/${id}`
    ),

  uploadDocument: (file: File, title?: string, description?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (title) formData.append("title", title);
    if (description) formData.append("description", description);
    return apiClient.upload<KnowledgeDocument>(
      "/api/v1/company/knowledge/documents",
      formData
    );
  },

  deleteDocument: (id: number) =>
    apiClient.delete<{ message: string; id: number }>(
      `/api/v1/company/knowledge/documents/${id}`
    ),

  retrieve: (payload: KnowledgeRetrievalPayload) =>
    apiClient.post<KnowledgeRetrievalResponse>(
      "/api/v1/company/knowledge/retrieve",
      payload
    ),
};
