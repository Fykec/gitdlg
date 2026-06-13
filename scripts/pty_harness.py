"""PTY helpers for gitdlg integration tests."""

from __future__ import annotations

import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITDLG = ROOT / "gitdlg.py"


def editor_argv() -> list[str]:
    override = os.environ.get("GITDLG_BIN")
    if override:
        path = Path(override)
        if path.suffix == ".py":
            return [sys.executable, str(path)]
        return [str(path)]
    return [sys.executable, str(GITDLG)]


def set_winsize(fd: int, rows: int, cols: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def disable_terminal_flow_control(fd: int = 0) -> None:
    try:
        attr = termios.tcgetattr(fd)
        attr[0] &= ~(termios.IXON | termios.IXOFF)
        termios.tcsetattr(fd, termios.TCSANOW, attr)
    except termios.error:
        pass


class PtySession:
    def __init__(
        self,
        argv: list[str],
        *,
        rows: int = 30,
        cols: int = 100,
        env: dict[str, str] | None = None,
    ) -> None:
        self.argv = argv
        self.rows = rows
        self.cols = cols
        self.extra_env = env or {}
        self.master: int | None = None
        self.pid: int | None = None
        self.output = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        pid, master = pty.fork()
        if pid == 0:
            disable_terminal_flow_control(0)
            os.environ.update(self.extra_env)
            os.environ.setdefault("TERM", "xterm-256color")
            os.execv(self.argv[0], self.argv)
        self.pid = pid
        self.master = master
        set_winsize(master, self.rows, self.cols)
        self._thread = threading.Thread(target=self._relay, daemon=True)
        self._thread.start()

    def _relay(self) -> None:
        assert self.master is not None
        fd = self.master
        while not self._stop.is_set():
            ready, _, _ = select.select([fd], [], [], 0.05)
            if not ready:
                continue
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            with self._lock:
                self.output.extend(chunk)

    def send(self, data: bytes) -> None:
        assert self.master is not None
        os.write(self.master, data)

    def read_output(self) -> bytes:
        with self._lock:
            return bytes(self.output)

    def wait(self, timeout: float = 8.0) -> int:
        assert self.pid is not None
        deadline = time.time() + timeout
        while time.time() < deadline:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                return os.waitstatus_to_exitcode(status)
            time.sleep(0.05)
        os.kill(self.pid, signal.SIGTERM)
        time.sleep(0.2)
        try:
            _, status = os.waitpid(self.pid, 0)
            return os.waitstatus_to_exitcode(status)
        except ChildProcessError:
            return -1

    def close(self) -> None:
        self._stop.set()
        if self.master is not None:
            try:
                os.close(self.master)
            except OSError:
                pass
            self.master = None


def run_editor(
    msg_path: Path,
    keys: bytes,
    *,
    rows: int = 30,
    cols: int = 100,
    env: dict[str, str] | None = None,
    start_delay: float = 0.8,
    exit_timeout: float = 8.0,
) -> tuple[int, bytes]:
    session = PtySession(
        editor_argv() + [str(msg_path)],
        rows=rows,
        cols=cols,
        env=env,
    )
    session.start()
    try:
        time.sleep(start_delay)
        if keys:
            session.send(keys)
        code = session.wait(exit_timeout)
        return code, session.read_output()
    finally:
        session.close()
