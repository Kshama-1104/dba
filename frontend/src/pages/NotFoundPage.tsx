import React from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { ArrowLeft, FileQuestion } from "lucide-react";

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6">
      <div className="w-14 h-14 rounded-full bg-background border border-border flex items-center justify-center text-muted mb-4">
        <FileQuestion className="w-7 h-7" />
      </div>
      <h1 className="text-2xl font-bold text-near-black tracking-tight">
        404 — Page Not Found
      </h1>
      <p className="text-xs text-muted max-w-sm mt-1 mb-6 leading-relaxed">
        The requested URL path does not exist in DailyBlog AI or you do not have permission to view it.
      </p>
      <Link to="/dashboard">
        <Button
          size="sm"
          variant="primary"
          leftIcon={<ArrowLeft className="w-4 h-4" />}
        >
          Return to Dashboard
        </Button>
      </Link>
    </div>
  );
};
