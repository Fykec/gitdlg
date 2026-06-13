#!/usr/bin/env python3
"""PTY tests for terminal protocol garbage (Warp mouse/CSI leaks)."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pty_harness import PtySession, editor_argv  # noqa: E402

GARBAGE = "│  │[M][0]:ƚƚ".encode("utf-8")
EXPECTED = "clean subject"
BAD_MARKERS = ("│", "[M", "ƚ", "ƙ")
CANCEL_BUTTON_X = 75
BUTTON_Y = 26


def run_case(
    name: str,
    *,
    garbage: bytes,
    env: dict[str, str],
    send_garbage_at: float,
    fragmented: bool,
    strict_subject: bool,
) -> bool:
    work = Path(tempfile.mkdtemp(prefix=f"gitdlg-warp-{name}-"))
    msg = work / "COMMIT_EDITMSG"
    msg.write_text("# comment\n\n", encoding="utf-8")

    base_env = {
        "LANG": "en_US.UTF-8",
        "TERM": "xterm-256color",
    }
    base_env.update(env)

    session = PtySession(editor_argv() + [str(msg)], env=base_env, rows=40, cols=120)
    session.start()
    try:
        time.sleep(send_garbage_at)
        if fragmented:
            for b in garbage:
                session.send(bytes([b]))
                time.sleep(0.01)
        else:
            session.send(garbage)
        time.sleep(0.15)
        session.send(EXPECTED.encode("utf-8") + b"\x13")
        time.sleep(0.2)
        code = session.wait(8.0)
    finally:
        session.close()

    saved = msg.read_text(encoding="utf-8")
    subject = saved.split("\n", 1)[0] if saved else ""
    bad = any(marker in subject for marker in BAD_MARKERS)
    if strict_subject:
        ok = code == 0 and subject == EXPECTED and not bad
    else:
        ok = code == 0 and subject.endswith(EXPECTED) and not bad
    print(f"{name}: exit={code} subject={subject!r} ok={ok}")
    return ok


def run_sgr_cancel_click() -> bool:
    work = Path(tempfile.mkdtemp(prefix="gitdlg-warp-sgr-cancel-"))
    msg = work / "COMMIT_EDITMSG"
    original = "# comment\n\nexisting subject\n"
    msg.write_text(original, encoding="utf-8")

    session = PtySession(
        editor_argv() + [str(msg)],
        env={"LANG": "en_US.UTF-8", "TERM": "xterm-256color", "TERM_PROGRAM": "WarpTerminal"},
        rows=40,
        cols=120,
    )
    session.start()
    try:
        time.sleep(0.5)
        session.send(f"\x1b[<0;{CANCEL_BUTTON_X};{BUTTON_Y}M".encode("ascii"))
        time.sleep(0.4)
        assert session.pid is not None
        press_pid, _ = os.waitpid(session.pid, os.WNOHANG)
        session.send(f"\x1b[<0;{CANCEL_BUTTON_X};{BUTTON_Y}m".encode("ascii"))
        code = session.wait(8.0)
    finally:
        session.close()

    saved = msg.read_text(encoding="utf-8")
    ok = press_pid == 0 and code == 0 and saved == original
    print(f"sgr_cancel_click: press_exited={press_pid != 0} exit={code} ok={ok}")
    return ok


def main() -> int:
    warp_env = {"TERM_PROGRAM": "WarpTerminal", "LANG": "zh_CN.UTF-8"}
    cases = [
        ("warp_startup_bulk", GARBAGE, warp_env, 0.05, False, True),
        ("warp_startup_fragmented", GARBAGE, warp_env, 0.05, True, False),
        ("warp_late_bulk", GARBAGE, warp_env, 0.9, False, True),
        ("mouse_esc", b"\x1b[M!!", {}, 0.9, False, False),
    ]
    results = [
        run_case(
            name,
            garbage=garbage,
            env=env,
            send_garbage_at=when,
            fragmented=frag,
            strict_subject=strict,
        )
        for name, garbage, env, when, frag, strict in cases
    ]
    sgr_cancel = run_sgr_cancel_click()
    required = [results[0], results[2], sgr_cancel]
    if all(required):
        print("PASS warp-garbage (startup + late bulk)")
        if all(results):
            print("PASS warp-garbage (all cases)")
        return 0
    print("FAIL warp-garbage")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
