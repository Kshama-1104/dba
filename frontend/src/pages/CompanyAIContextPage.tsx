import React, { useEffect, useState } from "react";
import { companyApi } from "../api/company";
import { CompanyAIProfile } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Textarea } from "../components/ui/Textarea";
import { Button } from "../components/ui/Button";
import { Save, Building2, Sparkles, Shield, AlertCircle } from "lucide-react";

export const CompanyAIContextPage: React.FC = () => {
  const { role } = useAuth();
  const { success, error: toastError } = useToast();

  const [profile, setProfile] = useState<CompanyAIProfile | null>(null);
  const [formData, setFormData] = useState({
    products_services: "",
    target_audience: "",
    preferred_writing_style: "",
    brand_voice: "",
    marketing_goals: "",
    company_guidelines: "",
    upcoming_projects: "",
    partner_companies: "",
    achievements: "",
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isAdmin = role === "company_admin";

  useEffect(() => {
    async function fetchProfile() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const data = await companyApi.getAIProfile();
        setProfile(data);
        setFormData({
          products_services: data.products_services || "",
          target_audience: data.target_audience || "",
          preferred_writing_style: data.preferred_writing_style || "",
          brand_voice: data.brand_voice || "",
          marketing_goals: data.marketing_goals || "",
          company_guidelines: data.company_guidelines || "",
          upcoming_projects: data.upcoming_projects || "",
          partner_companies: data.partner_companies || "",
          achievements: data.achievements || "",
        });
        setIsDirty(false);
      } catch (err: unknown) {
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Failed to load Company AI profile."
        );
      } finally {
        setIsLoading(false);
      }
    }

    fetchProfile();
  }, []);

  const handleChange = (field: keyof typeof formData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setIsDirty(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;

    setIsSaving(true);
    setErrorMessage(null);

    try {
      const updated = await companyApi.updateAIProfile(formData);
      setProfile(updated);
      setIsDirty(false);
      success("Profile Updated", "Company AI profile guidelines saved successfully.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update profile.";
      setErrorMessage(msg);
      toastError("Save Failed", msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-surface p-6 border border-border rounded-lg shadow-subtle">
        <div>
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-bold text-near-black tracking-tight">
              Company AI Context &amp; Brand Guidelines
            </h1>
          </div>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Phase 1 authoritative knowledge and brand profile. Enforced across topic generation, synthesis, and memory precedence.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {!isAdmin && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-background border border-border rounded text-xs text-muted">
              <Shield className="w-3.5 h-3.5" />
              <span>Read-only (Admin authorization required to edit)</span>
            </div>
          )}

          {isAdmin && (
            <Button
              size="sm"
              variant="primary"
              onClick={handleSave}
              disabled={!isDirty || isSaving}
              isLoading={isSaving}
              leftIcon={<Save className="w-3.5 h-3.5" />}
            >
              {isDirty ? "Save Changes" : "Saved"}
            </Button>
          )}
        </div>
      </div>

      {errorMessage && (
        <div className="p-4 bg-primary-light border border-primary-border rounded-lg text-xs text-primary-dark flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {isLoading ? (
        <Card>
          <CardContent className="p-8 space-y-4">
            <div className="h-5 bg-gray-200 animate-pulse rounded w-1/3" />
            <div className="h-24 bg-gray-200 animate-pulse rounded w-full" />
            <div className="h-5 bg-gray-200 animate-pulse rounded w-1/4" />
            <div className="h-24 bg-gray-200 animate-pulse rounded w-full" />
          </CardContent>
        </Card>
      ) : (
        <form onSubmit={handleSave} className="space-y-6">
          {/* Brand Voice & Tone */}
          <Card>
            <CardHeader
              title="Brand Voice & Editorial Style"
              description="Defines the tone, voice, and stylistic preferences for all generated content"
            />
            <CardContent className="space-y-4">
              <Textarea
                label="Brand Voice"
                helperText="E.g., Authoritative, visionary, technically precise, empathetic B2B SaaS tone."
                value={formData.brand_voice}
                onChange={(e) => handleChange("brand_voice", e.target.value)}
                disabled={!isAdmin}
                rows={3}
              />

              <Textarea
                label="Preferred Writing Style"
                helperText="E.g., Clear active voice, short paragraphs, metric-backed arguments, no hyperbole."
                value={formData.preferred_writing_style}
                onChange={(e) =>
                  handleChange("preferred_writing_style", e.target.value)
                }
                disabled={!isAdmin}
                rows={3}
              />
            </CardContent>
          </Card>

          {/* Positioning & Audience */}
          <Card>
            <CardHeader
              title="Products, Positioning & Audience"
              description="Context used by the AI to address reader pain points and articulate solutions"
            />
            <CardContent className="space-y-4">
              <Textarea
                label="Products & Services"
                helperText="Detailed overview of company offerings, platform modules, and core value proposition."
                value={formData.products_services}
                onChange={(e) =>
                  handleChange("products_services", e.target.value)
                }
                disabled={!isAdmin}
                rows={3}
              />

              <Textarea
                label="Target Audience"
                helperText="Key personas: VP of Engineering, Chief Information Security Officer, Head of Growth, etc."
                value={formData.target_audience}
                onChange={(e) => handleChange("target_audience", e.target.value)}
                disabled={!isAdmin}
                rows={3}
              />

              <Textarea
                label="Marketing Goals"
                helperText="Key business objectives: brand authority, organic inbound leads, enterprise trust."
                value={formData.marketing_goals}
                onChange={(e) =>
                  handleChange("marketing_goals", e.target.value)
                }
                disabled={!isAdmin}
                rows={3}
              />
            </CardContent>
          </Card>

          {/* Rules & Corporate Knowledge */}
          <Card>
            <CardHeader
              title="Corporate Guidelines & Milestones"
              description="Negative constraints, partner entities, and company proof points"
            />
            <CardContent className="space-y-4">
              <Textarea
                label="Company Guidelines / Constraints"
                helperText="Rules the AI must adhere to: never mention competitor X, do not make unsubstantiated financial claims."
                value={formData.company_guidelines}
                onChange={(e) =>
                  handleChange("company_guidelines", e.target.value)
                }
                disabled={!isAdmin}
                rows={3}
              />

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Textarea
                  label="Upcoming Projects"
                  value={formData.upcoming_projects}
                  onChange={(e) =>
                    handleChange("upcoming_projects", e.target.value)
                  }
                  disabled={!isAdmin}
                  rows={2}
                />
                <Textarea
                  label="Partner Companies"
                  value={formData.partner_companies}
                  onChange={(e) =>
                    handleChange("partner_companies", e.target.value)
                  }
                  disabled={!isAdmin}
                  rows={2}
                />
                <Textarea
                  label="Achievements & Awards"
                  value={formData.achievements}
                  onChange={(e) => handleChange("achievements", e.target.value)}
                  disabled={!isAdmin}
                  rows={2}
                />
              </div>
            </CardContent>
          </Card>
        </form>
      )}
    </div>
  );
};
