import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from django.conf import settings

from .constants import MCP_TIMEOUT_MS, MCP_PROTOCOL_VERSION, PLAYWRIGHT_BROWSER
from .credential_manager import get_credentials


@dataclass
class _PendingRequest:
    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: Optional[str] = None


def _find_mcp_cli() -> str:
    # node_modules live in backend/ (next to package.json), not in the data dir
    backend_root = settings.BACKEND_ROOT
    pkg_dir = os.path.join(backend_root, 'node_modules', '@playwright', 'mcp')
    pkg_json_path = os.path.join(pkg_dir, 'package.json')

    if not os.path.isfile(pkg_json_path):
        raise RuntimeError(
            '@playwright/mcp is not installed.\n'
            f'Run: cd {backend_root} && npm install'
        )

    with open(pkg_json_path, encoding='utf-8') as f:
        pkg = json.load(f)

    candidates = []
    bin_field = pkg.get('bin')
    if isinstance(bin_field, str):
        candidates.append(os.path.join(pkg_dir, bin_field))
    elif isinstance(bin_field, dict):
        for rel in bin_field.values():
            candidates.append(os.path.join(pkg_dir, rel))

    for c in candidates:
        if os.path.isfile(c):
            return c

    raise RuntimeError(
        'Found @playwright/mcp but could not locate its CLI entry.\n'
        f'Checked: {", ".join(candidates)}\n'
        'Inspect node_modules/@playwright/mcp/package.json -> "bin" field.'
    )


class MCPBridge:
    def __init__(self, project_root: Optional[str] = None, extra_args: Optional[list] = None):
        self._project_root = project_root or settings.PLAYWRIGHT_PROJECT_ROOT
        cli_path = _find_mcp_cli()

        session_path = os.path.join(self._project_root, '.auth', 'session.json')
        session_args = ['--storage-state', session_path] if os.path.isfile(session_path) else []

        args = ['--browser', PLAYWRIGHT_BROWSER] + session_args
        if extra_args:
            args += extra_args

        node_bin = 'node'
        self.proc = subprocess.Popen(
            [node_bin, cli_path] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
            cwd=self._project_root,
        )

        self._next_id = 1
        self._pending: dict[int, _PendingRequest] = {}
        self._lock = threading.Lock()
        self._closed = False

        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

        self._initialize()

    def _read_loop(self):
        try:
            for line in self.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg_id = msg.get('id')
                if msg_id is None:
                    continue
                with self._lock:
                    pending = self._pending.pop(msg_id, None)
                if pending is None:
                    continue
                if msg.get('error'):
                    err = msg['error']
                    pending.error = f"MCP error {err.get('code', '?')}: {err.get('message', '')}"
                else:
                    pending.result = msg.get('result')
                pending.event.set()
        except Exception:
            pass

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
            dashboard_url = get_credentials()['dashboard_url'].rstrip('/')
            self._send('tools/call', {
                'name': 'browser_navigate',
                'arguments': {'url': f'{dashboard_url}/home'},
            })
        except Exception as e:
            print(f'[MCPBridge] warmup navigation skipped: {e}', file=sys.stderr)

    def list_tools(self):
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
