import { apiClient } from "./client";

export interface CompanyRegistrationPayload {
  company_name: string;
  company_description: string;
  logo_url: string;
  company_type: string;
  industry: string;
  country_region: string;
  company_email: string;
}

export interface RegistrationSessionResponse {
  message: string;
  registration_token: string;
  current_step: number;
  next_step: number;
}

export interface OtpSendResponse {
  message: string;
  development_otp: string;
}

export interface OtpVerifyResponse {
  message: string;
  otp_verified: boolean;
  next_step: string;
}

export interface CaptchaGenerateResponse {
  message: string;
  development_captcha: string;
}

export interface CaptchaVerifyResponse {
  message: string;
  captcha_verified: boolean;
  next_step: number;
}

export interface CompleteRegistrationPayload {
  registration_token: string;
  password: string;
  confirm_password: string;
}

export interface CompleteRegistrationResponse {
  message: string;
  company_id: number;
  company_name: string;
  company_email: string;
  role: string;
}

export const registrationApi = {
  /** Step 1: Submit company information to start a registration session. */
  startRegistration: (payload: CompanyRegistrationPayload) =>
    apiClient.post<RegistrationSessionResponse>(
      "/api/v1/registration/company",
      payload
    ),

  /** Step 2a: Request an OTP to be sent to the company email. */
  sendOtp: (registrationToken: string) =>
    apiClient.post<OtpSendResponse>(
      `/api/v1/registration/otp/send?registration_token=${encodeURIComponent(registrationToken)}`
    ),

  /** Step 2b: Verify the 6-digit OTP. */
  verifyOtp: (registrationToken: string, otp: string) =>
    apiClient.post<OtpVerifyResponse>("/api/v1/registration/otp/verify", {
      registration_token: registrationToken,
      otp,
    }),

  /** Step 2c: Generate a CAPTCHA challenge. */
  generateCaptcha: (registrationToken: string) =>
    apiClient.post<CaptchaGenerateResponse>(
      `/api/v1/registration/captcha/generate?registration_token=${encodeURIComponent(registrationToken)}`
    ),

  /** Step 2d: Verify the CAPTCHA answer. */
  verifyCaptcha: (registrationToken: string, captcha: string) =>
    apiClient.post<CaptchaVerifyResponse>(
      `/api/v1/registration/captcha/verify?registration_token=${encodeURIComponent(registrationToken)}&captcha=${encodeURIComponent(captcha)}`
    ),

  /** Step 3: Set the admin password and complete account creation. */
  completeRegistration: (payload: CompleteRegistrationPayload) =>
    apiClient.post<CompleteRegistrationResponse>(
      "/api/v1/registration/company/complete",
      payload
    ),
};
