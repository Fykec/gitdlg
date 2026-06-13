#!/usr/bin/env python3
"""Unit tests for gitdlg.py (stdlib only)."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITDLG = ROOT / "gitdlg.py"


def load_gitdlg():
    spec = importlib.util.spec_from_file_location("gitdlg", GITDLG)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gitdlg"] = mod
    spec.loader.exec_module(mod)
    return mod


gitdlg = load_gitdlg()
parse_message = gitdlg.parse_message
format_message = gitdlg.format_message
find_message_path = gitdlg.find_message_path
read_message_file = gitdlg.read_message_file
write_message_file = gitdlg.write_message_file
restore_message_file = gitdlg.restore_message_file
detect_lang = gitdlg.detect_lang
Lang = gitdlg.Lang


class CommitTests(unittest.TestCase):
    def test_parse_git_template_with_comments(self) -> None:
        content = (
            "# Please enter the commit message for your changes.\n"
            "# On branch main\n"
            "\n"
            "feat: add gitdlg\n"
            "\n"
            "Body paragraph one.\n"
            "Body paragraph two.\n"
        )
        parsed = parse_message(content)
        self.assertEqual(parsed.subject, "feat: add gitdlg")
        self.assertEqual(parsed.body, "Body paragraph one.\nBody paragraph two.")

    def test_parse_chinese_subject(self) -> None:
        content = (
            "# Please enter the commit message.\n"
            "\n"
            "修复：中文主题展示\n"
            "\n"
            "正文第一段。\n"
        )
        parsed = parse_message(content)
        self.assertEqual(parsed.subject, "修复：中文主题展示")
        self.assertEqual(parsed.body, "正文第一段。")

    def test_subject_insert_chinese(self) -> None:
        subject = gitdlg.SubjectInput("")
        gitdlg.handle_subject_key(subject, "你")
        gitdlg.handle_subject_key(subject, "好")
        self.assertEqual(subject.text, "你好")
        self.assertEqual(subject.cursor, 2)

    def test_format_message_roundtrip(self) -> None:
        formatted = format_message("subject", "line one\nline two")
        self.assertEqual(formatted, "subject\n\nline one\nline two\n")
        parsed = parse_message(formatted)
        self.assertEqual(parsed.subject, "subject")
        self.assertEqual(parsed.body, "line one\nline two")

    def test_empty_message(self) -> None:
        parsed = parse_message("# comment only\n")
        self.assertEqual(parsed.subject, "")
        self.assertEqual(parsed.body, "")

    def test_find_message_path_skips_vim_args(self) -> None:
        args = ["gitdlg", "+3", "/tmp/COMMIT_EDITMSG"]
        self.assertEqual(find_message_path(args), "/tmp/COMMIT_EDITMSG")

    def test_write_and_read_message_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp:
            path = tmp.name
        try:
            write_message_file(path, "feat: test", "details here")
            parsed = read_message_file(path)
            self.assertEqual(parsed.subject, "feat: test")
            self.assertEqual(parsed.body, "details here")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_restore_message_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp:
            path = tmp.name
        raw = "# comment\n\nfeat: amend me\n\nbody line\n"
        try:
            restore_message_file(path, raw)
            restore_message_file(path, "edited")
            restore_message_file(path, raw)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), raw)
        finally:
            Path(path).unlink(missing_ok=True)


class LocaleTests(unittest.TestCase):
    def test_detect_chinese(self) -> None:
        self.assertEqual(detect_lang({"LANG": "zh_CN.UTF-8"}), Lang.ZH)

    def test_detect_english(self) -> None:
        self.assertEqual(detect_lang({"LANG": "en_US.UTF-8"}), Lang.EN)

    def test_detect_chinese_language_var(self) -> None:
        self.assertEqual(detect_lang({"LANGUAGE": "zh_CN:en"}), Lang.ZH)

    def test_default_english(self) -> None:
        self.assertEqual(detect_lang({}), Lang.EN)


if __name__ == "__main__":
    unittest.main()
