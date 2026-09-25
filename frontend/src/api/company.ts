import { apiClient } from "./client";
import {
  CompanyAIProfile,
  CompanyDashboardData,
  CompanySettings,
  TeamMember,
} from "../types";

export interface CompanyAIProfileUpdatePayload {
  products_services?: string | null;
  target_audience?: string | null;
  preferred_writing_style?: string | null;
  brand_voice?: string | null;
  marketing_goals?: string | null;
  company_guidelines?: string | null;
  upcoming_projects?: string | null;
  partner_companies?: string | null;
  achievements?: string | null;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export const companyApi = {
  getDashboard: () =>
    apiClient.get<CompanyDashboardData>("/api/v1/company/dashboard"),

  getAIProfile: () =>
    apiClient.get<CompanyAIProfile>("/api/v1/company/ai-profile"),

  updateAIProfile: (payload: CompanyAIProfileUpdatePayload) =>
    apiClient.put<CompanyAIProfile>("/api/v1/company/ai-profile", payload),

  getSettings: () =>
    apiClient.get<CompanySettings>("/api/v1/company/settings"),

  updateNotificationEmail: (notification_email: string) =>
    apiClient.patch<{ message: string; notification_email: string }>(
      "/api/v1/company/settings/notification-email",
      { notification_email }
    ),

  changePassword: (payload: ChangePasswordPayload) =>
    apiClient.patch<{ message: string }>(
      "/api/v1/company/settings/password",
      payload
    ),

  getReviewers: () =>
    apiClient.get<{ count: number; reviewers: TeamMember[] }>(
      "/api/v1/company/reviewers"
    ),

  getEditors: () =>
    apiClient.get<{ count: number; editors: TeamMember[] }>(
      "/api/v1/company/editors"
    ),
};
