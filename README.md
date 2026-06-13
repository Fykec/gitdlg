# gitdlg

**git dialog** — a TUI dialog editor for Git commit messages.

Python 3 stdlib only (`curses`, no pip, no compile). Use as `$GIT_EDITOR` / `core.editor` for a Subject + Body form instead of a plain text file.

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
- macOS / Linux terminal support (including Terminal.app CJK rendering)

## Install

Requires **Python 3.9+** with `curses` (included on typical macOS / Linux builds).

**Single-file distribution:** copy `gitdlg.py` only.

```bash
cp gitdlg.py ~/.local/bin/gitdlg
chmod +x ~/.local/bin/gitdlg
gitdlg --help
```

Or point Git at the script directly:

```bash
git config --global core.editor /path/to/gitdlg.py
```

## Configure Git

```bash
# persistent
git config --global core.editor gitdlg
# or with an absolute path:
git config --global core.editor /path/to/gitdlg.py

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

## Test

```bash
python3 scripts/test_gitdlg.py
chmod +x scripts/integration-test.sh
./scripts/integration-test.sh
```

## License

See repository license (if present). Otherwise treat as personal / internal tooling until published.
