#!/usr/bin/env python3
"""PTY smoke tests for gitdlg (Ghostty-like TTY relay; works in CI)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from pty_harness import BIN, run_editor

ROOT = Path(__file__).resolve().parents[1]

# Indexed-color SGR we no longer want (30-37, 90-97, 38;5;n).
INDEX_COLOR_RE = re.compile(r"\x1b\[(?:3[0-7]|9[0-7]|38;5;\d+)m")


def write_msg(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_render() -> None:
    work = Path(os.environ.get("TMPDIR", "/tmp")) / "gitdlg-smoke"
    msg = work / "COMMIT_EDITMSG"
    write_msg(
        msg,
        "# Please enter the commit message for your changes.\n#\n\n",
    )

    code, out = run_editor(msg, b"\x1b", start_delay=1.0)
    text = out.decode("utf-8", "replace")

    assert code == 0, f"expected exit 0 after cancel, got {code}"
    assert "┌" in text or "─" in text, "dialog frame not rendered"
    assert "Ctrl+S" in text or "确认" in text, "footer hint missing"
    assert INDEX_COLOR_RE.search(text) is None, (
        f"indexed colors found: {INDEX_COLOR_RE.findall(text)[:5]}"
    )


def test_cancel_restore_normal() -> None:
    work = Path(os.environ.get("TMPDIR", "/tmp")) / "gitdlg-smoke"
    msg = work / "COMMIT_EDITMSG.normal"
    original = "# Please enter the commit message for your changes.\n#\n\n"
    write_msg(msg, original)

    code, _ = run_editor(msg, b"\x1b")
    assert code == 0, f"expected exit 0 on cancel, got {code}"
    assert msg.read_text(encoding="utf-8") == original


def test_cancel_restore_amend() -> None:
    work = Path(os.environ.get("TMPDIR", "/tmp")) / "gitdlg-smoke"
    msg = work / "COMMIT_EDITMSG.amend"
    original = "feat: seed subject\n\nBody line one.\n\n# Please enter the commit message.\n"
    write_msg(msg, original)

    code, _ = run_editor(
        msg,
        b"\x1b",
        env={"GIT_REFLOG_ACTION": "commit (amend)"},
    )
    assert code == 0, f"expected exit 0 on amend cancel, got {code}"
    assert msg.read_text(encoding="utf-8") == original


def test_save_ctrl_s() -> None:
    work = Path(os.environ.get("TMPDIR", "/tmp")) / "gitdlg-smoke"
    msg = work / "COMMIT_EDITMSG.save"
    write_msg(
        msg,
        "# comment\n\nfeat: from template\n\nDetails here.\n",
    )

    code, _ = run_editor(msg, b"\x13", start_delay=1.0)
    assert code == 0, f"expected exit 0 on save, got {code}"
    saved = msg.read_text(encoding="utf-8")
    assert "feat: from template" in saved
    assert "Details here." in saved


def main() -> int:
    if not BIN.is_file():
        print(f"error: build gitdlg first: {BIN}", file=sys.stderr)
        return 1

    tests = [
        ("render", test_render),
        ("cancel_normal", test_cancel_restore_normal),
        ("cancel_amend", test_cancel_restore_amend),
        ("save", test_save_ctrl_s),
    ]

    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 - smoke test
            failed += 1
            print(f"FAIL {name}: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
