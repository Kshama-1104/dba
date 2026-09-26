import { apiClient } from "./client";
import {
  BlogDetail,
  BlogStatus,
  BlogSummary,
  BlogValidationResponse,
} from "../types";

export interface BlogGeneratePayload {
  topic_candidate_id: number;
  editor_instruction?: string | null;
}

export interface ListBlogsParams {
  skip?: number;
  limit?: number;
  status?: BlogStatus;
}

export const blogsApi = {
  listBlogs: (params?: ListBlogsParams) => {
    const query = new URLSearchParams();
    if (params?.skip !== undefined) query.set("skip", String(params.skip));
    if (params?.limit !== undefined) query.set("limit", String(params.limit));
    if (params?.status) query.set("status", params.status);
    const qs = query.toString();
    return apiClient.get<BlogSummary[]>(`/api/v1/blogs${qs ? `?${qs}` : ""}`);
  },

  getBlog: (id: number) =>
    apiClient.get<BlogDetail>(`/api/v1/blogs/${id}`),

  generateBlog: (payload: BlogGeneratePayload) =>
    apiClient.post<BlogDetail>("/api/v1/blogs/generate", payload),

  validateBlog: (id: number) =>
    apiClient.post<BlogValidationResponse>(`/api/v1/blogs/${id}/validate`),

  getValidation: (id: number) =>
    apiClient.get<BlogValidationResponse>(`/api/v1/blogs/${id}/validation`),
};
