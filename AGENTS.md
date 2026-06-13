# Agent guide — gitdlg

Python 3 single-file Git commit TUI editor. **Read this before changing the codebase.**

## Quick facts

- **App:** `gitdlg.py` only (stdlib `curses`, no pip)
- **Branch:** `py` (Python); `main` (Zig binary)
- **Platform:** macOS / Linux, interactive TTY required

## Full development guide

See [skills/gitdlg/SKILL.md](skills/gitdlg/SKILL.md) for:

- Git editor contract (args, exit codes, cancel semantics)
- Architecture inside `gitdlg.py`
- Terminal/CJK pitfalls and fixes
- Test commands

## Verify changes

```bash
python3 scripts/test_gitdlg.py
./scripts/integration-test.sh
```

## User docs

- [README.md](README.md) — English
- [README.zh-CN.md](README.zh-CN.md) — 中文
