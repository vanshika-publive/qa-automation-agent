#!/bin/sh
set -e

# Headed Chromium (HEADED=true) needs an X display, which a Railway container lacks.
# Start a virtual framebuffer and point DISPLAY at it. The Django server — and every
# child it spawns (the pytest runner AND the @playwright/mcp planner/generator
# browsers) — inherits this DISPLAY, so all browsers render into Xvfb on :99 instead
# of dying with "Missing X server or $DISPLAY".
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99

# Live view (opt-in): export the :99 display over HTTP via VNC so the whole pipeline's
# browsing can be watched in a browser at http://<host>:6080/vnc.html. OFF by default —
# every browser here is logged into the live dashboard, so require VNC_ENABLED=true AND
# a VNC_PASSWORD before exposing anything.
if [ "$VNC_ENABLED" = "true" ] && [ -n "$VNC_PASSWORD" ]; then
    x11vnc -storepasswd "$VNC_PASSWORD" /tmp/.x11vnc.pass >/dev/null 2>&1\
    x11vnc -display :99 -rfbauth /tmp/.x11vnc.pass -forever -shared -rfbport 5900 \
        -noxdamage -bg -o /tmp/x11vnc.log
    websockify --web=/usr/share/novnc "${NOVNC_PORT:-6080}" localhost:5900 \
        >/tmp/novnc.log 2>&1 &
    echo "[entrypoint] noVNC live view ENABLED on :${NOVNC_PORT:-6080} (/vnc.html)"
else
    echo "[entrypoint] noVNC live view disabled (set VNC_ENABLED=true + VNC_PASSWORD to enable)"
fi

python manage.py makemigrations --noinput
python manage.py migrate --fake-initial --noinput

exec python manage.py runserver "0.0.0.0:${PORT:-8000}"
