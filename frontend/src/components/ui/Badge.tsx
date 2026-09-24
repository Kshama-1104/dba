import React from "react";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: "neutral" | "orange" | "dark" | "outline";
  size?: "sm" | "md";
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "neutral",
  size = "md",
  className = "",
}) => {
  const variantStyles = {
    neutral: "bg-gray-100 text-near-black border-border",
    orange: "bg-primary-light text-primary-dark border-primary-border",
    dark: "bg-black text-white border-black",
    outline: "bg-transparent text-muted border-border",
  };

  const sizeStyles = {
    sm: "text-[11px] px-1.5 py-0.5 leading-tight",
    md: "text-xs px-2.5 py-1 leading-normal",
  };

  return (
    <span
      className={`inline-flex items-center font-medium border rounded uppercase tracking-wider ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {children}
    </span>
  );
};
