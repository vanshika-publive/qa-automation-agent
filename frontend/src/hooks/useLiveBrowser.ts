import { useCallback, useEffect, useRef, useState } from 'react';
import { liveViewWsUrl } from '../services/liveView';

export type LiveStatus = 'connecting' | 'live' | 'error' | 'closed';

// Layer 2 — owns the WebRTC + signaling lifecycle for the live browser stream.
// The GStreamer server (webrtcbin) is the OFFERER: it fires on-negotiation-needed, sends us
// an SDP offer over the signaling WebSocket, and we answer. Video arrives on a recvonly
// track; we attach it to the <video> element via `videoRef`. `active` toggles the whole
// connection so the caller can open/close it with a modal.
export function useLiveBrowser(active: boolean) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [status, setStatus] = useState<LiveStatus>('connecting');
  const [error, setError] = useState<string | null>(null);

  const fail = useCallback((msg: string) => {
    setStatus('error');
    setError(msg);
  }, []);

  useEffect(() => {
    if (!active) return;
    setStatus('connecting');
    setError(null);

    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    });
    let ws: WebSocket;

    // Server -> us: the remote video track. Attach the whole stream to the <video>.
    pc.ontrack = (e) => {
      if (videoRef.current) videoRef.current.srcObject = e.streams[0];
    };
    pc.onconnectionstatechange = () => {
      const st = pc.connectionState;
      if (st === 'connected') setStatus('live');
      else if (st === 'failed' || st === 'disconnected') fail(`WebRTC connection ${st}`);
    };

    try {
      ws = new WebSocket(liveViewWsUrl());
    } catch (err) {
      fail(`Could not open signaling socket: ${String(err)}`);
      pc.close();
      return;
    }

    // Our ICE candidates -> server (trickle).
    pc.onicecandidate = (e) => {
      if (e.candidate && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'ice',
          candidate: e.candidate.candidate,
          sdpMLineIndex: e.candidate.sdpMLineIndex,
        }));
      }
    };

    ws.onmessage = async (ev) => {
      let msg: { type?: string; sdp?: string; candidate?: string; sdpMLineIndex?: number };
      try { msg = JSON.parse(ev.data); } catch { return; }

      if (msg.type === 'offer' && msg.sdp) {
        await pc.setRemoteDescription({ type: 'offer', sdp: msg.sdp });
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        ws.send(JSON.stringify({ type: 'answer', sdp: answer.sdp }));
      } else if (msg.type === 'ice' && msg.candidate) {
        try {
          await pc.addIceCandidate({
            candidate: msg.candidate,
            sdpMLineIndex: msg.sdpMLineIndex ?? 0,
          });
        } catch { /* ignore late/duplicate candidates */ }
      }
    };
    ws.onerror = () => fail('Signaling socket error — is the live-view streamer running on :8001?');
    ws.onclose = () => setStatus((s) => (s === 'live' ? 'closed' : s));

    return () => {
      ws.close();
      pc.close();
    };
  }, [active, fail]);

  return { videoRef, status, error };
}
