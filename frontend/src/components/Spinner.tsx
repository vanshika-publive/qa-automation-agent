export function Spinner({ size = 32, className = '' }: { size?: number; className?: string }) {
  const border = size >= 24 ? 'border-4' : 'border-2';
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block ${border} border-primary/20 border-t-primary rounded-full animate-spin ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
