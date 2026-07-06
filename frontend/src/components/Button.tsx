import { type ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'danger';

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-white font-semibold hover:bg-primary/90 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/25 active:translate-y-0',
  secondary: 'border border-border-subtle text-text-secondary font-medium hover:bg-surface-muted',
  danger: 'bg-error text-white font-semibold hover:bg-error/90',
};

/** Standard pill action button. Native button props (onClick, disabled, title, type) pass through. */
export function Button({
  variant = 'primary',
  className = '',
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

type Tone = 'neutral' | 'primary' | 'error' | 'success' | 'warning';

const TONES: Record<Tone, string> = {
  neutral: 'text-text-secondary hover:bg-surface-muted',
  primary: 'text-text-secondary hover:text-primary hover:bg-primary/10',
  error:   'text-text-secondary hover:text-error hover:bg-error/10',
  success: 'text-success hover:bg-success/10',
  warning: 'text-warning hover:bg-warning/10',
};

/**
 * Square icon-only button (rounded-lg). `tone` sets the hover color, `size` the box
 * in px (28 = table actions, 32 = modal close). Extra modifiers (borders, opacity)
 * go through `className`.
 */
export function IconButton({
  tone = 'neutral',
  size = 28,
  className = '',
  children,
  style,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: Tone; size?: number }) {
  return (
    <button
      {...props}
      style={{ width: size, height: size, ...style }}
      className={`flex items-center justify-center rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${TONES[tone]} ${className}`}
    >
      {children}
    </button>
  );
}
