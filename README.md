# gitdlg

**git dialog** — a TUI dialog editor for Git commit messages.

Built with Zig 0.16 and [libvaxis](https://github.com/rockorager/libvaxis). Use it as `$GIT_EDITOR` / `core.editor` when you want a structured Subject + Body form instead of a plain text file.

[中文文档](README.zh-CN.md)

<p align="center">
  <img src="./assets/gitdlg-screenshot.jpg" alt="gitdlg dialog-style commit editor" width="900">
</p>

## Features

- Subject + Body form in a centered dialog
- Tab / Shift+Tab to move focus (Subject → Body → Confirm → Cancel)
- Confirm and Cancel buttons with keyboard shortcuts
- Parses git `#` comment lines in `COMMIT_EDITMSG`
- Cancel restores the original file (`:q!` semantics; exit 0)
- UI follows terminal default colors (bold / dim / reverse only)
- Locale-aware UI: English by default; Chinese when `LANG` / `LC_*` starts with `zh`
- macOS Terminal.app compatibility for CJK subject rendering

## Build & install

Requires [Zig](https://ziglang.org/) **0.16+**.

### macOS

```bash
brew install zig
cd /path/to/gitdlg
zig build -Doptimize=ReleaseFast
mkdir -p ~/.local/bin
install -m 755 zig-out/bin/gitdlg ~/.local/bin/gitdlg
gitdlg --help
```

### Linux

**Install Zig 0.16 (x86_64 example):**

```bash
curl -fsSL -o /tmp/zig.tar.xz \
  https://ziglang.org/download/0.16.0/zig-x86_64-linux-0.16.0.tar.xz
tar -xf /tmp/zig.tar.xz -C ~/.local/opt
export PATH="$HOME/.local/opt/zig-x86_64-linux-0.16.0:$PATH"
zig version   # should print 0.16.0
```

**Community mirrors:** pick one from the [mirror list](https://ziglang.org/download/community-mirrors.txt). Example:

```bash
curl -fsSL -o /tmp/zig.tar.xz \
  https://fs.liujiacai.net/zigbuilds/0.16.0/zig-x86_64-linux-0.16.0.tar.xz
tar -xf /tmp/zig.tar.xz -C ~/.local/opt
export PATH="$HOME/.local/opt/zig-x86_64-linux-0.16.0:$PATH"
```

The full tarball is **55,478,392 bytes**. If the size differs, try another mirror or the official URL.

Add the `export PATH=...` line to `~/.bashrc` or `~/.zshrc` so new shells can find `zig`.

**Build and install:**

```bash
cd /path/to/gitdlg
zig build -Doptimize=ReleaseFast
mkdir -p ~/.local/bin
install -m 755 zig-out/bin/gitdlg ~/.local/bin/gitdlg
gitdlg --help
```

## Configure Git

```bash
# persistent
git config --global core.editor gitdlg
# or with an absolute path:
git config --global core.editor /path/to/gitdlg

# one-off
GIT_EDITOR=gitdlg git commit
```

### Cursor / VS Code

The TUI needs a real terminal. Run `git commit` in the **integrated terminal** to open the dialog.

If you commit from the **Source Control** panel, enable **Terminal Git Editor** (`git.terminalGitEditor`: `true`), or set:

```bash
git config --global core.editor /path/to/scripts/gitdlg-wrapper.sh
```

The wrapper re-attaches stdio to `/dev/tty` when Git is launched without a controlling terminal.

Without a TTY, Git reports `there was a problem with the editor` and the dialog does not open.

### macOS Terminal.app

`gitdlg` disables vaxis explicit-width rendering on `TERM_PROGRAM=Apple_Terminal` so Chinese (and other wide) subject text displays correctly.

## Keys

| Key | Action |
|-----|--------|
| Tab / Shift+Tab | Cycle Subject → Body → Confirm → Cancel |
| ↑↓←→ on buttons | Move between Confirm / Cancel |
| Ctrl+Enter / Ctrl+J | Confirm (save message) |
| Enter / Space on button | Activate Confirm or Cancel |
| Esc / Ctrl+C | Cancel (restore original `COMMIT_EDITMSG`) |

Note: `Ctrl+S` is often captured by the terminal; prefer **Ctrl+Enter** to confirm.

## Test

```bash
zig build test
./scripts/integration-test.sh
python3 scripts/tui-smoke-test.py
python3 scripts/terminal-app-compat-test.py
```

## Layout

| Terminal size | Behavior |
|---------------|----------|
| Large enough | Subject + Body + buttons |
| Medium | Subject + buttons (Body hidden) |
| Small | Subject only |
| Too small | Centered hint; Esc to cancel |

Maximum dialog size: **80×22** (centered when the terminal is larger).

## Project layout

| Path | Role |
|------|------|
| `src/commit.zig` | Parse / format / restore `COMMIT_EDITMSG` |
| `src/multiline.zig` | Body input |
| `src/editor.zig` | vaxis dialog UI |
| `src/locale.zig` | i18n strings and `--help` |
| `src/main.zig` | CLI entry (`GIT_EDITOR` contract) |
| `scripts/gitdlg-wrapper.sh` | TTY wrapper for GUI Git clients |
| `skills/gitdlg/` | Agent skill (install → see below) |

### Cursor Agent skill

Skill source lives in `skills/gitdlg/` (versioned with the repo). Enable it:

```bash
mkdir -p .cursor/skills
ln -sf ../../skills/gitdlg .cursor/skills/gitdlg
```

For all projects: `ln -sf /path/to/gitdlg/skills/gitdlg ~/.cursor/skills/gitdlg`

## License

See repository license (if present). Otherwise treat as personal / internal tooling until published.
