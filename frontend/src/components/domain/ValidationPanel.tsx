import React from "react";
import { BlogValidationResponse } from "../../types";
import { Check, AlertTriangle, XCircle } from "lucide-react";
import { Card, CardHeader, CardContent } from "../ui/Card";

export interface ValidationPanelProps {
  validation: BlogValidationResponse | null;
  isLoading?: boolean;
}

export const ValidationPanel: React.FC<ValidationPanelProps> = ({
  validation,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <Card>
        <CardHeader title="SEO & Format Validation" description="Analyzing article quality against company rules..." />
        <CardContent>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 animate-pulse rounded w-3/4" />
            <div className="h-4 bg-gray-200 animate-pulse rounded w-1/2" />
            <div className="h-4 bg-gray-200 animate-pulse rounded w-5/6" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!validation) {
    return (
      <Card>
        <CardHeader
          title="SEO & Format Validation"
          description="Validation has not been executed yet. Run validation to inspect adherence to Phase 7 criteria."
        />
      </Card>
    );
  }

  const { passed, errors, warnings, recommendations, seo_report, format_report } =
    validation;

  const seoItems = [
    {
      label: "SEO Title Length",
      passed: seo_report.seo_title_valid,
      detail: `${seo_report.seo_title_length} characters`,
    },
    {
      label: "Meta Description Length",
      passed: seo_report.meta_description_valid,
      detail: `${seo_report.meta_description_length} characters`,
    },
    {
      label: "Keyword in Title",
      passed: seo_report.keyword_in_seo_title,
      detail: seo_report.primary_keyword || "None",
    },
    {
      label: "Keyword in Introduction",
      passed: seo_report.keyword_in_introduction,
      detail: seo_report.primary_keyword || "None",
    },
    {
      label: "Keyword in H2 Headings",
      passed: seo_report.keyword_in_h2,
      detail: seo_report.primary_keyword || "None",
    },
    {
      label: "Slug Validity",
      passed: seo_report.slug_valid,
      detail: seo_report.slug_issues.length
        ? seo_report.slug_issues.join(", ")
        : "Valid",
    },
  ];

  const formatItems = [
    {
      label: "Baseline Sections",
      passed: format_report.baseline_sections_valid,
      detail: "H1, Intro, Headings, Main, Conclusion",
    },
    {
      label: "H1 Title Valid",
      passed: format_report.h1_title_valid,
      detail: "Single H1 structure",
    },
    {
      label: "Introduction Section",
      passed: format_report.introduction_valid,
      detail: "Hook, problem, thesis",
    },
    {
      label: "Conclusion Section",
      passed: format_report.conclusion_valid,
      detail: "Summary & CTA",
    },
    {
      label: "Heading Hierarchy",
      passed: format_report.heading_hierarchy_valid,
      detail: "Sequential H2 / H3 levels",
    },
    {
      label: "Company Format Rules",
      passed: format_report.company_sections_valid,
      detail: format_report.company_format_checked
        ? `v${format_report.company_format_version}`
        : "Default Baseline",
    },
  ];

  return (
    <Card>
      <CardHeader
        title="SEO & Format Validation"
        description={`Validated at ${new Date(
          validation.validated_at
        ).toLocaleTimeString()}`}
        action={
          <div
            className={`px-3 py-1 rounded text-xs font-semibold tracking-wider uppercase border ${
              passed
                ? "bg-black text-white border-black"
                : errors.length > 0
                ? "bg-primary-light text-primary-dark border-primary-border"
                : "bg-gray-100 text-near-black border-border"
            }`}
          >
            {passed ? "PASS" : errors.length > 0 ? "FAIL" : "WARNING"}
          </div>
        }
      />
      <CardContent className="space-y-6">
        {/* SEO Grid */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">
            SEO Criteria
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {seoItems.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2.5 bg-background border border-border rounded text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {item.passed ? (
                    <Check className="w-4 h-4 text-primary flex-shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-primary-dark flex-shrink-0" />
                  )}
                  <span className="font-medium text-near-black truncate">
                    {item.label}
                  </span>
                </div>
                <span className="text-[11px] text-muted flex-shrink-0 ml-2">
                  {item.detail}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Format Grid */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">
            Format & Structure Criteria
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {formatItems.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2.5 bg-background border border-border rounded text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {item.passed ? (
                    <Check className="w-4 h-4 text-primary flex-shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-primary-dark flex-shrink-0" />
                  )}
                  <span className="font-medium text-near-black truncate">
                    {item.label}
                  </span>
                </div>
                <span className="text-[11px] text-muted flex-shrink-0 ml-2">
                  {item.detail}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Findings: Errors & Warnings */}
        {(errors.length > 0 || warnings.length > 0) && (
          <div className="pt-4 border-t border-border space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-near-black">
              Detailed Findings ({errors.length + warnings.length})
            </h4>
            <div className="space-y-2">
              {errors.map((err, idx) => (
                <div
                  key={`err-${idx}`}
                  className="p-3 bg-primary-light border border-primary-border rounded text-xs text-primary-dark flex items-start gap-2.5"
                >
                  <XCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold uppercase tracking-wider text-[10px] mr-1.5">
                      Error [{err.rule}]:
                    </span>
                    <span>{err.message}</span>
                  </div>
                </div>
              ))}
              {warnings.map((warn, idx) => (
                <div
                  key={`warn-${idx}`}
                  className="p-3 bg-background border border-border rounded text-xs text-near-black flex items-start gap-2.5"
                >
                  <AlertTriangle className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold uppercase tracking-wider text-[10px] text-muted mr-1.5">
                      Warning [{warn.rule}]:
                    </span>
                    <span>{warn.message}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div className="pt-4 border-t border-border">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Optimization Recommendations
            </h4>
            <ul className="list-disc list-inside space-y-1 text-xs text-muted">
              {recommendations.map((rec, idx) => (
                <li key={idx} className="leading-relaxed">
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
