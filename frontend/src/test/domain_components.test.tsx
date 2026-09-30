import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TopicCard } from "../components/domain/TopicCard";
import { ValidationPanel } from "../components/domain/ValidationPanel";
import { ReviewDecisionModal } from "../components/domain/ReviewDecisionModal";
import { ScheduleModal } from "../components/domain/ScheduleModal";
import * as AuthContextModule from "../contexts/AuthContext";
import { BlogValidationResponse, TopicCandidate } from "../types";

describe("Domain Components & Core Workflows", () => {
  const mockEditorAuth = () => {
    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: {
        user_id: 2,
        name: "Ed Editor",
        email: "ed@example.com",
        role: "editor",
        company_id: 10,
      },
      company: null,
      role: "editor",
      token: "mock-token",
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
  };

  it("renders TopicCard and handles Select and Reject actions", () => {
    mockEditorAuth();
    const onSelect = vi.fn();
    const onReject = vi.fn();

    const mockTopic: TopicCandidate = {
      id: 42,
      company_id: 10,
      title: "Fintech Compliance Playbook",
      angle: "Zero-trust model audit",
      rationale: "Addresses risk officer anxiety",
      primary_keyword: "fintech compliance",
      relevance_score: 0.95,
      freshness_score: 0.88,
      final_score: 0.91,
      status: "suggested",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(
      <TopicCard
        topic={mockTopic}
        onSelect={onSelect}
        onReject={onReject}
      />
    );

    expect(screen.getByText("Fintech Compliance Playbook")).toBeInTheDocument();
    expect(screen.getByText("fintech compliance")).toBeInTheDocument();

    const selectBtn = screen.getByRole("button", { name: /select/i });
    fireEvent.click(selectBtn);
    expect(onSelect).toHaveBeenCalledWith(42);

    const rejectBtn = screen.getByRole("button", { name: /reject/i });
    fireEvent.click(rejectBtn);
    expect(onReject).toHaveBeenCalledWith(42);
  });

  it("renders ValidationPanel with correct PASS/FAIL indicators and rule findings", () => {
    const mockValidation: BlogValidationResponse = {
      blog_id: 101,
      company_id: 10,
      passed: false,
      errors: [
        {
          rule: "SEO_TITLE_LENGTH",
          message: "Title exceeds 60 characters limit.",
          severity: "error",
        },
      ],
      warnings: [],
      recommendations: ["Incorporate primary keyword into first H2 section."],
      seo_report: {
        seo_title_valid: false,
        seo_title_length: 72,
        meta_description_valid: true,
        meta_description_length: 150,
        primary_keyword: "cloud migration",
        keyword_in_seo_title: true,
        keyword_in_introduction: true,
        keyword_in_h2: false,
        slug_valid: true,
        slug_issues: [],
        keyword_stuffing_warning: false,
        keyword_density: 0.02,
        findings: [],
      },
      format_report: {
        baseline_sections_valid: true,
        h1_title_valid: true,
        introduction_valid: true,
        conclusion_valid: true,
        sections_valid: true,
        heading_hierarchy_valid: true,
        duplicate_headings: [],
        company_format_checked: true,
        company_format_version: 1,
        company_sections_valid: true,
        missing_company_sections: [],
        findings: [],
      },
      validated_at: new Date().toISOString(),
    };

    render(<ValidationPanel validation={mockValidation} />);

    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(screen.getByText(/Title exceeds 60 characters limit/i)).toBeInTheDocument();
    expect(screen.getByText(/Incorporate primary keyword into first H2 section/i)).toBeInTheDocument();
  });

  it("enforces mandatory feedback on Request Changes in ReviewDecisionModal", async () => {
    const onSubmit = vi.fn();

    render(
      <ReviewDecisionModal
        isOpen={true}
        onClose={vi.fn()}
        blogTitle="Enterprise AI Architecture"
        revisionNumber={2}
        onSubmit={onSubmit}
      />
    );

    // Select "Request Changes"
    const reqChangesBtn = screen.getByText(/request changes/i);
    fireEvent.click(reqChangesBtn);

    // Try submitting without feedback
    const submitBtn = screen.getByRole("button", { name: /submit decision/i });
    fireEvent.click(submitBtn);

    expect(
      screen.getByText(/editorial feedback is mandatory when requesting changes/i)
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    // Now fill in feedback
    const feedbackInput = screen.getByLabelText(/revision feedback \(mandatory\)/i);
    fireEvent.change(feedbackInput, {
      target: { value: "Please tighten section 2 and add metrics." },
    });

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        decision: "request_changes",
        feedback: "Please tighten section 2 and add metrics.",
        reviewer_comment: undefined,
      });
    });
  });

  it("submits wall-clock scheduled time and timezone in ScheduleModal", async () => {
    const onSubmit = vi.fn();

    render(
      <ScheduleModal
        isOpen={true}
        onClose={vi.fn()}
        blogId={55}
        blogTitle="Scaling SaaS Content"
        targetRevisionId={3}
        onSubmit={onSubmit}
      />
    );

    expect(screen.getByText(/snapshot #3/i)).toBeInTheDocument();

    const confirmBtn = screen.getByRole("button", { name: /confirm schedule/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
      const callArg = onSubmit.mock.calls[0][0];
      expect(callArg.timezone).toBe("UTC");
      expect(callArg.target_revision_id).toBe(3);
    });
  });
});
