"""
Live-view WebRTC streamer for the pipeline's headed browsers.

The pipeline renders every HEADED browser (the planner/generator MCP browser and the
pytest runner) into the container's shared Xvfb display :99 (see docker-entrypoint.sh).
This server captures that whole display with GStreamer, encodes it to VP8, and streams it
to the user's browser over WebRTC — so a user can watch, live, whatever the pipeline is
doing right now. We stream the DISPLAY (not a single browser) on purpose: the MCP spawns a
fresh, short-lived browser per planner run and per generator scenario, so following one
browser would flicker; the display always shows the current activity.

This is a STANDALONE asyncio process, NOT part of Django's sync `runserver` (WSGI cannot
speak WebSocket). docker-entrypoint.sh launches it in the background when LIVE_VIEW_ENABLED
is set. It needs the same DISPLAY (:99) the pipeline renders into, which it inherits from
the entrypoint's environment.

Signaling — JSON over an aiohttp WebSocket at:
    ws://<host>:<LIVE_VIEW_PORT>/ws/live?token=<LIVE_VIEW_TOKEN>
    server -> client : {"type":"offer","sdp":"..."}
                       {"type":"ice","candidate":"...","sdpMLineIndex":N}
    client -> server : {"type":"answer","sdp":"..."}
                       {"type":"ice","candidate":"...","sdpMLineIndex":N}

SECURITY: the streamed browser is authenticated to the REAL production dashboard, so the
stream is gated behind (a) LIVE_VIEW_ENABLED and (b) a shared LIVE_VIEW_TOKEN. Never expose
this port without the token set — anyone who can view the stream sees live prod data.
"""
import asyncio
import json
import os
import threading

import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp, GLib  # noqa: E402
from aiohttp import web, WSMsgType  # noqa: E402

DISPLAY = os.environ.get('DISPLAY', ':99')
STUN_SERVER = os.environ.get('LIVE_VIEW_STUN', 'stun://stun.l.google.com:19302')
FRAMERATE = int(os.environ.get('LIVE_VIEW_FPS', '15'))
BITRATE = int(os.environ.get('LIVE_VIEW_BITRATE', '2000000'))  # target, bits/sec
PORT = int(os.environ.get('LIVE_VIEW_PORT', '8001'))
TOKEN = os.environ.get('LIVE_VIEW_TOKEN', '')

# One pipeline per connected viewer (each gets its own capture+encode — fine for a
# low-viewer internal tool; switch to a shared `tee` if many viewers ever watch at once).
# use-damage=0 -> full frames (avoids missed-update artifacts); show-pointer=1 -> see clicks.
# vp8enc deadline=1 + cpu-used=4 keeps CPU sane for real-time on a server CPU.
PIPELINE_DESC = (
    'webrtcbin name=sendrecv bundle-policy=max-bundle latency=0 stun-server={stun} '
    'ximagesrc display-name={display} use-damage=0 show-pointer=1 '
    '! video/x-raw,framerate={fps}/1 ! videoconvert ! queue max-size-buffers=2 leaky=downstream '
    '! vp8enc deadline=1 cpu-used=4 target-bitrate={bitrate} keyframe-max-dist=30 '
    '! rtpvp8pay picture-id-mode=2 '
    '! application/x-rtp,media=video,encoding-name=VP8,payload=96 ! sendrecv.'
)


class WebRTCSession:
    """One viewer: a GStreamer pipeline + webrtcbin, bridged to an aiohttp WebSocket.

    GStreamer callbacks fire on the GLib main-loop thread; ws sends must run on the asyncio
    loop. We marshal every server->client message across with run_coroutine_threadsafe.
    """

    def __init__(self, ws: web.WebSocketResponse, loop: asyncio.AbstractEventLoop):
        self.ws = ws
        self.loop = loop
        self.pipe = Gst.parse_launch(PIPELINE_DESC.format(
            stun=STUN_SERVER, display=DISPLAY, fps=FRAMERATE, bitrate=BITRATE,
        ))
        self.webrtc = self.pipe.get_by_name('sendrecv')
        self.webrtc.connect('on-negotiation-needed', self._on_negotiation_needed)
        self.webrtc.connect('on-ice-candidate', self._on_ice_candidate)

    def start(self):
        self.pipe.set_state(Gst.State.PLAYING)

    def stop(self):
        self.pipe.set_state(Gst.State.NULL)

    def _send(self, payload: dict):
        # Called from the GLib thread — hop back onto the asyncio loop to send.
        asyncio.run_coroutine_threadsafe(self._safe_send(payload), self.loop)

    async def _safe_send(self, payload: dict):
        if not self.ws.closed:
            await self.ws.send_json(payload)

    # ---- GStreamer -> client (offer + our ICE) ----
    def _on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self._on_offer_created, element, None)
        element.emit('create-offer', None, promise)

    def _on_offer_created(self, promise, element, _data):
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        element.emit('set-local-description', offer, Gst.Promise.new())
        self._send({'type': 'offer', 'sdp': offer.sdp.as_text()})

    def _on_ice_candidate(self, _element, mlineindex: int, candidate: str):
        self._send({'type': 'ice', 'candidate': candidate, 'sdpMLineIndex': mlineindex})

    # ---- client -> GStreamer (answer + remote ICE) ----
    def on_answer(self, sdp_text: str):
        _res, sdpmsg = GstSdp.SDPMessage.new_from_text(sdp_text)
        answer = GstWebRTC.WebRTCSessionDescription.new(
            GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
        self.webrtc.emit('set-remote-description', answer, Gst.Promise.new())

    def on_remote_ice(self, candidate: str, mlineindex: int):
        self.webrtc.emit('add-ice-candidate', mlineindex, candidate)


async def ws_handler(request: web.Request):
    if TOKEN and request.query.get('token') != TOKEN:
        return web.Response(status=403, text='forbidden: bad or missing token')

    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    session = WebRTCSession(ws, asyncio.get_running_loop())
    session.start()
    print('[live-view] viewer connected')
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                continue
            kind = data.get('type')
            if kind == 'answer':
                session.on_answer(data['sdp'])
            elif kind == 'ice':
                session.on_remote_ice(data['candidate'], int(data.get('sdpMLineIndex', 0)))
    finally:
        session.stop()
        print('[live-view] viewer disconnected')
    return ws


async def health(_request: web.Request):
    return web.json_response({'ok': True, 'display': DISPLAY, 'fps': FRAMERATE})


def main():
    enabled = os.environ.get('LIVE_VIEW_ENABLED', '').strip().lower() in ('1', 'true', 'yes')
    if not enabled:
        print('[live-view] LIVE_VIEW_ENABLED not set — streamer disabled, exiting.')
        return
    if not TOKEN:
        print('[live-view] WARNING: LIVE_VIEW_TOKEN is empty — stream is UNAUTHENTICATED.')

    Gst.init(None)
    # webrtcbin's bus/callbacks need a running GLib main loop; run it on its own thread so
    # it coexists with aiohttp's asyncio loop (which owns the WebSocket I/O).
    glib_loop = GLib.MainLoop()
    threading.Thread(target=glib_loop.run, daemon=True).start()

    app = web.Application()
    app.router.add_get('/ws/live', ws_handler)
    app.router.add_get('/health', health)
    print(f'[live-view] WebRTC signaling on :{PORT} (display {DISPLAY}, {FRAMERATE}fps, '
          f'token={"set" if TOKEN else "NONE"})')
    web.run_app(app, host='0.0.0.0', port=PORT, print=None)


if __name__ == '__main__':
    main()
