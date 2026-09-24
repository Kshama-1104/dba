import React from "react";

export interface SelectOption {
  label: string;
  value: string | number;
}

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
  helperText?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    { label, options, error, helperText, className = "", id, required, ...props },
    ref
  ) => {
    const selectId =
      id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-xs font-semibold uppercase tracking-wider text-near-black mb-1.5"
          >
            {label}
            {required && <span className="text-primary ml-1">*</span>}
          </label>
        )}
        <select
          id={selectId}
          ref={ref}
          required={required}
          className={`w-full px-3 py-2 text-sm bg-surface border rounded text-near-black transition-colors duration-150 focus:border-primary focus:ring-1 focus:ring-primary ${
            error ? "border-primary-dark" : "border-border hover:border-gray-400"
          } ${className}`}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && <p className="text-xs text-primary-dark mt-1">{error}</p>}
        {!error && helperText && (
          <p className="text-xs text-muted mt-1">{helperText}</p>
        )}
      </div>
    );
  }
);

Select.displayName = "Select";
