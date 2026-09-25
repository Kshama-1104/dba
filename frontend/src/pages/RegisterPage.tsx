import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import {
  Building2,
  Mail,
  Globe,
  Briefcase,
  Factory,
  MapPin,
  Link as LinkIcon,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  ShieldCheck,
  KeyRound,
  Lock,
  Eye,
  EyeOff,
  CheckCircle2,
} from "lucide-react";
import { registrationApi } from "../api/registration";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type RegistrationStep = 1 | 2 | 3 | 4;

interface CompanyForm {
  company_name: string;
  company_description: string;
  logo_url: string;
  company_type: string;
  industry: string;
  country_region: string;
  company_email: string;
}

const INITIAL_COMPANY_FORM: CompanyForm = {
  company_name: "",
  company_description: "",
  logo_url: "",
  company_type: "",
  industry: "",
  country_region: "",
  company_email: "",
};

/* ------------------------------------------------------------------ */
/*  Step indicator                                                     */
/* ------------------------------------------------------------------ */

const STEPS: { label: string; icon: React.ReactNode }[] = [
  { label: "Company Info", icon: <Building2 className="w-4 h-4" /> },
  { label: "Verify Email", icon: <ShieldCheck className="w-4 h-4" /> },
  { label: "Set Password", icon: <KeyRound className="w-4 h-4" /> },
  { label: "Done", icon: <CheckCircle2 className="w-4 h-4" /> },
];

const StepIndicator: React.FC<{ current: RegistrationStep }> = ({ current }) => (
  <div className="flex items-center justify-between mb-8 px-2">
    {STEPS.map((s, i) => {
      const stepNum = (i + 1) as RegistrationStep;
      const isActive = stepNum === current;
      const isDone = stepNum < current;
      return (
        <React.Fragment key={stepNum}>
          {i > 0 && (
            <div
              className={`flex-1 h-px mx-2 transition-colors duration-200 ${
                isDone ? "bg-primary" : "bg-border"
              }`}
            />
          )}
          <div className="flex flex-col items-center gap-1.5 min-w-[64px]">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors duration-200 ${
                isDone
                  ? "bg-primary text-white"
                  : isActive
                    ? "bg-primary text-white"
                    : "bg-background border border-border text-muted"
              }`}
            >
              {isDone ? <Check className="w-4 h-4" /> : s.icon}
            </div>
            <span
              className={`text-[10px] font-medium leading-none ${
                isActive || isDone ? "text-near-black" : "text-muted"
              }`}
            >
              {s.label}
            </span>
          </div>
        </React.Fragment>
      );
    })}
  </div>
);

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();

  /* Shared state */
  const [step, setStep] = useState<RegistrationStep>(1);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [registrationToken, setRegistrationToken] = useState("");

  /* Step 1 — company form */
  const [form, setForm] = useState<CompanyForm>(INITIAL_COMPANY_FORM);

  /* Step 2 — OTP + CAPTCHA */
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpVerified, setOtpVerified] = useState(false);
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const [captcha, setCaptcha] = useState("");
  const [captchaGenerated, setCaptchaGenerated] = useState(false);
  const [captchaVerified, setCaptchaVerified] = useState(false);
  const [devCaptcha, setDevCaptcha] = useState<string | null>(null);

  /* Step 3 — password */
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  /* Step 4 — success data */
  const [companyName, setCompanyName] = useState("");

  /* ---- helpers ---- */
  const setField = useCallback(
    (field: keyof CompanyForm, value: string) =>
      setForm((prev) => ({ ...prev, [field]: value })),
    []
  );

  const clearError = () => setError(null);

  /* ---------------------------------------------------------------- */
  /*  Step 1 — Submit company info                                     */
  /* ---------------------------------------------------------------- */
  const handleStep1 = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    /* basic client-side checks */
    const missing = Object.entries(form).find(([, v]) => !v.trim());
    if (missing) {
      setError("All fields are required.");
      return;
    }

    setIsLoading(true);
    try {
      const res = await registrationApi.startRegistration(form);
      setRegistrationToken(res.registration_token);
      setStep(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Step 2a — Send OTP                                               */
  /* ---------------------------------------------------------------- */
  const handleSendOtp = async () => {
    clearError();
    setIsLoading(true);
    try {
      const res = await registrationApi.sendOtp(registrationToken);
      setOtpSent(true);
      setDevOtp(res.development_otp ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send OTP.");
    } finally {
      setIsLoading(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Step 2b — Verify OTP                                             */
  /* ---------------------------------------------------------------- */
  const handleVerifyOtp = async () => {
    clearError();
    if (otp.length !== 6) {
      setError("OTP must be exactly 6 digits.");
      return;
    }
    setIsLoading(true);
    try {
      const res = await registrationApi.verifyOtp(registrationToken, otp);
      if (res.otp_verified) {
        setOtpVerified(true);
      } else {
        setError("Invalid OTP. Please try again.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "OTP verification failed.");
    } finally {
      setIsLoading(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Step 2c — Generate CAPTCHA                                       */
  /* ---------------------------------------------------------------- */
  const handleGenerateCaptcha = async () => {
    clearError();
    setIsLoading(true);
    try {
      const res = await registrationApi.generateCaptcha(registrationToken);
      setCaptchaGenerated(true);
      setDevCaptcha(res.development_captcha ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate CAPTCHA.");
    } finally {
      setIsLoading(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Step 2d — Verify CAPTCHA                                         */
  /* ---------------------------------------------------------------- */
  const handleVerifyCaptcha = async () => {
    clearError();
    if (!captcha.trim()) {
      setError("Please enter the CAPTCHA answer.");
      return;
    }
    setIsLoading(true);
    try {
      const res = await registrationApi.verifyCaptcha(registrationToken, captcha.trim());
      if (res.captcha_verified) {
        setCaptchaVerified(true);
        setStep(3);
      } else {
        setError("Invalid CAPTCHA. Please try again.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "CAPTCHA verification failed.");
    } finally {
      setIsLoading(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Step 3 — Set password & complete                                 */
  /* ---------------------------------------------------------------- */
  const handleStep3 = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsLoading(true);
    try {
      const res = await registrationApi.completeRegistration({
        registration_token: registrationToken,
        password,
        confirm_password: confirmPassword,
      });
      setCompanyName(res.company_name);
      setStep(4);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Account creation failed.");
    } finally {
      setIsLoading(false);
    }
  };

  /* ================================================================ */
  /*  RENDER                                                           */
  /* ================================================================ */

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center items-center p-4 selection:bg-primary-light selection:text-primary-dark">
      <div className="w-full max-w-lg">
        {/* Brand */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded bg-black text-white font-bold text-lg mb-3 tracking-wider">
            DB
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-near-black">
            DailyBlog <span className="text-primary">AI</span>
          </h1>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Create your company admin account
          </p>
        </div>

        {/* Card */}
        <div className="bg-surface border border-border rounded-lg shadow-card p-6 sm:p-8">
          <StepIndicator current={step} />

          {/* Error banner */}
          {error && (
            <div className="mb-5 p-3.5 bg-primary-light border border-primary-border rounded text-xs text-primary-dark flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span className="leading-relaxed">{error}</span>
            </div>
          )}

          {/* ---- STEP 1 ---- */}
          {step === 1 && (
            <form onSubmit={handleStep1} className="space-y-4">
              <h2 className="text-base font-semibold text-near-black mb-1">
                Company Information
              </h2>
              <p className="text-xs text-muted mb-4">
                Tell us about your organisation to get started.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Company Name"
                  placeholder="Acme Corp"
                  value={form.company_name}
                  onChange={(e) => setField("company_name", e.target.value)}
                  required
                  disabled={isLoading}
                />
                <Input
                  label="Company Email"
                  type="email"
                  placeholder="admin@acme.com"
                  value={form.company_email}
                  onChange={(e) => setField("company_email", e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-1.5">
                  Company Description <span className="text-primary ml-1">*</span>
                </label>
                <textarea
                  className="w-full px-3 py-2 text-sm bg-surface border border-border rounded text-near-black placeholder:text-muted/60 transition-colors duration-150 focus:border-primary focus:ring-1 focus:ring-primary hover:border-gray-400 resize-y min-h-[80px]"
                  rows={3}
                  placeholder="Brief description of your company..."
                  value={form.company_description}
                  onChange={(e) => setField("company_description", e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Logo URL"
                  placeholder="https://example.com/logo.png"
                  value={form.logo_url}
                  onChange={(e) => setField("logo_url", e.target.value)}
                  required
                  disabled={isLoading}
                />
                <Input
                  label="Company Type"
                  placeholder="e.g. Technology, Agency"
                  value={form.company_type}
                  onChange={(e) => setField("company_type", e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Industry"
                  placeholder="e.g. SaaS, Healthcare"
                  value={form.industry}
                  onChange={(e) => setField("industry", e.target.value)}
                  required
                  disabled={isLoading}
                />
                <Input
                  label="Country / Region"
                  placeholder="e.g. United States"
                  value={form.country_region}
                  onChange={(e) => setField("country_region", e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => navigate("/login")}
                  className="text-xs text-muted hover:text-near-black transition-colors inline-flex items-center gap-1"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back to Sign In
                </button>
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  isLoading={isLoading}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Continue
                </Button>
              </div>
            </form>
          )}

          {/* ---- STEP 2 ---- */}
          {step === 2 && (
            <div className="space-y-5">
              <h2 className="text-base font-semibold text-near-black mb-1">
                Verify Your Email
              </h2>
              <p className="text-xs text-muted mb-2">
                We need to confirm ownership of{" "}
                <span className="font-semibold text-near-black">{form.company_email}</span>.
              </p>

              {/* OTP Section */}
              <div className="p-4 border border-border rounded-lg bg-background space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-near-black uppercase tracking-wider">
                  <Mail className="w-4 h-4 text-primary" />
                  Email OTP Verification
                  {otpVerified && <Check className="w-4 h-4 text-green-600 ml-auto" />}
                </div>

                {!otpSent && !otpVerified && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleSendOtp}
                    isLoading={isLoading}
                  >
                    Send OTP
                  </Button>
                )}

                {otpSent && !otpVerified && (
                  <>
                    {devOtp && (
                      <div className="p-2.5 bg-primary-light border border-primary-border rounded text-xs text-primary-dark">
                        <span className="font-semibold">Dev OTP:</span> {devOtp}
                      </div>
                    )}
                    <div className="flex items-end gap-2">
                      <Input
                        label="6-Digit OTP"
                        placeholder="000000"
                        value={otp}
                        onChange={(e) => {
                          const v = e.target.value.replace(/\D/g, "").slice(0, 6);
                          setOtp(v);
                        }}
                        maxLength={6}
                        disabled={isLoading}
                      />
                      <Button
                        variant="primary"
                        size="md"
                        onClick={handleVerifyOtp}
                        isLoading={isLoading}
                        disabled={otp.length !== 6}
                      >
                        Verify
                      </Button>
                    </div>
                    <button
                      type="button"
                      onClick={handleSendOtp}
                      className="text-xs text-primary hover:text-primary-dark transition-colors font-medium"
                      disabled={isLoading}
                    >
                      Resend OTP
                    </button>
                  </>
                )}

                {otpVerified && (
                  <p className="text-xs text-green-700 font-medium flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    OTP verified successfully
                  </p>
                )}
              </div>

              {/* CAPTCHA Section */}
              {otpVerified && (
                <div className="p-4 border border-border rounded-lg bg-background space-y-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-near-black uppercase tracking-wider">
                    <ShieldCheck className="w-4 h-4 text-primary" />
                    CAPTCHA Verification
                    {captchaVerified && <Check className="w-4 h-4 text-green-600 ml-auto" />}
                  </div>

                  {!captchaGenerated && !captchaVerified && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleGenerateCaptcha}
                      isLoading={isLoading}
                    >
                      Generate CAPTCHA
                    </Button>
                  )}

                  {captchaGenerated && !captchaVerified && (
                    <>
                      {devCaptcha && (
                        <div className="p-2.5 bg-primary-light border border-primary-border rounded text-xs text-primary-dark">
                          <span className="font-semibold">Dev CAPTCHA:</span> {devCaptcha}
                        </div>
                      )}
                      <div className="flex items-end gap-2">
                        <Input
                          label="CAPTCHA Answer"
                          placeholder="Enter answer"
                          value={captcha}
                          onChange={(e) => setCaptcha(e.target.value)}
                          disabled={isLoading}
                        />
                        <Button
                          variant="primary"
                          size="md"
                          onClick={handleVerifyCaptcha}
                          isLoading={isLoading}
                          disabled={!captcha.trim()}
                        >
                          Verify
                        </Button>
                      </div>
                      <button
                        type="button"
                        onClick={handleGenerateCaptcha}
                        className="text-xs text-primary hover:text-primary-dark transition-colors font-medium"
                        disabled={isLoading}
                      >
                        Refresh CAPTCHA
                      </button>
                    </>
                  )}

                  {captchaVerified && (
                    <p className="text-xs text-green-700 font-medium flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      CAPTCHA verified — proceeding to password setup
                    </p>
                  )}
                </div>
              )}

              {/* Navigation */}
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => navigate("/login")}
                  className="text-xs text-muted hover:text-near-black transition-colors inline-flex items-center gap-1"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back to Sign In
                </button>
              </div>
            </div>
          )}

          {/* ---- STEP 3 ---- */}
          {step === 3 && (
            <form onSubmit={handleStep3} className="space-y-4">
              <h2 className="text-base font-semibold text-near-black mb-1">
                Create Your Password
              </h2>
              <p className="text-xs text-muted mb-4">
                This will be your company admin login password. Must be at least 8
                characters.
              </p>

              <div className="relative">
                <Input
                  label="Password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-8 text-muted hover:text-near-black transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>

              <div className="relative">
                <Input
                  label="Confirm Password"
                  type={showConfirm ? "text" : "password"}
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-8 text-muted hover:text-near-black transition-colors"
                  aria-label={showConfirm ? "Hide password" : "Show password"}
                >
                  {showConfirm ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>

              {/* Password strength hints */}
              <div className="text-xs text-muted space-y-1 pl-1">
                <p className={password.length >= 8 ? "text-green-600" : ""}>
                  {password.length >= 8 ? "✓" : "○"} At least 8 characters
                </p>
                <p className={password && password === confirmPassword ? "text-green-600" : ""}>
                  {password && password === confirmPassword ? "✓" : "○"} Passwords match
                </p>
              </div>

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => navigate("/login")}
                  className="text-xs text-muted hover:text-near-black transition-colors inline-flex items-center gap-1"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back to Sign In
                </button>
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  isLoading={isLoading}
                  rightIcon={<Check className="w-4 h-4" />}
                  disabled={password.length < 8 || password !== confirmPassword}
                >
                  Create Account
                </Button>
              </div>
            </form>
          )}

          {/* ---- STEP 4 — SUCCESS ---- */}
          {step === 4 && (
            <div className="text-center py-4 space-y-5">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-green-50 border border-green-200 text-green-600">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <h2 className="text-lg font-bold text-near-black">
                Welcome to DailyBlog AI!
              </h2>
              <p className="text-sm text-muted max-w-sm mx-auto leading-relaxed">
                <span className="font-semibold text-near-black">{companyName}</span> has
                been registered successfully. You can now sign in with your company
                email and the password you just created.
              </p>
              <Button
                variant="primary"
                size="md"
                onClick={() => navigate("/login")}
                leftIcon={<Lock className="w-4 h-4" />}
              >
                Go to Sign In
              </Button>
            </div>
          )}
        </div>

        {/* Footer text */}
        <p className="text-center text-[11px] text-muted mt-4">
          Already have an account?{" "}
          <button
            type="button"
            onClick={() => navigate("/login")}
            className="text-primary hover:text-primary-dark font-medium transition-colors"
          >
            Sign In
          </button>
        </p>
      </div>
    </div>
  );
};
