---
name: gitdlg
description: >-
  Maintain and extend gitdlg, a Python 3 stdlib TUI Git commit message editor
  (single-file gitdlg.py). Use when editing gitdlg.py, fixing terminal/CJK
  layout or input bugs, updating Git editor behavior, or running gitdlg tests.
---

# gitdlg

Python 3 **single-file** Git commit dialog editor (`gitdlg.py`). Branch `py`; Zig binary lives on `main`.

## Distribution model

- **Ship only `gitdlg.py`** — entire app in one file (~1200 lines, stdlib only).
- No pip deps. Requires Python 3.9+ with `curses`.
- Do **not** split back into packages unless user explicitly asks.

## Git editor contract

- Args: `gitdlg <COMMIT_EDITMSG>` (skip `-` / `+vim` args via `find_message_path`)
- `--batch-save <path>`: parse `#` comments, rewrite file (integration tests)
- `--help` / `-h`: usage on stderr, exit 0
- Save: write subject + blank line + body; exit 0
- Cancel (Esc): restore **raw** original bytes; exit 0
- No TTY: print `no_tty` message; exit 1

## Architecture (sections in gitdlg.py)

1. **commit message I/O** — `parse_message`, `format_message`, file read/write
2. **locale** — `detect_lang`, `messages` (EN/zh UI strings)
3. **terminal editor** — curses layout, input loop, draw
4. **CLI** — `main()`

## Critical implementation rules

### Terminal size

`curses.getmaxyx()` returns `(rows, cols)`. Layout uses `(term_w, term_h)` = **(cols, rows)**.

```python
def terminal_size(win):
    rows, cols = win.getmaxyx()
    return cols, rows
```

Never pass `*stdscr.getmaxyx()` directly to `ComputedLayout.compute`.

### UTF-8 / Chinese input

Use **`get_wch()`** via `read_key()`, not `getch()`. IME returns `str`; special keys return `int`.

- Text: `subject.insert(ch)` when `isinstance(ch, str)`
- Set `LANG` / `LC_CTYPE` UTF-8 in `setup_locale()` before `curses.wrapper`

### Box drawing

Use **ncurses ACS** (`ACS_ULCORNER`, `ACS_HLINE`, …) with `addch`, not Unicode `┌─│`.

Unicode box chars are East Asian Width **Ambiguous** — in `zh_*` locale terminals they render **double-width** and break layout.

### Text cursor placement

`addstr` moves the terminal cursor. Always call **`place_cursor()` at the end of `draw()`** after footer/buttons/placeholders.

### Ctrl+S

Disable terminal IXON (`termios`) in `attach_stdio_to_tty()` and PTY test child, or Ctrl+S triggers flow control instead of save.

### Colors

Call `curses.start_color()` before `use_default_colors()`. Use attributes only: `A_BOLD`, `A_DIM`, `A_REVERSE` — no indexed colors.

## Layout modes

`ComputedLayout.compute(cols, rows)` picks `FULL`, `NO_BODY`, `NO_BUTTONS`, or `TOO_SMALL` based on inner panel size. Footer at `ph - 1`; buttons at `btn_row`.

## Testing

```bash
python3 scripts/test_gitdlg.py
./scripts/integration-test.sh
```

PTY tests use `scripts/pty_harness.py` → `python3 gitdlg.py`. Python curses alt-screen may not echo UI text to PTY capture; functional tests (save/cancel/roundtrip) are authoritative.

## Common pitfalls (already fixed — do not regress)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Blank screen in Ghostty | `getmaxyx` rows/cols swapped | `terminal_size()` |
| Garbled Chinese input | `getch` byte fragments | `get_wch` + `read_key` |
| Messy borders in zh locale | Unicode box double-width | ACS line chars |
| Text cursor not in Subject | later `addstr` moves cursor | `place_cursor()` last |
| Ctrl+S hangs in PTY | IXON flow control | disable IXON |

## When modifying

- Keep **minimal diff** — single file, no new dependencies.
- Match existing key bindings and Git `:q!` cancel semantics.
- Run `python3 scripts/test_gitdlg.py` and `./scripts/integration-test.sh`.
- Update `README.md` / `README.zh-CN.md` if install or behavior changes.
