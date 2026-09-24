import React from "react";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, helperText, className = "", id, required, rows = 4, ...props }, ref) => {
    const textareaId =
      id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={textareaId}
            className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-1.5"
          >
            {label}
            {required && <span className="text-primary ml-1">*</span>}
          </label>
        )}
        <textarea
          id={textareaId}
          ref={ref}
          rows={rows}
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

Textarea.displayName = "Textarea";
