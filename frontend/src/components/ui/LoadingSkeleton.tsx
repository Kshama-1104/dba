import React from "react";

export const LoadingSkeleton: React.FC<{
  className?: string;
  lines?: number;
}> = ({ className = "h-4 w-full", lines = 1 }) => {
  if (lines > 1) {
    return (
      <div className="space-y-2 w-full">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={`bg-gray-200 animate-pulse rounded ${className} ${
              i === lines - 1 ? "w-3/4" : "w-full"
            }`}
          />
        ))}
      </div>
    );
  }

  return (
    <div className={`bg-gray-200 animate-pulse rounded ${className}`} />
  );
};
