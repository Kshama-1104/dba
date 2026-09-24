import React from "react";
import { Button } from "./Button";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  actionIcon?: React.ReactNode;
  actionDisabled?: boolean;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  actionIcon,
  actionDisabled = false,
}) => {
  return (
    <div className="bg-surface border border-dashed border-border rounded-lg p-10 text-center flex flex-col items-center justify-center my-4">
      {icon && (
        <div className="w-12 h-12 rounded-full bg-background border border-border flex items-center justify-center text-muted mb-4">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-near-black">{title}</h3>
      <p className="text-xs text-muted max-w-sm mt-1 mb-5 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button
          size="sm"
          variant="primary"
          onClick={onAction}
          leftIcon={actionIcon}
          disabled={actionDisabled}
        >
          {actionLabel}
        </Button>
      )}
    </div>
  );
};
