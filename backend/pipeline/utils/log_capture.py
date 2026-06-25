import sys


class _TeeWriter:

    def __init__(self, orig, lines, prefix=''):
        self._orig = orig
        self._lines = lines
        self._prefix = prefix

    def write(self, text):
        if self._orig:
            self._orig.write(text)
        stripped = text.rstrip('\n')
        if stripped:
            self._lines.append(f'{self._prefix}{stripped}')

    def flush(self):
        if self._orig:
            self._orig.flush()


class LogCapture:

    def __init__(self):
        self._lines = []
        self._orig_stdout = None
        self._orig_stderr = None

    def start(self):
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = _TeeWriter(self._orig_stdout, self._lines)
        sys.stderr = _TeeWriter(self._orig_stderr, self._lines, prefix='WARN: ')

    def flush(self) -> str:
        result = '\n'.join(self._lines)
        self._lines.clear()
        return result

    def stop(self):
        if self._orig_stdout:
            sys.stdout = self._orig_stdout
        if self._orig_stderr:
            sys.stderr = self._orig_stderr
