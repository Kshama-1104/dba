import React from "react";
import { BlogFormatDefinition } from "../../types";
import { Card, CardHeader, CardContent } from "../ui/Card";
import { Badge } from "../ui/Badge";
import { Check, ShieldCheck } from "lucide-react";

export interface FormatViewerProps {
  definition: BlogFormatDefinition;
  version: number;
  isActive: boolean;
  action?: React.ReactNode;
}

export const FormatViewer: React.FC<FormatViewerProps> = ({
  definition,
  version,
  isActive,
  action,
}) => {
  return (
    <Card className="h-full">
      <CardHeader
        title={
          <div className="flex items-center gap-2">
            <span>Global Blog Format Specification</span>
            <Badge variant={isActive ? "dark" : "outline"} size="sm">
              v{version} {isActive && "• ACTIVE"}
            </Badge>
          </div>
        }
        description="Company-wide baseline and custom formatting rules (Level 2)"
        action={action}
      />
      <CardContent className="space-y-6">
        {/* Core Sections Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-3 bg-background border border-border rounded">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
              Title Structure
            </p>
            <p className="text-xs text-near-black font-medium">
              {definition.title_structure || "Compelling, brand-aligned H1 headline"}
            </p>
          </div>

          <div className="p-3 bg-background border border-border rounded">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
              Introduction Structure
            </p>
            <p className="text-xs text-near-black font-medium">
              {definition.introduction_structure || "Hook, problem articulation, thesis statement"}
            </p>
          </div>

          <div className="p-3 bg-background border border-border rounded">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
              Heading Structure
            </p>
            <p className="text-xs text-near-black font-medium">
              {definition.heading_structure || "Hierarchical H2/H3 organizing core arguments"}
            </p>
          </div>

          <div className="p-3 bg-background border border-border rounded">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
              Main Content Structure
            </p>
            <p className="text-xs text-near-black font-medium">
              {definition.main_content_structure || "Educational body sections, data callouts"}
            </p>
          </div>

          <div className="p-3 bg-background border border-border rounded">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
              Conclusion Structure
            </p>
            <p className="text-xs text-near-black font-medium">
              {definition.conclusion_structure || "Summary synthesis, closing thoughts, brand CTA"}
            </p>
          </div>

          <div className="p-3 bg-background border border-border rounded">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1">
              Closing Call-to-Action Directive
            </p>
            <p className="text-xs text-near-black font-medium">
              {definition.call_to_action || "None specified"}
            </p>
          </div>
        </div>

        {/* Required & Optional Sections */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-border">
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <ShieldCheck className="w-3.5 h-3.5 text-primary" />
              <p className="text-xs font-semibold uppercase tracking-wider text-near-black">
                Mandatory Baseline Sections
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {definition.required_sections?.map((sec, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 px-2.5 py-1 bg-surface border border-border rounded text-xs text-near-black font-medium"
                >
                  <Check className="w-3 h-3 text-primary" />
                  {sec}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Optional / Conditional Sections
            </p>
            <div className="flex flex-wrap gap-1.5">
              {definition.optional_sections && definition.optional_sections.length > 0 ? (
                definition.optional_sections.map((sec, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center px-2.5 py-1 bg-background border border-border rounded text-xs text-muted"
                  >
                    {sec}
                  </span>
                ))
              ) : (
                <span className="text-xs text-muted italic">None defined</span>
              )}
            </div>
          </div>
        </div>

        {/* Custom Rules */}
        {definition.custom_rules && definition.custom_rules.length > 0 && (
          <div className="pt-4 border-t border-border">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Company-Specific Editorial Rules
            </p>
            <ul className="list-disc list-inside space-y-1 text-xs text-near-black">
              {definition.custom_rules.map((rule, idx) => (
                <li key={idx} className="leading-relaxed">
                  {rule}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
