import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Building2,
  FileCode2,
  BookOpen,
  Brain,
  Sparkles,
  FileText,
  CheckSquare,
  Calendar,
  Globe,
  Settings,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";

export const Sidebar: React.FC<{ isOpen: boolean; onClose: () => void }> = ({
  isOpen,
  onClose,
}) => {
  const { user, role, company, logout } = useAuth();

  const navItems = [
    {
      to: "/dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
      roles: ["company_admin", "editor", "reviewer"],
    },
    {
      to: "/company/ai-context",
      label: "Company AI Context",
      icon: Building2,
      roles: ["company_admin"],
    },
    {
      to: "/company/blog-format",
      label: "Blog Format",
      icon: FileCode2,
      roles: ["company_admin", "editor"],
    },
    {
      to: "/knowledge",
      label: "Knowledge (RAG)",
      icon: BookOpen,
      roles: ["company_admin", "editor"],
    },
    {
      to: "/memory",
      label: "Memory",
      icon: Brain,
      roles: ["company_admin", "editor"],
    },
    {
      to: "/topics",
      label: "Topic Intelligence",
      icon: Sparkles,
      roles: ["company_admin", "editor"],
    },
    {
      to: "/blogs",
      label: "Blogs",
      icon: FileText,
      roles: ["company_admin", "editor", "reviewer"],
    },
    {
      to: "/reviews",
      label: "Reviews",
      icon: CheckSquare,
      roles: ["company_admin", "reviewer", "editor"],
    },
    {
      to: "/schedule",
      label: "Schedule",
      icon: Calendar,
      roles: ["company_admin", "editor", "reviewer"],
    },
    {
      to: "/wordpress",
      label: "WordPress",
      icon: Globe,
      roles: ["company_admin"],
    },
    {
      to: "/settings",
      label: "Settings",
      icon: Settings,
      roles: ["company_admin"],
    },
  ];

  const filteredNavItems = navItems.filter(
    (item) => !role || item.roles.includes(role)
  );

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 w-64 bg-near-black text-white flex flex-col transition-transform duration-200 lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand header */}
        <div className="h-16 px-6 border-b border-border-dark flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-primary flex items-center justify-center font-bold text-white tracking-wider text-sm">
              DB
            </div>
            <div>
              <span className="font-bold text-sm tracking-tight text-white block">
                DailyBlog <span className="text-primary">AI</span>
              </span>
              <span className="text-[10px] text-muted-dark block -mt-0.5 uppercase tracking-wider">
                Enterprise Content
              </span>
            </div>
          </div>
        </div>

        {/* Workspace context banner */}
        <div className="px-6 py-3 border-b border-border-dark bg-black/40">
          <p className="text-[11px] uppercase tracking-wider text-muted-dark font-medium">
            Company Context
          </p>
          <p className="text-xs font-semibold text-white truncate mt-0.5">
            {company?.name || `Company #${user?.company_id || "—"}`}
          </p>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {filteredNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded text-xs font-medium transition-colors duration-150 ${
                    isActive
                      ? "bg-surface-dark text-white border-l-2 border-primary pl-2.5"
                      : "text-muted-dark hover:text-white hover:bg-surface-dark/60"
                  }`
                }
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* User profile footer */}
        <div className="p-4 border-t border-border-dark bg-surface-dark">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-full bg-border-dark flex items-center justify-center text-muted-dark flex-shrink-0">
                <UserIcon className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-white truncate">
                  {user?.name || user?.email || "User"}
                </p>
                <p className="text-[10px] uppercase font-mono text-primary truncate">
                  {role ? role.replace("_", " ") : "guest"}
                </p>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="p-1.5 text-muted-dark hover:text-white hover:bg-black rounded transition-colors"
              aria-label="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};
