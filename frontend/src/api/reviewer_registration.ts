import { apiClient } from "./client";

export const reviewerRegistrationApi = {
  start: (payload: { name: string; company_email: string }) =>
    apiClient.post("/api/v1/registration/reviewer", payload),
  
  sendOtp: (token: string) =>
    apiClient.post(`/api/v1/registration/reviewer/otp/send?registration_token=${encodeURIComponent(token)}`),
    
  verifyOtp: (token: string, otp: string) =>
    apiClient.post("/api/v1/registration/reviewer/otp/verify", {
      registration_token: token,
      otp,
    }),
    
  generateCaptcha: (token: string) =>
    apiClient.post(`/api/v1/registration/reviewer/captcha/generate?registration_token=${encodeURIComponent(token)}`),
    
  verifyCaptcha: (token: string, captcha: string) =>
    apiClient.post(`/api/v1/registration/reviewer/captcha/verify?registration_token=${encodeURIComponent(token)}&captcha=${encodeURIComponent(captcha)}`),
    
  complete: (payload: { registration_token: string; password: string; confirm_password: string; id_card_id?: number }) =>
    apiClient.post("/api/v1/registration/reviewer/complete", payload),
};
