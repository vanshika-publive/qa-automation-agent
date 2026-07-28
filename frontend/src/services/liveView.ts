// Layer 1 — pure. Builds the WebRTC signaling WebSocket URL for the live-view streamer
// (backend/live_view/webrtc_server.py). The streamer listens on its OWN port
// (LIVE_VIEW_PORT, default 8001), NOT behind the Vite /api proxy, so we derive the host
// from the current page origin and append the shared token. No React, no state.

const LIVE_VIEW_PORT = import.meta.env.VITE_LIVE_VIEW_PORT || '8001';
const LIVE_VIEW_TOKEN = import.meta.env.VITE_LIVE_VIEW_TOKEN || '';
const LIVE_VIEW_ENABLED = import.meta.env.VITE_LIVE_VIEW_ENABLED;

/** Whether the live-view control should be offered in the UI. */
export function isLiveViewEnabled(): boolean {
  return LIVE_VIEW_ENABLED === '1' || LIVE_VIEW_ENABLED === 'true';
}

/** ws(s)://<page-host>:<port>/ws/live?token=... — protocol tracks the page to avoid mixed-content. */
export function liveViewWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.hostname;
  const query = LIVE_VIEW_TOKEN ? `?token=${encodeURIComponent(LIVE_VIEW_TOKEN)}` : '';
  return `${proto}://${host}:${LIVE_VIEW_PORT}/ws/live${query}`;
}
