/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1"/"true" to show the live-view (WebRTC) control in the UI. */
  readonly VITE_LIVE_VIEW_ENABLED?: string;
  /** Port the WebRTC signaling server listens on (default 8001). */
  readonly VITE_LIVE_VIEW_PORT?: string;
  /** Shared secret matching backend LIVE_VIEW_TOKEN (baked into the bundle). */
  readonly VITE_LIVE_VIEW_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
