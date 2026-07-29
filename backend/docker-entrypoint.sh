#!/bin/sh
set -e

# Headed Chromium (HEADED=true) needs an X display, which a Railway container lacks.
# Start a virtual framebuffer and point DISPLAY at it. The Django server — and every
# child it spawns, including the pytest runner — inherits this DISPLAY, so headed
# browser launches render into Xvfb instead of dying with "Missing X server or $DISPLAY".
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99

# WebRTC live-view (opt-in via LIVE_VIEW_ENABLED). When on: force HEADED so the MCP
# planner/generator browsers AND the pytest runner render into Xvfb :99 (otherwise they
# run headless and there is nothing to capture), then start the standalone streamer
# (live_view/webrtc_server.py) in the background. It exposes WebSocket signaling on
# :${LIVE_VIEW_PORT:-8001}; the Django server below is unaffected either way.
case "${LIVE_VIEW_ENABLED:-}" in
  1|true|TRUE|yes|YES)
    export HEADED=true
    echo "[entrypoint] live-view ENABLED — headed browsers + WebRTC streamer on :${LIVE_VIEW_PORT:-8001}"
    python -m live_view >/tmp/live_view.log 2>&1 &
    ;;
esac

python manage.py makemigrations --noinput
python manage.py migrate --fake-initial --noinput

exec python manage.py runserver "0.0.0.0:${PORT:-8000}"
