import { apiClient } from "./client";

export const editorRegistrationApi = {
  start: (payload: { name: string; company_email: string }) =>
    apiClient.post("/api/v1/registration/editor", payload),
  
  sendOtp: (token: string) =>
    apiClient.post(`/api/v1/registration/editor/otp/send?registration_token=${encodeURIComponent(token)}`),
    
  verifyOtp: (token: string, otp: string) =>
    apiClient.post("/api/v1/registration/editor/otp/verify", {
      registration_token: token,
      otp,
    }),
    
  generateCaptcha: (token: string) =>
    apiClient.post(`/api/v1/registration/editor/captcha/generate?registration_token=${encodeURIComponent(token)}`),
    
  verifyCaptcha: (token: string, captcha: string) =>
    apiClient.post(`/api/v1/registration/editor/captcha/verify?registration_token=${encodeURIComponent(token)}&captcha=${encodeURIComponent(captcha)}`),
    
  getReviewers: (token: string) =>
    apiClient.get(`/api/v1/registration/editor/reviewers?registration_token=${encodeURIComponent(token)}`),
    
  selectReviewer: (token: string, reviewerId: number) =>
    apiClient.post("/api/v1/registration/editor/reviewer/select", {
      registration_token: token,
      reviewer_id: reviewerId,
    }),
    
  complete: (payload: { registration_token: string; password: string; confirm_password: string; id_card_id?: number }) =>
    apiClient.post("/api/v1/registration/editor/complete", payload),
};
