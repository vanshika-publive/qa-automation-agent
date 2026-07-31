#!/usr/bin/env bash
#
# Post-deploy smoke-check for the merged feature/codebase (Postgres artifacts + WebRTC
# live-view) on the EC2 single box. Run it ON THE BOX after:
#
#   docker compose -f docker-compose.yml -f docker-compose.webrtc.yml up -d --build
#
# It confirms, in one pass, that BOTH halves of the deploy are alive:
#   1. backend up + DB migrations applied (Postgres-artifacts half)
#   2. live-view streamer reachable + token gate working (WebRTC half)
#   3. a real pipeline execution runs end-to-end
#   4. tails both logs so you can watch the first live run
#
# It is READ-ONLY except for step 3, which kicks off one execution against a test you name.
# Nothing here deletes or publishes anything.
#
# Usage:
#   ./scripts/smoke-check-liveview.sh                 # steps 1-2 + log tail only
#   ./scripts/smoke-check-liveview.sh <TEST_ID>       # also kicks off one run (step 3)
#
# Env overrides (defaults match docker-compose.webrtc.yml):
#   API=http://127.0.0.1:8000   LIVE=http://127.0.0.1:8001
#   LIVE_VIEW_TOKEN=<secret>    (needed for the token-gate check to pass, not just 403)

set -u

API="${API:-http://127.0.0.1:8000}"
LIVE="${LIVE:-http://127.0.0.1:8001}"
TOKEN="${LIVE_VIEW_TOKEN:-}"
TEST_ID="${1:-}"

pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILED=1; }
hdr()  { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
FAILED=0

# ------------------------------------------------------------------ 1. backend + DB
hdr "1. Backend liveness + DB migrations"

health=$(curl -fsS --max-time 5 "$API/api/health" 2>/dev/null) \
  && pass "GET /api/health -> $health" \
  || fail "GET /api/health unreachable at $API (backend up? entrypoint finished migrating?)"

# The artifact tables must exist, else the Postgres-artifacts half never migrated.
if docker compose exec -T backend python manage.py showmigrations core 2>/dev/null \
     | grep -E '0003_artifact_tables|0004_backfill_artifacts' | grep -q '\[X\]'; then
  pass "core migrations 0003_artifact_tables / 0004_backfill_artifacts applied"
else
  fail "artifact migrations NOT applied — the Postgres-artifacts half is not live"
fi

# Sanity: the auth session the pipeline needs exists (in DB now, not on disk).
sess=$(docker compose exec -T backend python manage.py shell -c \
  "from core.models import AuthSession; print(AuthSession.objects.count())" 2>/dev/null | tr -d '\r')
case "$sess" in
  ""|0) warn "no AuthSession row found — a real run will fail auth until you capture/upload a session" ;;
  *)    pass "AuthSession present ($sess row(s))" ;;
esac

# ------------------------------------------------------------------ 2. live-view streamer
hdr "2. WebRTC live-view streamer (:8001)"

lv=$(curl -fsS --max-time 5 "$LIVE/health" 2>/dev/null) \
  && pass "GET :8001/health -> $lv" \
  || fail "streamer /health unreachable — LIVE_VIEW_ENABLED=1 set? check /tmp/live_view.log in the container"

# The signaling WS must reject a bad/missing token (403). A 101/upgrade on a bad token
# means the gate is OPEN — that's a security problem, not a pass.
code=$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 5 "$LIVE/ws/live?token=deliberately-wrong" 2>/dev/null)
if [ "$code" = "403" ]; then
  pass "signaling rejects a bad token (403) — token gate is enforced"
elif [ -z "$TOKEN" ]; then
  warn "bad-token request returned $code and no LIVE_VIEW_TOKEN set here — if the server token is also empty the stream is UNAUTHENTICATED"
else
  fail "bad-token request returned $code (expected 403) — token gate may be OPEN"
fi

# Xvfb must actually be up inside the container, else there's nothing to capture (black video).
if docker compose exec -T backend sh -c 'DISPLAY=:99 xdpyinfo >/dev/null 2>&1'; then
  pass "Xvfb :99 is live inside the backend container (something to capture)"
else
  warn "could not confirm Xvfb :99 (xdpyinfo missing or display down) — video may be black"
fi

# ------------------------------------------------------------------ 3. one real run
hdr "3. End-to-end pipeline run"

if [ -z "$TEST_ID" ]; then
  warn "no TEST_ID arg — skipping the live run. Re-run as: $0 <TEST_ID>"
else
  resp=$(curl -fsS --max-time 10 -X POST "$API/api/executions/tests/$TEST_ID/run" 2>/dev/null)
  exec_id=$(printf '%s' "$resp" | sed -n 's/.*"executionId"[: ]*"\([^"]*\)".*/\1/p')
  if [ -n "$exec_id" ]; then
    pass "kicked off execution $exec_id (open ExecutionDetail and click 'Watch live' now)"
    printf '     poll: curl -s %s/api/executions/%s | python -c "import sys,json;print(json.load(sys.stdin)[\"data\"][\"status\"])"\n' "$API" "$exec_id"
  else
    fail "run POST did not return an executionId — response was: $resp"
  fi
fi

# ------------------------------------------------------------------ 4. tail both logs
hdr "4. Live logs (Ctrl-C to stop)"
echo "  backend  = docker compose logs -f backend"
echo "  streamer = docker compose exec backend tail -f /tmp/live_view.log"
echo
if [ "$FAILED" = "1" ]; then
  printf '\033[31mSMOKE CHECK FAILED — fix the ✗ items above before trusting the deploy.\033[0m\n'
else
  printf '\033[32mChecks passed. Tailing backend + streamer logs...\033[0m\n'
fi
echo
# Interleave both logs so the first live run is visible in one stream.
( docker compose exec -T backend tail -f /tmp/live_view.log 2>/dev/null | sed 's/^/[live] /' & )
docker compose logs -f backend 2>/dev/null | sed 's/^/[api ] /'

exit "$FAILED"
