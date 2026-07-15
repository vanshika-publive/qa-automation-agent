import { useEffect } from 'react';

const SIZES = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-3xl',
} as const;

export function Modal({
  onClose,
  children,
  size = 'sm',
  backdropClassName = 'bg-black/50',
  cardClassName = '',
}: {
  onClose: () => void;
  children: React.ReactNode;
  size?: keyof typeof SIZES;
  backdropClassName?: string;
  cardClassName?: string;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className={`fixed inset-0 flex items-center justify-center z-50 p-4 ${backdropClassName}`}
      onClick={onClose}
    >
      <div
        className={`bg-surface-main rounded-2xl shadow-2xl w-full overflow-hidden ${SIZES[size]} ${cardClassName}`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
