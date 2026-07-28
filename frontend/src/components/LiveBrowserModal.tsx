import { X } from 'lucide-react';
import { Modal } from './Modal';
import { useLiveBrowser, LiveStatus } from '../hooks/useLiveBrowser';

const STATUS: Record<LiveStatus, { label: string; dot: string }> = {
  connecting: { label: 'Connecting…', dot: 'bg-warning animate-pulse' },
  live:       { label: 'Live',        dot: 'bg-success animate-pulse' },
  error:      { label: 'Error',       dot: 'bg-error' },
  closed:     { label: 'Disconnected', dot: 'bg-border-subtle' },
};

/**
 * Live view of the pipeline's headed browser, streamed from the container's Xvfb :99 over
 * WebRTC. Mounting this modal opens the connection; unmounting tears it down.
 */
export function LiveBrowserModal({ onClose }: { onClose: () => void }) {
  const { videoRef, status, error } = useLiveBrowser(true);
  const s = STATUS[status];

  return (
    <Modal onClose={onClose} size="lg" cardClassName="max-w-4xl">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${s.dot}`} />
          <h2 className="text-sm font-semibold text-text-primary">Live browser — {s.label}</h2>
        </div>
        <button onClick={onClose} className="text-text-secondary hover:text-text-primary transition-colors">
          <X size={18} />
        </button>
      </div>

      <div className="bg-black">
        {/* muted + playsInline so browsers allow autoplay of the incoming stream */}
        <video ref={videoRef} autoPlay playsInline muted className="w-full aspect-[16/10] bg-black" />
      </div>

      {error && <p className="px-5 py-3 text-xs text-error">{error}</p>}
      <p className="px-5 py-3 text-[11px] text-text-secondary/70 border-t border-border-subtle">
        Streaming the pipeline's headed browser (Xvfb&nbsp;:99) over WebRTC — shows whichever run
        is currently active on the server.
      </p>
    </Modal>
  );
}
