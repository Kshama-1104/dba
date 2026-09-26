import { apiClient } from "./client";
import { BlogFormat, BlogFormatDefinition, BlogFormatListResponse } from "../types";

export interface BlogFormatCreatePayload {
  format_definition?: BlogFormatDefinition;
  title_structure?: string;
  introduction_structure?: string;
  heading_structure?: string;
  main_content_structure?: string;
  conclusion_structure?: string;
  call_to_action?: string;
  preferred_writing_style?: string;
  required_sections?: string[];
  optional_sections?: string[];
  seo_guidelines?: Record<string, unknown>;
  custom_rules?: string[];
}

export const blogFormatApi = {
  getActiveFormat: () =>
    apiClient.get<BlogFormat>("/api/v1/company/blog-format"),

  updateFormat: (payload: BlogFormatCreatePayload) =>
    apiClient.put<BlogFormat>("/api/v1/company/blog-format", payload),

  listVersions: () =>
    apiClient.get<BlogFormatListResponse>("/api/v1/company/blog-format/versions"),

  getVersion: (version: number) =>
    apiClient.get<BlogFormat>(`/api/v1/company/blog-format/versions/${version}`),

  activateVersion: (version: number) =>
    apiClient.post<BlogFormat>(
      `/api/v1/company/blog-format/versions/${version}/activate`
    ),
};
