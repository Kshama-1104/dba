import React from "react";
import { Menu, Building2, Shield } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";

export interface TopBarProps {
  onToggleSidebar: () => void;
  title?: string;
}

export const TopBar: React.FC<TopBarProps> = ({
  onToggleSidebar,
  title,
}) => {
  const { user, role, company } = useAuth();

  return (
    <header className="h-16 bg-surface border-b border-border px-4 lg:px-8 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-2 text-muted hover:text-near-black rounded lg:hidden transition-colors"
          aria-label="Toggle navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>
        {title && (
          <h1 className="text-base font-semibold text-near-black tracking-tight">
            {title}
          </h1>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Workspace context */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-background border border-border rounded text-xs">
          <Building2 className="w-3.5 h-3.5 text-muted" />
          <span className="font-medium text-near-black">
            {company?.name || `Tenant #${user?.company_id || "—"}`}
          </span>
        </div>

        {/* Role badge */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-primary-light border border-primary-border rounded text-xs text-primary-dark font-medium uppercase tracking-wider">
          <Shield className="w-3 h-3" />
          <span>{role ? role.replace("_", " ") : "Member"}</span>
        </div>
      </div>
    </header>
  );
};
