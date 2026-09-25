import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { reviewerRegistrationApi } from "../api/reviewer_registration";

export const ReviewerRegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [otp, setOtp] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await reviewerRegistrationApi.start({ name, company_email: email });
      setToken((res as any).registration_token);
      setStep(2);
      await reviewerRegistrationApi.sendOtp((res as any).registration_token);
      await reviewerRegistrationApi.generateCaptcha((res as any).registration_token);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to start registration");
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await reviewerRegistrationApi.verifyOtp(token, otp);
      await reviewerRegistrationApi.verifyCaptcha(token, captcha);
      setStep(3);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to verify OTP/CAPTCHA");
    }
  };

  const handleComplete = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await reviewerRegistrationApi.complete({
        registration_token: token,
        password,
        confirm_password: confirmPassword,
      });
      navigate("/login?message=Registration successful, waiting for admin approval");
    } catch (err: any) {
      setError(err.message || "Failed to complete registration");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="max-w-md w-full bg-surface p-8 rounded-xl shadow-subtle border border-border">
        <h1 className="text-2xl font-bold mb-6 text-near-black">Reviewer Registration</h1>
        
        {error && <div className="mb-4 text-red-500 text-sm">{error}</div>}

        {step === 1 && (
          <form onSubmit={handleStart} className="space-y-4">
            <Input label="Full Name" value={name} onChange={(e) => setName(e.target.value)} required />
            <Input label="Company Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Button type="submit" className="w-full">Next</Button>
          </form>
        )}

        {step === 2 && (
          <form onSubmit={handleVerify} className="space-y-4">
            <Input label="OTP" value={otp} onChange={(e) => setOtp(e.target.value)} required />
            <Input label="CAPTCHA" value={captcha} onChange={(e) => setCaptcha(e.target.value)} required />
            <Button type="submit" className="w-full">Verify</Button>
          </form>
        )}

        {step === 3 && (
          <form onSubmit={handleComplete} className="space-y-4">
            <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <Input label="Confirm Password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
            <Button type="submit" className="w-full">Complete Request</Button>
          </form>
        )}
        
        <div className="mt-4 text-center text-sm">
          <Link to="/login" className="text-primary hover:underline">Back to Login</Link>
        </div>
      </div>
    </div>
  );
};
