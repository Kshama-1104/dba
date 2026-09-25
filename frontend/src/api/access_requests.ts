import { apiClient } from "./client";

export interface AccessRequest {
  id: number;
  company_id: number;
  requester_id: number;
  approver_id: number;
  request_type: string;
  status: string;
  expires_at: string;
  responded_at: string | null;
  created_at: string;
}

export interface AccessRequestDecisionResponse {
  message: string;
  access_request: AccessRequest;
  requester: any;
  temporary_password?: string;
}

export const accessRequestsApi = {
  list: () =>
    apiClient.get<AccessRequest[]>("/api/v1/access-requests"),

  decide: (requestId: number, decision: "accepted" | "rejected") =>
    apiClient.patch<AccessRequestDecisionResponse>(`/api/v1/access-requests/${requestId}/decision`, {
      decision,
    }),
};
