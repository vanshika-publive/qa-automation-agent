import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from django.conf import settings

from pipeline.constants import MCP_TIMEOUT_MS, MCP_PROTOCOL_VERSION, PLAYWRIGHT_BROWSER
from pipeline.utils.credential_manager import CredentialManager

@dataclass
class _PendingRequest:
    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: Optional[str] = None


class MCPBridge:

    def __init__(self, project_root: Optional[str] = None, read_only: bool = False):
        self._project_root = project_root or settings.PLAYWRIGHT_PROJECT_ROOT
        cli_path = MCPBridge._find_cli()

        session_path = os.path.join(self._project_root, '.auth', 'session.json')
        # @playwright/mcp only honors --storage-state when --isolated is also set ("path to the
        # storage state file for isolated sessions"). Without --isolated it falls back to a default
        # persistent profile and silently ignores the stored session, so every page redirects to
        # /login. Pass both together so the captured MFA-cleared session actually authenticates.
        session_args = ['--isolated', '--storage-state', session_path] if os.path.isfile(session_path) else []

        # Read-only mode (planner + generator): inject readonly_guard.js into every page so a stray
        # confirm-click during UI exploration cannot mutate the live dashboard. The guard neutralizes
        # POST/PUT/PATCH/DELETE in-browser; reads (GET/HEAD) are untouched. The runner does NOT use
        # MCPBridge (it runs pytest directly), so real test mutations are unaffected.
        readonly_args = []
        if read_only:
            guard_path = os.path.join(os.path.dirname(__file__), 'readonly_guard.js')
            readonly_args = ['--init-script', guard_path]
            print('[MCPBridge] read-only mode ON — mutating HTTP (POST/PUT/PATCH/DELETE) blocked in-browser')

        # HEADED=true → pass --headed EXPLICITLY (don't rely on @playwright/mcp's auto-default
        # `headless = linux && !DISPLAY`, which silently falls back to headless if DISPLAY isn't
        # effective for this child) so the planner/generator browser is actually visible on the
        # Xvfb display (:99) and watchable over noVNC. Otherwise --headless so it needs no display
        # on a screenless container. --no-sandbox: the container runs as root and Chromium refuses
        # to launch as root with the sandbox enabled.
        headed = os.environ.get('HEADED', '').strip().lower() in ('true', '1', 'yes')
        launch_args = ['--no-sandbox'] + (['--headed'] if headed else ['--headless'])

        args = ['--browser', PLAYWRIGHT_BROWSER] + launch_args + session_args + readonly_args

        # A headed browser needs DISPLAY. The child inherits our env, but guarantee it points at
        # the Xvfb display so --headed can't crash with "Missing X server" if DISPLAY got dropped.
        child_env = dict(os.environ)
        if headed and not child_env.get('DISPLAY'):
            child_env['DISPLAY'] = ':99'
        print(f'[MCPBridge] launching MCP browser: headed={headed} '
              f'DISPLAY={child_env.get("DISPLAY")!r} launch_args={launch_args}')

        self.proc = subprocess.Popen(
            ['node', cli_path] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
            cwd=self._project_root,
            env=child_env,
        )

        self._next_id = 1
        self._pending: dict[int, _PendingRequest] = {}
        self._lock = threading.Lock()
        self._closed = False

        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        self._initialize()

    @staticmethod
    def _find_cli() -> str:
        backend_root = settings.BACKEND_ROOT
        cli_path = os.path.join(backend_root, 'node_modules', '@playwright', 'mcp', 'cli.js')
        if not os.path.isfile(cli_path):
            raise RuntimeError(
                '@playwright/mcp CLI not found at expected path:\n'
                f'  {cli_path}\n'
                f'Run: cd {backend_root} && npm install\n'
                '(If the package updated, check its package.json "bin" field for a renamed entry.)'
            )
        return cli_path

    def _read_loop(self):
        try:
            for line in self.proc.stdout:
                self._handle_line(line.strip())
        except Exception:
            pass

    def _handle_line(self, line: str):
        if not line:
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return
        msg_id = msg.get('id')
        if msg_id is None:
            return
        with self._lock:
            pending = self._pending.pop(msg_id, None)
        if pending is None:
            return
        if msg.get('error'):
            err = msg['error']
            pending.error = f"MCP error {err.get('code', '?')}: {err.get('message', '')}"
        else:
            pending.result = msg.get('result')
        pending.event.set()

    def _send(self, method: str, params=None, timeout_s: Optional[float] = None):
        if timeout_s is None:
            timeout_s = MCP_TIMEOUT_MS / 1000.0

        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            pending = _PendingRequest()
            self._pending[req_id] = pending

        request = {'jsonrpc': '2.0', 'id': req_id, 'method': method}
        if params is not None:
            request['params'] = params

        try:
            self.proc.stdin.write(json.dumps(request) + '\n')
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            with self._lock:
                self._pending.pop(req_id, None)
            raise RuntimeError(f'MCP process stdin error: {e}')

        if not pending.event.wait(timeout=timeout_s):
            with self._lock:
                self._pending.pop(req_id, None)
            raise TimeoutError(
                f'MCP call timed out after {timeout_s}s — method: {method}\n'
                'Possible causes: browser failed to launch, page navigation hung.'
            )

        if pending.error:
            raise RuntimeError(pending.error)
        return pending.result

    def _notify(self, method: str, params=None):
        notification = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            notification['params'] = params
        try:
            self.proc.stdin.write(json.dumps(notification) + '\n')
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def _initialize(self):
        self._send('initialize', {
            'protocolVersion': MCP_PROTOCOL_VERSION,
            'capabilities': {},
            'clientInfo': {'name': 'playwright-ai-tester', 'version': '1.0.0'},
        })
        self._notify('notifications/initialized')

        try:
            dashboard_url = CredentialManager.get_all()['dashboard_url'].rstrip('/')
            self._send('tools/call', {
                'name': 'browser_navigate',
                'arguments': {'url': f'{dashboard_url}/home'},
            })
        except Exception as e:
            print(f'[MCPBridge] warmup navigation skipped: {e}', file=sys.stderr)

    def list_tools(self) -> list:
        result = self._send('tools/list')
        return result.get('tools', []) if result else []

    def call_tool(self, name: str, args: dict) -> str:
        safe_args = args if isinstance(args, dict) else {}
        result = self._send('tools/call', {'name': name, 'arguments': safe_args})
        if result and 'content' in result:
            text_parts = [
                c.get('text', '')
                for c in result['content']
                if c.get('type') == 'text'
            ]
            if text_parts:
                return '\n'.join(text_parts)
        return json.dumps(result)

    def close(self):
        if self._closed:
            return
        self._closed = True
        with self._lock:
            for p in self._pending.values():
                p.error = 'MCPBridge closed'
                p.event.set()
            self._pending.clear()
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.kill()
        except Exception:
            pass