FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# WORKDIR is a sibling of /app/data (mounted in docker-compose.yml), mirroring the
# backend/ + data/ layout on the host — config/settings.py derives
# PLAYWRIGHT_PROJECT_ROOT from BASE_DIR.parent, so this path match is required.
WORKDIR /app/backend

# Node is required for pipeline/mcp_bridge.py, which spawns this project's own
# node_modules/@playwright/mcp as a child process.
# xvfb provides a virtual X display so the runner can launch HEADED Chromium
# (HEADED=true) on a screenless container — see docker-entrypoint.sh.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        xvfb \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# --- WebRTC live-view (live_view/webrtc_server.py) ---
# GStreamer streams the Xvfb :99 display to the browser over WebRTC. Runtime plugins:
#   plugins-good = ximagesrc + vp8enc + rtp;  plugins-bad = webrtcbin + dtls/srtp;
#   nice = ICE (libnice).  The gir1.2-* typelibs expose Gst/GstSdp/GstWebRTC to Python.
# The build deps (libgirepository/gcc/pkg-config/cairo) let pip build PyGObject against
# this container's /usr/local python — the apt python3-gi targets a DIFFERENT interpreter.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gstreamer1.0-tools \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-nice \
        gir1.2-gstreamer-1.0 \
        gir1.2-gst-plugins-base-1.0 \
        gir1.2-gst-plugins-bad-1.0 \
        libgirepository1.0-dev \
        libcairo2-dev \
        pkg-config \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt package.json ./
# Two SEPARATE Playwright browsers are required:
#   - `playwright install chromium`  -> the runner's pytest-playwright chromium
#   - `@playwright/mcp install-browser chrome-for-testing` -> the browser the MCP
#     bridge (planner/generator discovery) launches; it will ONLY use chrome-for-testing.
# Omitting the second one leaves the planner/generator blind: every browser tool call
# returns 'Browser "chrome-for-testing" is not installed', so the planner fabricates a
# plan from priors and the run fails at the runner (see Export Activity Logs, 2026-07-27).
RUN pip install --no-cache-dir -r requirements.txt \
    && npm install \
    && python -m playwright install --with-deps chromium \
    && npx @playwright/mcp install-browser chrome-for-testing

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
# 8001 = WebRTC live-view signaling (WebSocket). Media flows over separate UDP ports
# (see LIVE_VIEW_MIN/MAX_PORT + the docker-compose port range and EC2 security group).
EXPOSE 8001

ENTRYPOINT ["./docker-entrypoint.sh"]