import { apiClient } from "./client";
import { LoginResponse, User } from "../types";

export interface LoginPayload {
  email: string;
  password: string;
}

export interface SetPermanentPasswordPayload {
  current_temporary_password: string;
  new_password: string;
  confirm_password: string;
}

export const authApi = {
  login: (payload: LoginPayload) =>
    apiClient.post<LoginResponse>("/api/v1/auth/login", payload),

  getMe: () =>
    apiClient.get<User>("/api/v1/me"),

  setPermanentPassword: (payload: SetPermanentPasswordPayload) =>
    apiClient.post<{ message: string; requires_password_setup: boolean }>(
      "/api/v1/auth/set-permanent-password",
      payload
    ),
};
