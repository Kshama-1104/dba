import React from "react";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className = "", id, required, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-1.5"
          >
            {label}
            {required && <span className="text-primary ml-1">*</span>}
          </label>
        )}
        <input
          id={inputId}
          ref={ref}
          required={required}
          className={`w-full px-3 py-2 text-sm bg-surface border rounded text-near-black placeholder:text-muted/60 transition-colors duration-150 focus:border-primary focus:ring-1 focus:ring-primary ${
            error ? "border-primary-dark" : "border-border hover:border-gray-400"
          } ${className}`}
          {...props}
        />
        {error && <p className="text-xs text-primary-dark mt-1">{error}</p>}
        {!error && helperText && (
          <p className="text-xs text-muted mt-1">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
