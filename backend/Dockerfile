FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# WORKDIR is a sibling of /app/data (mounted in docker-compose.yml), mirroring the
# backend/ + data/ layout on the host — config/settings.py derives
# PLAYWRIGHT_PROJECT_ROOT from BASE_DIR.parent, so this path match is required.
WORKDIR /app/backend

# Node is required for pipeline/mcp_bridge.py, which spawns this project's own
# node_modules/@playwright/mcp as a child process.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt package.json ./
RUN pip install --no-cache-dir -r requirements.txt \
    && npm install \
    && python -m playwright install --with-deps chromium

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
