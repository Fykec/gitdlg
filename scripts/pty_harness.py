"""Shared PTY helpers for gitdlg integration scripts."""

from __future__ import annotations

import fcntl
import os
import pty
import select
import signal
import struct
import termios
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "zig-out" / "bin" / "gitdlg"


def set_winsize(fd: int, rows: int, cols: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


class PtySession:
    """Run gitdlg on a PTY and answer vaxis capability / status queries."""

    def __init__(
        self,
        argv: list[str],
        *,
        rows: int = 30,
        cols: int = 100,
        env: dict[str, str] | None = None,
        terminal_app_probe: bool = False,
        use_vhs_record: bool = True,
    ) -> None:
        self.argv = argv
        self.rows = rows
        self.cols = cols
        self.extra_env = env or {}
        self.terminal_app_probe = terminal_app_probe
        self.use_vhs_record = use_vhs_record
        self.master: int | None = None
        self.pid: int | None = None
        self.output = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        pid, master = pty.fork()
        if pid == 0:
            os.environ.update(self.extra_env)
            if self.use_vhs_record:
                os.environ.setdefault("VHS_RECORD", "1")
            os.environ.setdefault("TERM", "xterm-256color")
            os.execv(self.argv[0], self.argv)
        self.pid = pid
        self.master = master
        set_winsize(master, self.rows, self.cols)
        self._thread = threading.Thread(target=self._relay, daemon=True)
        self._thread.start()

    def _respond(self, chunk: bytes) -> None:
        assert self.master is not None
        fd = self.master
        if b"\x1b[6n" in chunk:
            if self.terminal_app_probe:
                # Terminal.app false-positive for vaxis explicit-width probe.
                os.write(fd, b"\x1b[1;2R")
            else:
                os.write(fd, f"\x1b[{self.rows};{self.cols}R".encode())
        if b"\x1b[c" in chunk:
            os.write(fd, b"\x1b[?1;2c")
        if b"\x1b[5n" in chunk:
            os.write(fd, b"\x1b[0n")

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
            self._respond(chunk)

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
    terminal_app_probe: bool = False,
    use_vhs_record: bool = True,
    start_delay: float = 0.8,
    exit_timeout: float = 8.0,
) -> tuple[int, bytes]:
    session = PtySession(
        [str(BIN), str(msg_path)],
        rows=rows,
        cols=cols,
        env=env,
        terminal_app_probe=terminal_app_probe,
        use_vhs_record=use_vhs_record,
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
