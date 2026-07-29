import { X } from 'lucide-react';
import { Modal } from './Modal';
import { LiveBrowserPanel } from './LiveBrowserPanel';

/**
 * Live view of the pipeline's headed browser, streamed from the container's Xvfb :99 over
 * WebRTC. Mounting this modal opens the connection; unmounting tears it down.
 */
export function LiveBrowserModal({ onClose }: { onClose: () => void }) {
  return (
    <Modal onClose={onClose} size="lg" cardClassName="max-w-4xl">
      <LiveBrowserPanel
        headerRight={
          <button onClick={onClose} className="text-text-secondary hover:text-text-primary transition-colors">
            <X size={18} />
          </button>
        }
      />
      <p className="px-4 py-3 text-[11px] text-text-secondary/70 border-t border-border-subtle">
        Streaming the pipeline's headed browser (Xvfb&nbsp;:99) over WebRTC — shows whichever run
        is currently active on the server.
      </p>
    </Modal>
  );
}
