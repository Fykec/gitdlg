# gitdlg

**git dialog** — a TUI dialog editor for Git commit messages.

Python 3 stdlib only (`curses`, no pip, no compile). Use as `$GIT_EDITOR` / `core.editor` for a Subject + Body form instead of a plain text file.

**Single-file distribution:** copy `gitdlg.py` only.

[中文文档](README.zh-CN.md)

<p align="center">
  <img src="./assets/gitdlg-usage.png" alt="gitdlg dialog-style commit editor" width="900">
</p>

## Features

- Subject + Body form in a centered dialog
- Tab / Shift+Tab to move focus (Subject → Body → Confirm → Cancel)
- Confirm and Cancel buttons with keyboard shortcuts
- Parses git `#` comment lines in `COMMIT_EDITMSG`
- Cancel restores the original file (`:q!` semantics; exit 0)
- UI follows terminal default colors (bold / dim / reverse only)
- Locale-aware UI: English by default; Chinese when `LANG` / `LC_*` starts with `zh`
- UTF-8 input via wide-character API (Chinese IME works)
- macOS / Linux terminals: Warp, Ghostty, Terminal.app, iTerm2, Linux VT
- Mouse click support restores terminal mouse mode on exit, including Warp SGR mouse sequences

## Requirements

- **Python 3.9+** with `curses` (typical macOS / Linux builds)
- Interactive TTY (`git commit` from a terminal)
- UTF-8 locale recommended for CJK (`LANG=en_US.UTF-8` or `zh_CN.UTF-8`)

## Install

```bash
cp gitdlg.py ~/.local/bin/gitdlg
chmod +x ~/.local/bin/gitdlg
gitdlg --help
```

Or point Git at the script directly (recommended when not on `PATH`):

```bash
git config --global core.editor "$(command -v python3) $HOME/.local/bin/gitdlg"
# or absolute path:
git config --global core.editor "/path/to/gitdlg.py"
```

## Configure Git

```bash
# persistent (script must be executable, or invoke via python3)
git config --global core.editor gitdlg

# one-off
GIT_EDITOR=gitdlg git commit
```

## Keys

| Key | Action |
|-----|--------|
| Tab / Shift+Tab | Cycle Subject → Body → Confirm → Cancel |
| ↑↓←→ on buttons | Move between Confirm / Cancel |
| Ctrl+S | Confirm (save message) |
| Enter on button | Activate Confirm or Cancel |
| Esc | Cancel (restore original `COMMIT_EDITMSG`) |
| Enter in Subject | Move focus to Body (or Confirm if Body hidden) |
| Enter in Body | Insert newline |

## Project layout

| Path | Purpose |
|------|---------|
| `gitdlg.py` | **The entire app** — copy this file to distribute |
| `AGENTS.md` | Agent guide (all coding agents) |
| `skills/gitdlg/SKILL.md` | Detailed development guide for agents |
| `scripts/test_gitdlg.py` | Unit tests |
| `scripts/integration-test.sh` | Git + PTY integration tests |
| `scripts/tui-smoke-test.py` | PTY smoke tests |
| `scripts/terminal-app-compat-test.py` | Terminal.app / CJK tests |
| `scripts/warp-garbage-test.py` | Warp mouse / terminal protocol garbage tests |
| `scripts/pty_harness.py` | Shared PTY test helpers |

## Test

```bash
python3 scripts/test_gitdlg.py
chmod +x scripts/integration-test.sh
./scripts/integration-test.sh
```

## Branches

| Branch | Implementation |
|--------|----------------|
| `py` | Python 3 single-file (`gitdlg.py`) — **current** |
| `main` | Zig + libvaxis static binary |

## License

MIT License. Copyright (c) 2026 Jiaji Yin. See [LICENSE](LICENSE).
