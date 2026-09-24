import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <div
      className={`bg-surface border border-border rounded-lg shadow-subtle ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<{
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}> = ({ title, description, action, className = "" }) => {
  return (
    <div
      className={`p-5 border-b border-border flex items-start justify-between gap-4 ${className}`}
    >
      <div>
        <h2 className="text-base font-semibold text-near-black tracking-tight">
          {title}
        </h2>
        {description && (
          <p className="text-xs text-muted mt-1 leading-relaxed">{description}</p>
        )}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
};

export const CardContent: React.FC<{
  children: React.ReactNode;
  className?: string;
}> = ({ children, className = "" }) => {
  return <div className={`p-5 ${className}`}>{children}</div>;
};

export const CardFooter: React.FC<{
  children: React.ReactNode;
  className?: string;
}> = ({ children, className = "" }) => {
  return (
    <div
      className={`p-4 bg-background border-t border-border rounded-b-lg flex items-center justify-between ${className}`}
    >
      {children}
    </div>
  );
};
