// Read-only guard for the AI pipeline's OBSERVATION browser (planner + generator).
//
// Injected via `@playwright/mcp --init-script`, so it runs in EVERY page before any of the
// page's own scripts and survives SPA route changes. Its job: make a stray confirm-click
// (Delete / Publish / Unpublish / Update / Save) during UI exploration a no-op against the
// LIVE dashboard. The planner/generator only need to *observe* the UI to write a plan/spec —
// they must never actually mutate production data. Real mutations happen only in the runner,
// which executes pytest directly and never loads this script.
//
// Reads (GET / HEAD) pass through untouched; only state-changing methods are neutralized.
// SINGLE RELAXATION KNOB: if a legitimate READ on this dashboard ever travels over POST
// (e.g. a GraphQL or search endpoint), drop 'POST' from BLOCKED_METHODS below.
(() => {
  const BLOCKED_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
  const isBlocked = (method) => BLOCKED_METHODS.has(String(method || 'GET').toUpperCase());

  const warn = (msg) => { try { console.warn('[readonly-guard] ' + msg); } catch (e) {} };

  const blockedResponse = () => new Response(
    JSON.stringify({ blocked: true, reason: 'read-only planning session' }),
    { status: 403, statusText: 'Blocked by read-only guard',
      headers: { 'Content-Type': 'application/json' } }
  );

  // --- fetch() ---
  const nativeFetch = window.fetch;
  if (typeof nativeFetch === 'function') {
    window.fetch = function (input, init) {
      const method = (init && init.method) ||
        (input && typeof input === 'object' && input.method) || 'GET';
      if (isBlocked(method)) {
        warn('blocked ' + String(method).toUpperCase() + ' ' +
          ((input && input.url) || String(input || '')));
        return Promise.resolve(blockedResponse());
      }
      return nativeFetch.apply(this, arguments);
    };
  }

  // --- XMLHttpRequest ---
  const nativeOpen = XMLHttpRequest.prototype.open;
  const nativeSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__ro_method = method;
    this.__ro_url = url;
    this.__ro_blocked = isBlocked(method);
    return nativeOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    if (!this.__ro_blocked) return nativeSend.apply(this, arguments);
    warn('blocked ' + String(this.__ro_method).toUpperCase() + ' ' + this.__ro_url);
    // Simulate a completed-but-forbidden request so callers resolve instead of hanging.
    const set = (k, v) => { try { Object.defineProperty(this, k, { value: v, configurable: true }); } catch (e) {} };
    set('readyState', 4);
    set('status', 403);
    set('responseText', '{"blocked":true}');
    set('response', '{"blocked":true}');
    try { this.dispatchEvent(new Event('readystatechange')); } catch (e) {}
    try { this.dispatchEvent(new Event('load')); } catch (e) {}
    try { this.dispatchEvent(new Event('loadend')); } catch (e) {}
  };

  // --- navigator.sendBeacon() (telemetry / unload POSTs) ---
  if (navigator && typeof navigator.sendBeacon === 'function') {
    navigator.sendBeacon = function () { warn('blocked sendBeacon'); return true; };
  }
})();
