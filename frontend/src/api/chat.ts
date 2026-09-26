import { apiClient } from "./client";
import {
  BlogChatResponse,
  BlogChatThread,
  BlogRevisionDetail,
  BlogRevisionSummary,
} from "../types";

export interface SendChatMessagePayload {
  message: string;
  base_revision_id: number;
  client_message_id?: string;
}

export const chatApi = {
  getChatHistory: (blogId: number, skip = 0, limit = 50) =>
    apiClient.get<BlogChatThread>(
      `/api/v1/blogs/${blogId}/chat?skip=${skip}&limit=${limit}`
    ),

  sendMessage: (blogId: number, payload: SendChatMessagePayload) =>
    apiClient.post<BlogChatResponse>(`/api/v1/blogs/${blogId}/chat`, payload),

  listRevisions: (blogId: number, skip = 0, limit = 50) =>
    apiClient.get<BlogRevisionSummary[]>(
      `/api/v1/blogs/${blogId}/revisions?skip=${skip}&limit=${limit}`
    ),

  getRevisionDetail: (blogId: number, revisionId: number) =>
    apiClient.get<BlogRevisionDetail>(
      `/api/v1/blogs/${blogId}/revisions/${revisionId}`
    ),

  restoreRevision: (
    blogId: number,
    revisionId: number,
    restoreSummary?: string
  ) =>
    apiClient.post<BlogRevisionDetail>(
      `/api/v1/blogs/${blogId}/revisions/${revisionId}/restore`,
      restoreSummary ? { restore_summary: restoreSummary } : {}
    ),
};
