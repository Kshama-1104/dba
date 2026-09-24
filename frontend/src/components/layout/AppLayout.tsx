import React, { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export const AppLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const getPageTitle = (path: string): string => {
    if (path.startsWith("/dashboard")) return "Dashboard";
    if (path.startsWith("/company/ai-context")) return "Company AI Context";
    if (path.startsWith("/company/blog-format")) return "Company Global Blog Format";
    if (path.startsWith("/knowledge")) return "Knowledge Base & RAG";
    if (path.startsWith("/memory")) return "Company Long-Term Memory";
    if (path.startsWith("/topics")) return "Topic Intelligence";
    if (path.includes("/editor")) return "Blog Editor & AI Co-Author";
    if (path.includes("/revisions")) return "Revision History & Snapshot Audit";
    if (path.startsWith("/blogs/")) return "Blog Overview";
    if (path.startsWith("/blogs")) return "Blog Management";
    if (path.startsWith("/reviews")) return "Editorial Review Queue";
    if (path.startsWith("/schedule")) return "Publication Schedule & Calendar";
    if (path.startsWith("/wordpress")) return "WordPress Publishing Integration";
    if (path.startsWith("/settings")) return "Company Settings & Team";
    return "DailyBlog AI";
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="lg:pl-64 flex flex-col flex-1">
        <TopBar
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title={getPageTitle(location.pathname)}
        />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
