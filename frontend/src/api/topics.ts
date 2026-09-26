import { apiClient } from "./client";
import { TopicCandidate, TopicStatus } from "../types";

export interface TopicGeneratePayload {
  focus_theme?: string | null;
  target_keyword?: string | null;
}

export interface CustomTopicPayload {
  title: string;
  angle: string;
  rationale: string;
  primary_keyword: string;
  target_audience?: string | null;
}

export const topicsApi = {
  listTopics: (status?: TopicStatus) => {
    const qs = status ? `?status=${status}` : "";
    return apiClient.get<TopicCandidate[]>(`/api/v1/company/topics${qs}`);
  },

  getTopic: (id: number) =>
    apiClient.get<TopicCandidate>(`/api/v1/company/topics/${id}`),

  generateTopics: (payload?: TopicGeneratePayload) =>
    apiClient.post<TopicCandidate[]>("/api/v1/company/topics/generate", payload || {}),

  createCustomTopic: (payload: CustomTopicPayload) =>
    apiClient.post<TopicCandidate>("/api/v1/company/topics/custom", payload),

  selectTopic: (id: number) =>
    apiClient.post<TopicCandidate>(`/api/v1/company/topics/${id}/select`),

  rejectTopic: (id: number) =>
    apiClient.post<TopicCandidate>(`/api/v1/company/topics/${id}/reject`),
};
