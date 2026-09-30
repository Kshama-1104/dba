import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { BrowserRouter } from "react-router-dom";
import { LoginPage } from "../pages/LoginPage";
import { AuthProvider } from "../contexts/AuthContext";
import { authApi } from "../api/auth";

vi.mock("../api/auth", () => ({
  authApi: {
    login: vi.fn(),
    getMe: vi.fn(),
  },
}));

describe("LoginPage & Authentication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders login form with email and password inputs", () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByPlaceholderText("name@company.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("••••••••")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  it("toggles password visibility when eye button is clicked", () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </BrowserRouter>
    );

    const passwordInput = screen.getByPlaceholderText("••••••••");
    expect(passwordInput).toHaveAttribute("type", "password");

    const toggleBtn = screen.getByRole("button", { name: /show password/i });
    fireEvent.click(toggleBtn);

    expect(passwordInput).toHaveAttribute("type", "text");
  });

  it("handles successful login and token storage", async () => {
    vi.mocked(authApi.login).mockResolvedValueOnce({
      access_token: "mock-jwt-token",
      user_id: 1,
      role: "company_admin",
      company_id: 10,
      requires_password_setup: false,
    });

    vi.mocked(authApi.getMe).mockResolvedValueOnce({
      user_id: 1,
      name: "Alice Admin",
      email: "alice@company.com",
      role: "company_admin",
      company_id: 10,
    });

    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </BrowserRouter>
    );

    fireEvent.change(screen.getByPlaceholderText("name@company.com"), {
      target: { value: "alice@company.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), {
      target: { value: "SecurePass123!" },
    });

    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith({
        email: "alice@company.com",
        password: "SecurePass123!",
      });
      expect(localStorage.getItem("dailyblog_token")).toBe("mock-jwt-token");
    });
  });

  it("displays error message when login fails with 401", async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce(
      new Error("Invalid email or password")
    );

    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </BrowserRouter>
    );

    fireEvent.change(screen.getByPlaceholderText("name@company.com"), {
      target: { value: "wrong@company.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), {
      target: { value: "BadPass" },
    });

    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/invalid email or password/i)
      ).toBeInTheDocument();
    });
  });
});
