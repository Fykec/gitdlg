#!/usr/bin/env python3
"""gitdlg — dialog-style git commit message editor (Python 3, stdlib only).

Single-file distribution: copy gitdlg.py anywhere and point Git at it.
"""

from __future__ import annotations

import curses
import locale
import os
import sys
import termios
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto
from math import sqrt
from pathlib import Path
# --- commit message I/O ---




@dataclass(frozen=True)
class Parsed:
    subject: str
    body: str


def parse_message(content: str) -> Parsed:
    """Split a git commit message into subject and body; skip ``#`` comment lines."""
    lines: list[str] = []
    for raw_line in content.split("\n"):
        line = raw_line.rstrip("\r")
        trimmed = line.strip()
        if not trimmed:
            continue
        if trimmed.startswith("#"):
            continue
        lines.append(line.lstrip())

    if not lines:
        return Parsed("", "")

    subject = lines[0]
    if len(lines) == 1:
        return Parsed(subject, "")

    return Parsed(subject, "\n".join(lines[1:]))


def format_message(subject: str, body: str) -> str:
    """Format subject/body the way git expects in COMMIT_EDITMSG."""
    trimmed_subject = subject.strip("\r\n").lstrip()
    trimmed_body = body.strip()

    if not trimmed_body:
        if not trimmed_subject:
            return ""
        return trimmed_subject + "\n"

    out = trimmed_subject + "\n\n" + trimmed_body
    if not trimmed_body.endswith("\n"):
        out += "\n"
    return out


def read_message_file(path: str | Path) -> Parsed:
    content = Path(path).read_text(encoding="utf-8")
    return parse_message(content)


def read_message_file_raw(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_message_file(path: str | Path, subject: str, body: str) -> None:
    Path(path).write_text(format_message(subject, body), encoding="utf-8")


def restore_message_file(path: str | Path, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def find_message_path(args: list[str]) -> str | None:
    """Git may prepend ``+line`` arguments before the file path."""
    for arg in reversed(args[1:]):
        if not arg:
            continue
        if arg[0] in "-+":
            continue
        return arg
    return None

# --- locale ---




class Lang(Enum):
    EN = "en"
    ZH = "zh"


@dataclass(frozen=True)
class UiStrings:
    subject_placeholder: str
    body_placeholder: str
    confirm_button: str
    cancel_button: str
    footer_hint: str
    terminal_too_small: str


@dataclass(frozen=True)
class Messages:
    ui: UiStrings
    usage: str
    no_tty: str


_MESSAGES: dict[Lang, Messages] = {
    Lang.ZH: Messages(
        ui=UiStrings(
            subject_placeholder="主题",
            body_placeholder="正文",
            confirm_button="确认(Ctrl+S)",
            cancel_button="取消(Esc)",
            footer_hint="Ctrl+S 确认 | Esc 取消",
            terminal_too_small="终端窗口过小，请放大后继续编辑 (Esc 取消)",
        ),
        usage=(
            "gitdlg - 图形化 git commit 消息编辑器\n"
            "\n"
            "用法:\n"
            "  gitdlg <COMMIT_EDITMSG 路径>\n"
            "  GIT_EDITOR=gitdlg git commit\n"
            "\n"
            "快捷键:\n"
            "  Tab / Shift+Tab  切换 主题 / 正文 / 确认 / 取消\n"
            "  Ctrl+S           确认\n"
            "  Enter            在确认按钮上确认\n"
            "  Esc              取消\n"
        ),
        no_tty=(
            "gitdlg: 需要交互式终端 (TTY)。\n"
            "\n"
            "请在终端里执行 git commit。\n"
        ),
    ),
    Lang.EN: Messages(
        ui=UiStrings(
            subject_placeholder="Subject",
            body_placeholder="Body",
            confirm_button="Confirm(Ctrl+S)",
            cancel_button="Cancel(Esc)",
            footer_hint="Ctrl+S confirm | Esc cancel",
            terminal_too_small="Terminal too small; enlarge to edit (Esc to cancel)",
        ),
        usage=(
            "gitdlg - dialog-style git commit message editor\n"
            "\n"
            "Usage:\n"
            "  gitdlg <path-to-COMMIT_EDITMSG>\n"
            "  GIT_EDITOR=gitdlg git commit\n"
            "\n"
            "Keys:\n"
            "  Tab / Shift+Tab    Cycle Subject, Body, Confirm, Cancel\n"
            "  Ctrl+S             Confirm\n"
            "  Enter on Confirm   Confirm\n"
            "  Esc                Cancel\n"
        ),
        no_tty=(
            "gitdlg: an interactive terminal (TTY) is required.\n"
            "\n"
            "Please run git commit from a terminal.\n"
        ),
    ),
}


def _is_chinese_locale(value: str) -> bool:
    segment = value
    while segment:
        for sep in (".", "@", ":", ";"):
            if sep in segment:
                part, _, segment = segment.partition(sep)
                break
        else:
            part, segment = segment, ""
        if len(part) >= 2 and part[0] == "z" and part[1] == "h":
            return True
        if len(part) >= 3 and part[:3].lower() == "yue":
            return True
    return False


def detect_lang(environ: Mapping[str, str] | None = None) -> Lang:
    """Resolve UI language from OS locale env vars. Defaults to English."""
    env = environ if environ is not None else os.environ
    for key in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = env.get(key)
        if not value or value in ("C", "POSIX"):
            continue
        if _is_chinese_locale(value):
            return Lang.ZH
        return Lang.EN
    return Lang.EN


def messages(lang: Lang | None = None) -> Messages:
    if lang is None:
        lang = detect_lang()
    return _MESSAGES[lang]

# --- terminal editor ---




class NoTty(Exception):
    """Raised when no interactive terminal is available."""


class Result(Enum):
    SAVED = auto()
    CANCELLED = auto()


class Focus(Enum):
    SUBJECT = auto()
    BODY = auto()
    CONFIRM = auto()
    CANCEL = auto()

    def is_button(self) -> bool:
        return self in (Focus.CONFIRM, Focus.CANCEL)


class LayoutMode(Enum):
    FULL = auto()
    NO_BODY = auto()
    NO_BUTTONS = auto()
    TOO_SMALL = auto()


@dataclass(frozen=True)
class LayoutDims:
    subject_top: int = 1
    subject_h: int = 3
    field_x: int = 2
    field_pad_right: int = 2
    button_w: int = 22
    button_h: int = 3
    button_gap: int = 4

    def buttons_total(self) -> int:
        return self.button_w * 2 + self.button_gap

    def body_top(self) -> int:
        return self.subject_top + self.subject_h + 1

    def min_panel_w_for_subject(self) -> int:
        return self.field_x + 1 + self.field_pad_right

    def min_panel_h_for_subject(self) -> int:
        return self.subject_top + self.subject_h + 1

    def buttons_fit_height(self, ph: int, btn_row: int) -> bool:
        return btn_row + self.button_h <= ph


LAYOUT_DIMS = LayoutDims()


@dataclass(frozen=True)
class DialogLayout:
    max_w: int = 80
    max_h: int = 0

    def __post_init__(self) -> None:
        if self.max_h == 0:
            object.__setattr__(self, "max_h", golden_max_height(self.max_w))

    def frame_rect(self, term_w: int, term_h: int) -> tuple[int, int, int, int]:
        w = min(term_w, self.max_w)
        h = min(term_h, self.max_h)
        x = (term_w - w) // 2 if term_w > w else 0
        y = (term_h - h) // 2 if term_h > h else 0
        return x, y, max(1, w), max(1, h)


def golden_max_height(max_w: int) -> int:
    phi = (1.0 + sqrt(5.0)) / 2.0
    h = max_w / (phi * phi + 1.0)
    return max(13, round(h))


DIALOG_LAYOUT = DialogLayout()


@dataclass
class ComputedLayout:
    mode: LayoutMode
    field_w: int
    body_top: int
    body_h: int
    btn_row: int
    buttons_x: int
    frame_x: int
    frame_y: int
    frame_w: int
    frame_h: int

    @staticmethod
    def too_small() -> ComputedLayout:
        return ComputedLayout(
            LayoutMode.TOO_SMALL,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )

    @classmethod
    def compute(cls, term_w: int, term_h: int) -> ComputedLayout:
        if term_w <= 0 or term_h <= 0:
            return cls.too_small()

        frame_x, frame_y, frame_w, frame_h = DIALOG_LAYOUT.frame_rect(term_w, term_h)
        panel_x = frame_x + 1
        panel_y = frame_y + 1
        pw = max(1, frame_w - 2)
        ph = max(1, frame_h - 2)
        field_w = max(1, pw - LAYOUT_DIMS.field_x - LAYOUT_DIMS.field_pad_right)

        if pw < LAYOUT_DIMS.min_panel_w_for_subject() or ph < LAYOUT_DIMS.min_panel_h_for_subject():
            return cls.too_small()

        buttons_wide = pw >= LAYOUT_DIMS.buttons_total()
        full_btn_row = ph - 4 if ph > 4 else 0
        compact_btn_row = LAYOUT_DIMS.body_top()
        full_body_h = full_btn_row - LAYOUT_DIMS.body_top() - 1 if full_btn_row > LAYOUT_DIMS.body_top() + 1 else 0

        show_body = buttons_wide and full_body_h >= 1 and LAYOUT_DIMS.buttons_fit_height(ph, full_btn_row)
        show_buttons = (
            True
            if show_body
            else buttons_wide and LAYOUT_DIMS.buttons_fit_height(ph, compact_btn_row)
        )

        if show_body:
            mode = LayoutMode.FULL
        elif show_buttons:
            mode = LayoutMode.NO_BODY
        else:
            mode = LayoutMode.NO_BUTTONS

        btn_row = full_btn_row if show_body else (compact_btn_row if show_buttons else 0)
        body_h = full_body_h if show_body else 0
        buttons_x = (pw - LAYOUT_DIMS.buttons_total()) // 2 if pw > LAYOUT_DIMS.buttons_total() else 0

        return cls(
            mode,
            field_w,
            LAYOUT_DIMS.body_top(),
            body_h,
            btn_row,
            buttons_x,
            frame_x,
            frame_y,
            frame_w,
            frame_h,
        )

    def shows_body(self) -> bool:
        return self.mode == LayoutMode.FULL

    def shows_buttons(self) -> bool:
        return self.mode in (LayoutMode.FULL, LayoutMode.NO_BODY)

    def focus_cycle(self, focus: Focus, reverse: bool) -> Focus:
        order = {
            LayoutMode.FULL: [Focus.SUBJECT, Focus.BODY, Focus.CONFIRM, Focus.CANCEL],
            LayoutMode.NO_BODY: [Focus.SUBJECT, Focus.CONFIRM, Focus.CANCEL],
            LayoutMode.NO_BUTTONS: [Focus.SUBJECT],
            LayoutMode.TOO_SMALL: [Focus.SUBJECT],
        }[self.mode]
        try:
            idx = order.index(focus)
        except ValueError:
            return order[0]
        if reverse:
            return order[(idx - 1) % len(order)]
        return order[(idx + 1) % len(order)]

    def clamp_focus(self, focus: Focus) -> Focus:
        if self.mode == LayoutMode.FULL:
            return focus
        if self.mode == LayoutMode.NO_BODY:
            return Focus.SUBJECT if focus == Focus.BODY else focus
        return Focus.SUBJECT

    def move_focus_vertical(self, focus: Focus, up: bool) -> Focus:
        if self.mode == LayoutMode.FULL:
            if up:
                return {
                    Focus.SUBJECT: Focus.CANCEL,
                    Focus.BODY: Focus.SUBJECT,
                    Focus.CONFIRM: Focus.BODY,
                    Focus.CANCEL: Focus.BODY,
                }[focus]
            return {
                Focus.SUBJECT: Focus.BODY,
                Focus.BODY: Focus.CONFIRM,
                Focus.CONFIRM: Focus.SUBJECT,
                Focus.CANCEL: Focus.SUBJECT,
            }[focus]
        if self.mode == LayoutMode.NO_BODY:
            if up:
                return {
                    Focus.SUBJECT: Focus.CANCEL,
                    Focus.CONFIRM: Focus.SUBJECT,
                    Focus.CANCEL: Focus.SUBJECT,
                }.get(focus, focus)
            return {
                Focus.SUBJECT: Focus.CONFIRM,
                Focus.CONFIRM: Focus.SUBJECT,
                Focus.CANCEL: Focus.SUBJECT,
            }.get(focus, focus)
        return focus

    def enter_from_subject(self) -> Focus:
        return {
            LayoutMode.FULL: Focus.BODY,
            LayoutMode.NO_BODY: Focus.CONFIRM,
            LayoutMode.NO_BUTTONS: Focus.SUBJECT,
            LayoutMode.TOO_SMALL: Focus.SUBJECT,
        }[self.mode]


class SubjectInput:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.cursor = len(text)

    def insert(self, s: str) -> None:
        self.text = self.text[: self.cursor] + s + self.text[self.cursor :]
        self.cursor += len(s)

    def backspace(self) -> None:
        if self.cursor == 0:
            return
        prev = prev_codepoint_start(self.text, self.cursor)
        self.text = self.text[:prev] + self.text[self.cursor :]
        self.cursor = prev

    def delete(self) -> None:
        if self.cursor >= len(self.text):
            return
        nxt = next_codepoint_end(self.text, self.cursor)
        self.text = self.text[: self.cursor] + self.text[nxt:]

    def move_left(self) -> None:
        if self.cursor > 0:
            self.cursor = prev_codepoint_start(self.text, self.cursor)

    def move_right(self) -> None:
        if self.cursor < len(self.text):
            self.cursor = next_codepoint_end(self.text, self.cursor)

    def move_home(self) -> None:
        self.cursor = 0

    def move_end(self) -> None:
        self.cursor = len(self.text)

    def is_empty(self) -> bool:
        return len(self.text) == 0


class BodyInput:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.cursor = len(text)

    def insert(self, s: str) -> None:
        if s == "\t":
            return
        self.text = self.text[: self.cursor] + s + self.text[self.cursor :]
        self.cursor += len(s)

    def backspace(self) -> None:
        if self.cursor == 0:
            return
        prev = prev_codepoint_start(self.text, self.cursor)
        self.text = self.text[:prev] + self.text[self.cursor :]
        self.cursor = prev

    def delete(self) -> None:
        if self.cursor >= len(self.text):
            return
        nxt = next_codepoint_end(self.text, self.cursor)
        self.text = self.text[: self.cursor] + self.text[nxt:]

    def move_left(self) -> None:
        if self.cursor > 0:
            self.cursor = prev_codepoint_start(self.text, self.cursor)

    def move_right(self) -> None:
        if self.cursor < len(self.text):
            self.cursor = next_codepoint_end(self.text, self.cursor)

    def move_up(self) -> None:
        self.cursor = move_vertical(self.text, self.cursor, -1)

    def move_down(self) -> None:
        self.cursor = move_vertical(self.text, self.cursor, 1)

    def move_home(self) -> None:
        self.cursor = line_start(self.text, self.cursor)

    def move_end(self) -> None:
        self.cursor = line_end(self.text, self.cursor)

    def insert_newline(self) -> None:
        self.text = self.text[: self.cursor] + "\n" + self.text[self.cursor :]
        self.cursor += 1

    def is_empty(self) -> bool:
        return len(self.text) == 0


def prev_codepoint_start(text: str, pos: int) -> int:
    if pos <= 0:
        return 0
    i = pos - 1
    while i > 0 and (ord(text[i]) & 0xC0) == 0x80:
        i -= 1
    return i


def next_codepoint_end(text: str, pos: int) -> int:
    if pos >= len(text):
        return len(text)
    i = pos + 1
    while i < len(text) and (ord(text[i]) & 0xC0) == 0x80:
        i += 1
    return i


def line_start(text: str, pos: int) -> int:
    i = pos
    while i > 0 and text[i - 1] != "\n":
        i -= 1
    return i


def line_end(text: str, pos: int) -> int:
    i = pos
    while i < len(text) and text[i] != "\n":
        i += 1
    return i


def move_vertical(text: str, pos: int, delta: int) -> int:
    line_s = line_start(text, pos)
    col = pos - line_s
    lines = text.split("\n")
    line_idx = text[:pos].count("\n")
    target = max(0, min(len(lines) - 1, line_idx + delta))
    target_line = lines[target]
    new_col = min(col, len(target_line))
    return sum(len(lines[i]) + 1 for i in range(target)) + new_col


def attach_stdio_to_tty() -> None:
    if sys.stdin.isatty():
        disable_terminal_flow_control(sys.stdin.fileno())
        return
    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR)
    except OSError as exc:
        raise NoTty() from exc
    os.dup2(tty_fd, sys.stdin.fileno())
    os.dup2(tty_fd, sys.stdout.fileno())
    os.dup2(tty_fd, sys.stderr.fileno())
    if tty_fd > 2:
        os.close(tty_fd)
    disable_terminal_flow_control(sys.stdin.fileno())


def disable_terminal_flow_control(fd: int) -> None:
    try:
        attr = termios.tcgetattr(fd)
        attr[0] &= ~(termios.IXON | termios.IXOFF)
        termios.tcsetattr(fd, termios.TCSANOW, attr)
    except termios.error:
        pass


def setup_locale() -> None:
    os.environ.setdefault("LANG", "en_US.UTF-8")
    os.environ.setdefault("LC_CTYPE", "en_US.UTF-8")
    for name in ("", "en_US.UTF-8", "zh_CN.UTF-8", "C.UTF-8"):
        try:
            locale.setlocale(locale.LC_ALL, name)
            return
        except locale.Error:
            continue


Key = int | str


def read_key(win: curses.window) -> Key | None:
    try:
        return win.get_wch()
    except curses.error:
        return None


def key_code(ch: Key) -> int | None:
    if isinstance(ch, int):
        return ch
    if len(ch) == 1:
        return ord(ch)
    return None


def is_mouse_event(ch: Key) -> bool:
    return isinstance(ch, int) and ch == getattr(curses, "KEY_MOUSE", -1)


def is_mouse_trailer(ch: Key) -> bool:
    code = key_code(ch)
    return code is not None and 32 <= code <= 255


def is_enter(ch: Key) -> bool:
    if isinstance(ch, int):
        return ch in (curses.KEY_ENTER, 10, 13)
    return ch in ("\n", "\r")


def is_backspace(ch: Key) -> bool:
    if isinstance(ch, int):
        return ch in (curses.KEY_BACKSPACE, 127, 8)
    return ch in ("\x7f", "\b")


def safe_curs_set(visibility: int) -> None:
    try:
        curses.curs_set(visibility)
    except curses.error:
        pass


def terminal_size(win: curses.window) -> tuple[int, int]:
    """Return (columns, rows) for layout."""
    rows, cols = win.getmaxyx()
    return cols, rows


def run_editor(path: str, original_raw: str, parsed: Parsed, ui_msgs: Messages | None = None) -> Result:
    ui_msgs = ui_msgs or messages(detect_lang())
    ui = ui_msgs.ui

    def _main(stdscr: curses.window) -> Result:
        safe_curs_set(1)
        if curses.has_colors():
            curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        stdscr.keypad(True)
        if hasattr(curses, "set_escdelay"):
            curses.set_escdelay(25)

        subject = SubjectInput(parsed.subject)
        body = BodyInput(parsed.body)
        focus = Focus.SUBJECT
        mouse_trailer = 0

        while True:
            layout = ComputedLayout.compute(*terminal_size(stdscr))
            draw(stdscr, layout, focus, ui, subject, body)
            stdscr.refresh()

            try:
                ch = read_key(stdscr)
            except curses.error:
                continue
            if ch is None:
                continue
            if is_mouse_event(ch):
                mouse_trailer = 2
                continue
            if mouse_trailer and is_mouse_trailer(ch):
                mouse_trailer -= 1
                continue
            mouse_trailer = 0

            if should_save(ch):
                write_message_file(path, subject.text, body.text)
                return Result.SAVED
            if should_cancel(ch):
                restore_message_file(path, original_raw)
                return Result.CANCELLED

            tab_dir = tab_direction(ch)
            if tab_dir is not None:
                focus = layout.focus_cycle(focus, tab_dir)
            elif focus.is_button():
                if not layout.shows_buttons():
                    focus = Focus.SUBJECT
                elif (arrow := arrow_direction(ch)) is not None:
                    if arrow == "left" and focus == Focus.CANCEL:
                        focus = Focus.CONFIRM
                    elif arrow == "right" and focus == Focus.CONFIRM:
                        focus = Focus.CANCEL
                    elif arrow in ("up", "down"):
                        focus = layout.move_focus_vertical(focus, arrow == "up")
                elif is_enter(ch):
                    if focus == Focus.CONFIRM:
                        write_message_file(path, subject.text, body.text)
                        return Result.SAVED
                    restore_message_file(path, original_raw)
                    return Result.CANCELLED
            elif focus == Focus.SUBJECT:
                if is_enter(ch):
                    focus = layout.enter_from_subject()
                else:
                    handle_subject_key(subject, ch)
            elif focus == Focus.BODY:
                if layout.shows_body():
                    handle_body_key(body, ch)
                else:
                    focus = Focus.SUBJECT

            focus = layout.clamp_focus(focus)

    return curses.wrapper(_main)


def should_save(ch: Key) -> bool:
    if isinstance(ch, str):
        return ch == "\x13"
    return ch in (19, ord("S") & 0x1F, ord("s") & 0x1F)


def should_cancel(ch: Key) -> bool:
    if isinstance(ch, str):
        return ch == "\x1b"
    return ch == 27


def tab_direction(ch: Key) -> bool | None:
    if ch == curses.KEY_BTAB:
        return True
    if key_code(ch) == 9:
        return False
    return None


def arrow_direction(ch: Key) -> str | None:
    if not isinstance(ch, int):
        return None
    mapping = {
        curses.KEY_UP: "up",
        curses.KEY_DOWN: "down",
        curses.KEY_LEFT: "left",
        curses.KEY_RIGHT: "right",
    }
    return mapping.get(ch)


def handle_subject_key(subject: SubjectInput, ch: Key) -> None:
    if is_backspace(ch):
        subject.backspace()
    elif isinstance(ch, int) and ch == curses.KEY_DC:
        subject.delete()
    elif isinstance(ch, int) and ch == curses.KEY_LEFT:
        subject.move_left()
    elif isinstance(ch, int) and ch == curses.KEY_RIGHT:
        subject.move_right()
    elif isinstance(ch, int) and ch in (curses.KEY_HOME,):
        subject.move_home()
    elif isinstance(ch, int) and ch in (curses.KEY_END,):
        subject.move_end()
    elif key_code(ch) == (ord("A") & 0x1F):
        subject.move_home()
    elif key_code(ch) == (ord("E") & 0x1F):
        subject.move_end()
    elif key_code(ch) == (ord("B") & 0x1F):
        subject.move_left()
    elif key_code(ch) == (ord("F") & 0x1F):
        subject.move_right()
    elif isinstance(ch, str):
        if len(ch) == 1 and ord(ch) < 32:
            return
        subject.insert(ch)


def handle_body_key(body: BodyInput, ch: Key) -> None:
    if is_backspace(ch):
        body.backspace()
    elif isinstance(ch, int) and ch == curses.KEY_DC:
        body.delete()
    elif isinstance(ch, int) and ch == curses.KEY_LEFT:
        body.move_left()
    elif isinstance(ch, int) and ch == curses.KEY_RIGHT:
        body.move_right()
    elif isinstance(ch, int) and ch == curses.KEY_UP:
        body.move_up()
    elif isinstance(ch, int) and ch == curses.KEY_DOWN:
        body.move_down()
    elif isinstance(ch, int) and ch in (curses.KEY_HOME,):
        body.move_home()
    elif isinstance(ch, int) and ch in (curses.KEY_END,):
        body.move_end()
    elif key_code(ch) == (ord("A") & 0x1F):
        body.move_home()
    elif key_code(ch) == (ord("E") & 0x1F):
        body.move_end()
    elif key_code(ch) == (ord("B") & 0x1F):
        body.move_left()
    elif key_code(ch) == (ord("F") & 0x1F):
        body.move_right()
    elif is_enter(ch):
        body.insert_newline()
    elif isinstance(ch, str):
        if ch == "\t":
            return
        if len(ch) == 1 and ord(ch) < 32:
            return
        body.insert(ch)


def draw(
    stdscr: curses.window,
    layout: ComputedLayout,
    focus: Focus,
    ui: UiStrings,
    subject: SubjectInput,
    body: BodyInput,
) -> None:
    stdscr.erase()
    if layout.mode == LayoutMode.TOO_SMALL:
        draw_centered(stdscr, ui.terminal_too_small, curses.A_DIM)
        return

    panel = layout
    draw_box(
        stdscr,
        panel.frame_y,
        panel.frame_x,
        panel.frame_h,
        panel.frame_w,
        curses.A_BOLD,
    )

    ph = panel.frame_h - 2
    py = panel.frame_y + 1
    px = panel.frame_x + 1

    draw_field_box(
        stdscr,
        py + LAYOUT_DIMS.subject_top,
        px + LAYOUT_DIMS.field_x,
        LAYOUT_DIMS.subject_h,
        panel.field_w,
        curses.A_BOLD if focus == Focus.SUBJECT else curses.A_NORMAL,
    )
    draw_subject(stdscr, py, px, panel, focus, ui, subject)

    if panel.shows_body():
        draw_field_box(
            stdscr,
            py + panel.body_top,
            px + LAYOUT_DIMS.field_x,
            panel.body_h,
            panel.field_w,
            curses.A_BOLD if focus == Focus.BODY else curses.A_NORMAL,
        )
        draw_body(stdscr, py, px, panel, focus, ui, body)

    if panel.shows_buttons():
        draw_button(
            stdscr,
            py + panel.btn_row,
            px + panel.buttons_x,
            LAYOUT_DIMS.button_w,
            LAYOUT_DIMS.button_h,
            ui.confirm_button,
            focus == Focus.CONFIRM,
        )
        draw_button(
            stdscr,
            py + panel.btn_row,
            px + panel.buttons_x + LAYOUT_DIMS.button_w + LAYOUT_DIMS.button_gap,
            LAYOUT_DIMS.button_w,
            LAYOUT_DIMS.button_h,
            ui.cancel_button,
            focus == Focus.CANCEL,
        )

    if ph > 0:
        safe_addstr(stdscr, py + ph - 1, px + 2, ui.footer_hint, curses.A_DIM)

    place_cursor(stdscr, layout, focus, subject, body, py, px)


def draw_box(win: curses.window, y: int, x: int, h: int, w: int, attr: int) -> None:
    if h < 2 or w < 2:
        return
    tl, tr, bl, br, hz, vt = box_acs()
    safe_addch(win, y, x, tl, attr)
    safe_addch(win, y, x + w - 1, tr, attr)
    safe_addch(win, y + h - 1, x, bl, attr)
    safe_addch(win, y + h - 1, x + w - 1, br, attr)
    for col in range(x + 1, x + w - 1):
        safe_addch(win, y, col, hz, attr)
        safe_addch(win, y + h - 1, col, hz, attr)
    for row in range(y + 1, y + h - 1):
        safe_addch(win, row, x, vt, attr)
        safe_addch(win, row, x + w - 1, vt, attr)
        clear_region(win, row, x + 1, w - 2, attr)


def draw_field_box(win: curses.window, y: int, x: int, h: int, w: int, attr: int) -> None:
    draw_box(win, y, x, h, w, attr)


def draw_button(win: curses.window, y: int, x: int, w: int, h: int, label: str, focused: bool) -> None:
    attr = curses.A_REVERSE if focused else curses.A_NORMAL
    draw_box(win, y, x, h, w, attr)
    text_y = y + (h - 1) // 2
    text_x = x + max(1, (w - display_width(label)) // 2)
    safe_addstr(win, text_y, text_x, label, attr)


def draw_subject(
    stdscr: curses.window,
    py: int,
    px: int,
    layout: ComputedLayout,
    focus: Focus,
    ui: UiStrings,
    subject: SubjectInput,
) -> None:
    inner_y = py + LAYOUT_DIMS.subject_top + 1
    inner_x = px + LAYOUT_DIMS.field_x + 1
    inner_h = LAYOUT_DIMS.subject_h - 2
    inner_w = layout.field_w - 2
    if inner_h <= 0 or inner_w <= 0:
        return

    row = inner_y + (inner_h - 1) // 2
    offset = max(0, display_width(subject.text[: subject.cursor]) - inner_w + 1)
    visible, _ = clip_text_with_offset(subject.text, inner_w, offset)
    clear_region(stdscr, row, inner_x, inner_w, curses.A_NORMAL)
    if focus != Focus.SUBJECT and subject.is_empty():
        safe_addstr(stdscr, row, inner_x, ui.subject_placeholder, curses.A_DIM)
    else:
        safe_addstr(stdscr, row, inner_x, visible)


def place_cursor(
    stdscr: curses.window,
    layout: ComputedLayout,
    focus: Focus,
    subject: SubjectInput,
    body: BodyInput,
    py: int,
    px: int,
) -> None:
    if focus == Focus.SUBJECT:
        inner_y = py + LAYOUT_DIMS.subject_top + 1
        inner_x = px + LAYOUT_DIMS.field_x + 1
        inner_h = LAYOUT_DIMS.subject_h - 2
        inner_w = layout.field_w - 2
        if inner_h <= 0 or inner_w <= 0:
            return
        row = inner_y + (inner_h - 1) // 2
        offset = max(0, display_width(subject.text[: subject.cursor]) - inner_w + 1)
        col = inner_x + min(max(0, display_width(subject.text[: subject.cursor]) - offset), inner_w - 1)
        safe_curs_set(1)
        safe_move(stdscr, row, col)
        return

    if focus == Focus.BODY and layout.shows_body():
        inner_y = py + layout.body_top + 1
        inner_x = px + LAYOUT_DIMS.field_x + 1
        inner_h = layout.body_h - 2
        inner_w = layout.field_w - 2
        if inner_h <= 0 or inner_w <= 0:
            return
        if body.is_empty():
            safe_curs_set(1)
            safe_move(stdscr, inner_y, inner_x)
            return
        lines = body.text.split("\n")
        cursor_row = body.text[: body.cursor].count("\n")
        line_start = sum(len(lines[i]) + 1 for i in range(cursor_row))
        cursor_col = display_width(body.text[line_start:body.cursor])
        scroll = max(0, cursor_row - inner_h + 1)
        y = inner_y + (cursor_row - scroll)
        if 0 <= cursor_row - scroll < inner_h:
            safe_curs_set(1)
            safe_move(stdscr, y, inner_x + min(max(0, cursor_col), inner_w - 1))
        return

    if focus.is_button():
        safe_curs_set(0)


def draw_body(
    stdscr: curses.window,
    py: int,
    px: int,
    layout: ComputedLayout,
    focus: Focus,
    ui: UiStrings,
    body: BodyInput,
) -> None:
    inner_y = py + layout.body_top + 1
    inner_x = px + LAYOUT_DIMS.field_x + 1
    inner_h = layout.body_h - 2
    inner_w = layout.field_w - 2
    if inner_h <= 0 or inner_w <= 0:
        return

    if body.is_empty():
        if focus != Focus.BODY:
            safe_addstr(stdscr, inner_y, inner_x, ui.body_placeholder, curses.A_DIM)
        return

    lines = body.text.split("\n")
    cursor_row = body.text[: body.cursor].count("\n")
    scroll = max(0, cursor_row - inner_h + 1)
    for row_idx in range(inner_h):
        line_idx = scroll + row_idx
        y = inner_y + row_idx
        clear_region(stdscr, y, inner_x, inner_w, curses.A_NORMAL)
        if line_idx >= len(lines):
            continue
        line = clip_text(lines[line_idx], inner_w)
        safe_addstr(stdscr, y, inner_x, line)


def draw_centered(stdscr: curses.window, text: str, attr: int) -> None:
    rows, cols = stdscr.getmaxyx()
    y = max(0, rows // 2)
    x = max(0, (cols - display_width(text)) // 2)
    safe_addstr(stdscr, y, x, text, attr)


def display_width(text: str) -> int:
    """Terminal display width (wide chars count as 2)."""
    width = 0
    for ch in text:
        if ord(ch) < 0x20:
            continue
        ea = unicodedata.east_asian_width(ch)
        width += 2 if ea in ("W", "F") else 1
    return width


def clip_text(text: str, max_w: int) -> str:
    clipped, _ = clip_text_with_offset(text, max_w, 0)
    return clipped


def clip_text_with_offset(text: str, max_w: int, offset_w: int) -> tuple[str, int]:
    if max_w <= 0:
        return "", 0
    skipped = 0
    start = 0
    for i, ch in enumerate(text):
        w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if skipped + w <= offset_w:
            skipped += w
            start = i + 1
            continue
        break

    out: list[str] = []
    used = 0
    for ch in text[start:]:
        w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + w > max_w:
            break
        out.append(ch)
        used += w
    return "".join(out), start


def safe_move(win: curses.window, y: int, x: int) -> None:
    rows, cols = win.getmaxyx()
    if rows <= 0 or cols <= 0:
        return
    y = max(0, min(rows - 1, y))
    x = max(0, min(cols - 1, x))
    try:
        win.move(y, x)
    except curses.error:
        pass


def clear_region(win: curses.window, y: int, x: int, w: int, attr: int = curses.A_NORMAL) -> None:
    rows, cols = win.getmaxyx()
    if w <= 0 or y < 0 or x < 0 or y >= rows:
        return
    n = min(w, max(0, cols - x - 1))
    if n <= 0:
        return
    try:
        win.addstr(y, x, " " * n, attr)
    except curses.error:
        pass


def box_acs() -> tuple[int, int, int, int, int, int]:
    return (
        curses.ACS_ULCORNER,
        curses.ACS_URCORNER,
        curses.ACS_LLCORNER,
        curses.ACS_LRCORNER,
        curses.ACS_HLINE,
        curses.ACS_VLINE,
    )


def safe_addch(win: curses.window, y: int, x: int, ch: int | str, attr: int = curses.A_NORMAL) -> None:
    rows, cols = win.getmaxyx()
    if y < 0 or x < 0 or y >= rows or x >= cols:
        return
    try:
        if isinstance(ch, str):
            win.addstr(y, x, ch, attr)
        else:
            win.addch(y, x, ch, attr)
    except curses.error:
        pass


def safe_addstr(win: curses.window, y: int, x: int, text: str, attr: int = curses.A_NORMAL) -> None:
    rows, cols = win.getmaxyx()
    if y < 0 or x < 0 or y >= rows:
        return
    clipped = clip_text(text, max(0, cols - x - 1))
    try:
        win.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def run(path: str) -> Result:
    attach_stdio_to_tty()
    setup_locale()
    original_raw = read_message_file_raw(path)
    parsed = parse_message(original_raw)
    return run_editor(path, original_raw, parsed)

# --- CLI ---

def print_err(msg: str) -> None:
    sys.stderr.write(msg)
    if not msg.endswith("\n"):
        sys.stderr.write("\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    msg = messages(detect_lang())

    if len(argv) < 2:
        print_err(msg.usage)
        return 1

    if argv[1] in ("--help", "-h"):
        print_err(msg.usage)
        return 0

    if argv[1] == "--batch-save":
        if len(argv) < 3:
            print_err("error: --batch-save requires a file path\n")
            return 1
        batch_path = argv[2]
        parsed = read_message_file(batch_path)
        write_message_file(batch_path, parsed.subject, parsed.body)
        return 0

    path = find_message_path(argv)
    if path is None:
        print_err("error: missing commit message file path\n")
        return 1

    if not os.path.isfile(path):
        print_err(f"error: file not found: {path}\n")
        return 1

    try:
        result = run(path)
    except NoTty:
        print_err(msg.no_tty)
        return 1
    except OSError as exc:
        print_err(f"error: {exc}: {path}\n")
        return 1

    return 0 if result in (Result.SAVED, Result.CANCELLED) else 1


if __name__ == "__main__":
    raise SystemExit(main())

