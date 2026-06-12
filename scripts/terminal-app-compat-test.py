#!/usr/bin/env python3
"""Terminal.app compatibility tests (CJK subject + default-color theme)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from pty_harness import BIN, run_editor

SUBJECT = "修复：中文主题展示"
BODY = "正文第一段。\n第二段内容。"
WORK = Path(os.environ.get("TMPDIR", "/tmp")) / "gitdlg-terminal-app"

# vaxis explicit-width *render* OSC (w>=2). Probe uses w=1 and is harmless.
EXPLICIT_WIDTH_RENDER = re.compile(rb"\x1b\]66;w=[2-9]\d*;")
# Indexed-color SGR we intentionally avoid for terminal theme parity.
INDEX_COLOR_RE = re.compile(rb"\x1b\[(?:3[0-7]|9[0-7]|38;5;\d+)m")


def write_msg(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def msg_with_chinese_subject() -> Path:
    path = WORK / "COMMIT_EDITMSG"
    write_msg(
        path,
        f"# Please enter the commit message.\n#\n\n{SUBJECT}\n\n{BODY}\n",
    )
    return path


def apple_env(**extra: str) -> dict[str, str]:
    env = {
        "TERM_PROGRAM": "Apple_Terminal",
        "TERM_PROGRAM_VERSION": "455",
        "LANG": "zh_CN.UTF-8",
        "LC_ALL": "zh_CN.UTF-8",
    }
    env.update(extra)
    return env


def test_apple_terminal_renders_chinese_subject() -> None:
    msg = msg_with_chinese_subject()
    code, out = run_editor(
        msg,
        b"\x1b",
        env=apple_env(),
        terminal_app_probe=True,
        use_vhs_record=False,
        start_delay=1.0,
    )
    assert code == 0, f"expected exit 0, got {code}"
    assert SUBJECT.encode("utf-8") in out, "Chinese subject not found in terminal output"
    assert EXPLICIT_WIDTH_RENDER.search(out) is None, (
        "explicit-width render OSC found; Terminal.app would hide CJK subject"
    )


def test_apple_terminal_no_indexed_colors() -> None:
    msg = msg_with_chinese_subject()
    _, out = run_editor(
        msg,
        b"\x1b",
        env=apple_env(),
        terminal_app_probe=True,
        use_vhs_record=False,
        start_delay=1.0,
    )
    assert INDEX_COLOR_RE.search(out) is None, (
        f"indexed colors in output: {INDEX_COLOR_RE.findall(out)[:5]}"
    )


def test_apple_terminal_chinese_ui() -> None:
    msg = msg_with_chinese_subject()
    _, out = run_editor(
        msg,
        b"\x1b",
        env=apple_env(),
        terminal_app_probe=True,
        use_vhs_record=False,
        start_delay=1.0,
    )
    text = out.decode("utf-8", "replace")
    assert "主题" in text or "确认" in text, "Chinese UI strings missing under zh_CN locale"


def test_apple_terminal_save_chinese_roundtrip() -> None:
    msg = WORK / "COMMIT_EDITMSG.save"
    write_msg(msg, f"# comment\n\n{SUBJECT}\n\n{BODY}\n")
    code, _ = run_editor(
        msg,
        b"\x13",  # Ctrl+S
        env=apple_env(),
        terminal_app_probe=True,
        use_vhs_record=False,
        start_delay=1.0,
    )
    assert code == 0, f"expected exit 0 on save, got {code}"
    saved = msg.read_text(encoding="utf-8")
    assert SUBJECT in saved
    assert "正文第一段。" in saved
    assert EXPLICIT_WIDTH_RENDER.search(saved.encode("utf-8")) is None


def test_regression_without_apple_compat() -> None:
    """Without Apple_Terminal workaround, false probe should emit explicit-width OSC."""
    msg = msg_with_chinese_subject()
    _, out = run_editor(
        msg,
        b"\x1b",
        env={"LANG": "en_US.UTF-8", "TERM": "xterm-256color"},
        terminal_app_probe=True,
        use_vhs_record=False,
        start_delay=1.0,
    )
    assert EXPLICIT_WIDTH_RENDER.search(out) is not None, (
        "expected explicit-width render OSC without Apple_Terminal compat (regression guard)"
    )


def main() -> int:
    if not BIN.is_file():
        print(f"error: build gitdlg first: {BIN}", file=sys.stderr)
        return 1

    tests = [
        ("apple_chinese_subject", test_apple_terminal_renders_chinese_subject),
        ("apple_no_indexed_colors", test_apple_terminal_no_indexed_colors),
        ("apple_chinese_ui", test_apple_terminal_chinese_ui),
        ("apple_save_chinese", test_apple_terminal_save_chinese_roundtrip),
        ("regression_no_compat", test_regression_without_apple_compat),
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
