import { ReactNode } from 'react';
import { useLiveBrowser, LiveStatus } from '../hooks/useLiveBrowser';

const STATUS: Record<LiveStatus, { label: string; dot: string }> = {
  connecting: { label: 'Connecting…', dot: 'bg-warning animate-pulse' },
  live:       { label: 'Live',        dot: 'bg-success animate-pulse' },
  error:      { label: 'Error',       dot: 'bg-error' },
  closed:     { label: 'Disconnected', dot: 'bg-border-subtle' },
};

interface Props {
  /** Drives the WebRTC connection — unmounting or passing false tears it down. */
  active?: boolean;
  /** Slot at the right of the header (e.g. a close button when used in a modal). */
  headerRight?: ReactNode;
  className?: string;
  /** Tailwind aspect class for the video box. */
  aspect?: string;
}

/**
 * The live browser stream (Xvfb :99 over WebRTC) without any surrounding chrome, so it can
 * be used both as a standalone modal (LiveBrowserModal) and inline inside the create-test
 * slide-over while the pipeline runs.
 */
export function LiveBrowserPanel({
  active = true,
  headerRight,
  className = '',
  aspect = 'aspect-[16/10]',
}: Props) {
  const { videoRef, status, error } = useLiveBrowser(active);
  const s = STATUS[status];

  return (
    <div className={className}>
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${s.dot}`} />
          <span className="text-sm font-semibold text-text-primary">Live browser — {s.label}</span>
        </div>
        {headerRight}
      </div>

      {/* muted + playsInline so browsers allow autoplay of the incoming stream */}
      <div className="bg-black">
        <video ref={videoRef} autoPlay playsInline muted className={`w-full ${aspect} bg-black`} />
      </div>

      {error && <p className="px-4 py-2 text-xs text-error">{error}</p>}
    </div>
  );
}
