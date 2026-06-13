#!/usr/bin/env python3
"""PTY test for commit.template strip on open and prefix on save."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pty_harness import PtySession, editor_argv  # noqa: E402

TEMPLATE = Path("/tmp/gitdlg-test-commit-template.txt")


def main() -> int:
    TEMPLATE.write_text("[M][0]: \n", encoding="utf-8")
    work = Path(tempfile.mkdtemp(prefix="gitdlg-template-"))
    msg = work / "COMMIT_EDITMSG"
    msg.write_text("[M][0]:\n\n# Please enter the commit message.\n#\n", encoding="utf-8")

    env = {
        "LANG": "en_US.UTF-8",
        "TERM": "xterm-256color",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "commit.template",
        "GIT_CONFIG_VALUE_0": str(TEMPLATE),
    }

    session = PtySession(editor_argv() + [str(msg)], env=env, rows=40, cols=120)
    session.start()
    try:
        time.sleep(0.9)
        session.send(b"fix from template test\x13")
        time.sleep(0.2)
        code = session.wait(8.0)
    finally:
        session.close()

    saved = msg.read_text(encoding="utf-8")
    ok = code == 0 and saved.startswith("[M][0]: fix from template test")
    print(f"exit={code} saved={saved!r} ok={ok}")
    if ok:
        print("PASS commit-template")
        return 0
    print("FAIL commit-template")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
