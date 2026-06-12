---
name: gitdlg
description: >-
  Build, install, and configure gitdlg (git dialog), a TUI commit message editor
  for Git as GIT_EDITOR/core.editor. Use when the user mentions gitdlg, git dialog,
  GIT_EDITOR, core.editor, commit message dialog, Terminal.app CJK subject, or
  installing this repository's commit editor.
---

# gitdlg

TUI dialog editor for Git commit messages (Subject + Body + Confirm/Cancel).

## Install this skill (Cursor users)

This skill ships in the repo at `skills/gitdlg/`. After cloning gitdlg, pick one:

```bash
# project-only (recommended): skill travels with the repo
mkdir -p .cursor/skills
ln -sf ../../skills/gitdlg .cursor/skills/gitdlg

# or user-wide: available in all workspaces
mkdir -p ~/.cursor/skills
ln -sf /path/to/gitdlg/skills/gitdlg ~/.cursor/skills/gitdlg
```

Restart Cursor or open a new Agent chat so the skill is picked up.

## When to use

- User wants `git commit` to open a dialog instead of vim/nano
- User sets up `core.editor` or `GIT_EDITOR`
- User commits from Cursor/VS Code and needs TTY wrapper
- User reports Chinese subject missing in macOS Terminal.app

## Build

From repository root (requires Zig 0.16+):

```bash
zig build -Doptimize=ReleaseFast
```

Binary: `zig-out/bin/gitdlg`

Verify:

```bash
zig-out/bin/gitdlg --help
```

## Install binary on PATH

```bash
install -m 755 zig-out/bin/gitdlg ~/.local/bin/gitdlg
# or: sudo install -m 755 zig-out/bin/gitdlg /usr/local/bin/gitdlg
```

Ensure the install directory is on `PATH`.

## Configure Git

```bash
git config --global core.editor gitdlg
# or absolute path if not on PATH:
git config --global core.editor "$(pwd)/zig-out/bin/gitdlg"
```

One-off:

```bash
GIT_EDITOR=gitdlg git commit
```

## Cursor / VS Code (no TTY from GUI)

Option A — integrated terminal (recommended):

```json
"git.terminalGitEditor": true
```

Then run `git commit` in the terminal panel.

Option B — wrapper script:

```bash
git config --global core.editor "/absolute/path/to/gitdlg/scripts/gitdlg-wrapper.sh"
```

Wrapper re-attaches stdio to `/dev/tty` when Git lacks a controlling terminal.

## Expected behavior

| Action | Result |
|--------|--------|
| Confirm (Ctrl+Enter) | Writes Subject + Body to `COMMIT_EDITMSG`; exit 0 |
| Cancel (Esc) | Restores file Git opened; exit 0; Git aborts commit with "you did not edit the message" |
| `--help` | Usage and key bindings |

UI language: English default; Chinese when `LANG`/`LC_*` is `zh*`.

## macOS Terminal.app

No extra config. `TERM_PROGRAM=Apple_Terminal` triggers built-in CJK / explicit-width workaround.

## Test after changes

```bash
zig build test
./scripts/integration-test.sh
python3 scripts/tui-smoke-test.py
python3 scripts/terminal-app-compat-test.py
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `there was a problem with the editor` | No TTY: use terminal Git editor or `gitdlg-wrapper.sh` |
| Chinese subject blank in Terminal.app | Rebuild latest; ensure `applyTerminalCompat` in `editor.zig` |
| Old binary still runs | Update `core.editor` path; rebuild with `-Doptimize=ReleaseFast` |
| Ctrl+Enter ignored | Use Ctrl+J or click Confirm; some terminals swallow Ctrl+S |

## Do not

- Point `core.editor` at obsolete binary names (`git-dialog` → use `gitdlg`)
- Commit `.env` or secrets when helping user configure Git
