import { apiClient } from "./client";
import { WordPressConnection, WordPressTestResponse } from "../types";

export interface WordPressConnectPayload {
  site_url: string;
  username: string;
  application_password: string;
  default_post_status?: "publish" | "draft";
}

export interface WordPressUpdatePayload {
  site_url?: string;
  username?: string;
  application_password?: string;
  status?: "ACTIVE" | "INACTIVE";
  default_post_status?: "publish" | "draft";
}

export const wordpressApi = {
  getConnection: () =>
    apiClient.get<WordPressConnection>("/api/v1/integrations/wordpress"),

  connect: (payload: WordPressConnectPayload) =>
    apiClient.post<WordPressConnection>(
      "/api/v1/integrations/wordpress",
      payload
    ),

  update: (payload: WordPressUpdatePayload) =>
    apiClient.put<WordPressConnection>(
      "/api/v1/integrations/wordpress",
      payload
    ),

  disconnect: () =>
    apiClient.delete<void>("/api/v1/integrations/wordpress"),

  testConnection: () =>
    apiClient.post<WordPressTestResponse>(
      "/api/v1/integrations/wordpress/test"
    ),
};
