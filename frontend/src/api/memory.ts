import { apiClient } from "./client";
import {
  CompanyMemory,
  CompanyMemoryListResponse,
  MemoryConflictResolutionResponse,
  MemoryConfidence,
  MemoryRetrievalResponse,
  MemorySource,
  MemoryStatus,
  MemoryType,
} from "../types";

export interface MemoryCreatePayload {
  memory_type: MemoryType;
  content: string;
  source?: MemorySource;
  confidence?: MemoryConfidence;
  importance?: number;
  status?: MemoryStatus;
  metadata_payload?: Record<string, unknown> | null;
}

export interface MemoryUpdatePayload {
  content?: string;
  memory_type?: MemoryType;
  confidence?: MemoryConfidence;
  importance?: number;
  status?: MemoryStatus;
  metadata_payload?: Record<string, unknown> | null;
}

export interface MemoryListParams {
  memory_type?: MemoryType;
  status?: MemoryStatus;
  active_only?: boolean;
}

export interface MemoryRetrievalPayload {
  query: string;
  memory_type?: MemoryType;
  top_k?: number;
  include_candidates?: boolean;
}

export const memoryApi = {
  listMemories: (params?: MemoryListParams) => {
    const query = new URLSearchParams();
    if (params?.memory_type) query.set("memory_type", params.memory_type);
    if (params?.status) query.set("status", params.status);
    if (params?.active_only !== undefined) query.set("active_only", String(params.active_only));
    const qs = query.toString();
    return apiClient.get<CompanyMemoryListResponse>(
      `/api/v1/company/memory${qs ? `?${qs}` : ""}`
    );
  },

  getMemory: (id: number) =>
    apiClient.get<CompanyMemory>(`/api/v1/company/memory/${id}`),

  createMemory: (payload: MemoryCreatePayload) =>
    apiClient.post<CompanyMemory>("/api/v1/company/memory", payload),

  updateMemory: (id: number, payload: MemoryUpdatePayload) =>
    apiClient.put<CompanyMemory>(`/api/v1/company/memory/${id}`, payload),

  supersedeMemory: (id: number, payload: MemoryCreatePayload) =>
    apiClient.post<CompanyMemory>(`/api/v1/company/memory/${id}/supersede`, payload),

  deleteMemory: (id: number, hardDelete = false) =>
    apiClient.delete<{ message: string; id: number }>(
      `/api/v1/company/memory/${id}?hard_delete=${hardDelete}`
    ),

  retrieve: (payload: MemoryRetrievalPayload) =>
    apiClient.post<MemoryRetrievalResponse>(
      "/api/v1/company/memory/retrieve",
      payload
    ),

  resolveConflicts: () =>
    apiClient.post<MemoryConflictResolutionResponse>(
      "/api/v1/company/memory/resolve-conflicts"
    ),
};
