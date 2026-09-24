import React from "react";
import { Badge } from "./Badge";

export interface StatusBadgeProps {
  status: string;
  className?: string;
  size?: "sm" | "md";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  className = "",
  size = "md",
}) => {
  const normalized = (status || "").toLowerCase().replace(/\s+/g, "_");

  switch (normalized) {
    case "draft":
    case "suggested":
    case "candidate":
      return (
        <Badge variant="neutral" size={size} className={className}>
          {status.replace(/_/g, " ")}
        </Badge>
      );

    case "pending_review":
    case "pending":
    case "selected":
      return (
        <Badge variant="orange" size={size} className={className}>
          {status.replace(/_/g, " ")}
        </Badge>
      );

    case "changes_requested":
      return (
        <Badge variant="orange" size={size} className={className}>
          Changes Requested
        </Badge>
      );

    case "approved":
    case "active":
    case "ready":
      return (
        <Badge variant="dark" size={size} className={className}>
          {status.replace(/_/g, " ")}
        </Badge>
      );

    case "scheduled":
    case "queued":
      return (
        <Badge variant="orange" size={size} className={className}>
          {status.replace(/_/g, " ")}
        </Badge>
      );

    case "publishing":
    case "running":
    case "processing":
      return (
        <Badge variant="orange" size={size} className={`animate-pulse ${className}`}>
          {status.replace(/_/g, " ")}...
        </Badge>
      );

    case "published":
    case "succeeded":
      return (
        <Badge variant="dark" size={size} className={className}>
          Published
        </Badge>
      );

    case "rejected":
    case "failed":
    case "cancelled":
    case "superseded":
    case "archived":
      return (
        <Badge variant="outline" size={size} className={className}>
          {status.replace(/_/g, " ")}
        </Badge>
      );

    default:
      return (
        <Badge variant="neutral" size={size} className={className}>
          {status.replace(/_/g, " ")}
        </Badge>
      );
  }
};
