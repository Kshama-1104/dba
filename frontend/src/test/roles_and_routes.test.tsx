import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import { ProtectedRoute } from "../routes/ProtectedRoute";
import { Sidebar } from "../components/layout/Sidebar";
import * as AuthContextModule from "../contexts/AuthContext";
import { UserRole } from "../types";

describe("Role-Aware UI & Protected Routes", () => {
  const mockAuth = (role: UserRole | null, isAuthenticated = true) => {
    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: role
        ? {
            user_id: 1,
            name: "Test User",
            email: "test@example.com",
            role,
            company_id: 10,
          }
        : null,
      company: {
        id: 10,
        name: "Acme Corp",
        description: null,
        logo_url: null,
        company_type: null,
        industry: null,
        country_region: null,
        company_email: null,
        notification_email: null,
      },
      role,
      token: isAuthenticated ? "mock-token" : null,
      isAuthenticated,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
  };

  it("shows Access Denied when role is unauthorized for protected route", () => {
    mockAuth("reviewer", true);

    render(
      <MemoryRouter>
        <ProtectedRoute allowedRoles={["company_admin"]}>
          <div>Admin Only Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText(/access denied/i)).toBeInTheDocument();
    expect(screen.queryByText(/admin only content/i)).not.toBeInTheDocument();
  });

  it("renders protected content when user has authorized role", () => {
    mockAuth("company_admin", true);

    render(
      <MemoryRouter>
        <ProtectedRoute allowedRoles={["company_admin"]}>
          <div>Admin Only Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText(/admin only content/i)).toBeInTheDocument();
    expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
  });

  it("renders role-appropriate navigation items in Sidebar for Editor", () => {
    mockAuth("editor", true);

    render(
      <BrowserRouter>
        <Sidebar isOpen={true} onClose={vi.fn()} />
      </BrowserRouter>
    );

    expect(screen.getByText(/topic intelligence/i)).toBeInTheDocument();
    expect(screen.getByText(/blogs/i)).toBeInTheDocument();
    expect(screen.queryByText(/settings/i)).not.toBeInTheDocument(); // Settings is admin only
  });

  it("renders Settings item in Sidebar for Company Admin", () => {
    mockAuth("company_admin", true);

    render(
      <BrowserRouter>
        <Sidebar isOpen={true} onClose={vi.fn()} />
      </BrowserRouter>
    );

    expect(screen.getByText(/settings/i)).toBeInTheDocument();
  });
});
