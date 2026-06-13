#!/usr/bin/env python3
"""Terminal.app compatibility tests (CJK + default-color theme)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from pty_harness import GITDLG, editor_argv, run_editor

SUBJECT = "修复：中文主题展示"
BODY = "正文第一段。\n第二段内容。"
WORK = Path(os.environ.get("TMPDIR", "/tmp")) / "gitdlg-terminal-app"
INDEX_COLOR_RE = re.compile(rb"\x1b\[(?:3[0-7]|9[0-7]|38;5;\d+)m")


def write_msg(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def apple_env(**extra: str) -> dict[str, str]:
    env = {
        "TERM_PROGRAM": "Apple_Terminal",
        "TERM_PROGRAM_VERSION": "455",
        "LANG": "zh_CN.UTF-8",
        "LC_ALL": "zh_CN.UTF-8",
    }
    env.update(extra)
    return env


def test_apple_terminal_cancel() -> None:
    msg = WORK / "COMMIT_EDITMSG"
    write_msg(msg, f"# Please enter the commit message.\n#\n\n{SUBJECT}\n\n{BODY}\n")
    code, _ = run_editor(msg, b"\x1b", env=apple_env(), start_delay=1.0)
    assert code == 0, f"expected exit 0, got {code}"


def test_apple_terminal_no_indexed_colors() -> None:
    msg = WORK / "COMMIT_EDITMSG"
    write_msg(msg, f"# Please enter the commit message.\n#\n\n{SUBJECT}\n\n{BODY}\n")
    _, out = run_editor(msg, b"\x1b", env=apple_env(), start_delay=1.0)
    assert INDEX_COLOR_RE.search(out) is None, (
        f"indexed colors in output: {INDEX_COLOR_RE.findall(out)[:5]}"
    )


def test_apple_terminal_save_chinese_roundtrip() -> None:
    msg = WORK / "COMMIT_EDITMSG.save"
    write_msg(msg, f"# comment\n\n{SUBJECT}\n\n{BODY}\n")
    code, _ = run_editor(msg, b"\x13", env=apple_env(), start_delay=1.0)
    assert code == 0, f"expected exit 0 on save, got {code}"
    saved = msg.read_text(encoding="utf-8")
    assert SUBJECT in saved
    assert "正文第一段。" in saved


def main() -> int:
    if not GITDLG.is_file():
        print(f"error: gitdlg.py not found: {GITDLG}", file=sys.stderr)
        return 1
    print(f"using: {' '.join(editor_argv())}")

    tests = [
        ("apple_cancel", test_apple_terminal_cancel),
        ("apple_no_indexed_colors", test_apple_terminal_no_indexed_colors),
        ("apple_save_chinese", test_apple_terminal_save_chinese_roundtrip),
    ]

    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 - integration script
            failed += 1
            print(f"FAIL {name}: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
