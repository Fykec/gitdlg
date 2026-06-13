# gitdlg

**git dialog** — a TUI dialog editor for Git commit messages.

Built with Zig 0.16 and [libvaxis](https://github.com/rockorager/libvaxis). Use it as `$GIT_EDITOR` / `core.editor` when you want a structured Subject + Body form instead of a plain text file.

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
- macOS Terminal.app compatibility for CJK subject rendering

## Build & install

Requires [Zig](https://ziglang.org/) **0.16+**.

```bash
cd /path/to/gitdlg
zig build -Doptimize=ReleaseFast
mkdir -p ~/.local/bin
cp zig-out/bin/gitdlg ~/.local/bin/gitdlg
chmod 755 ~/.local/bin/gitdlg
gitdlg --help
```

### Install Zig 0.16 (if missing)

**macOS:** `brew install zig`

**Linux (x86_64):**

```bash
curl -fsSL -o /tmp/zig.tar.xz \
  https://ziglang.org/download/0.16.0/zig-x86_64-linux-0.16.0.tar.xz
tar -xf /tmp/zig.tar.xz -C ~/.local/opt
export PATH="$HOME/.local/opt/zig-x86_64-linux-0.16.0:$PATH"
echo 'export PATH="$HOME/.local/opt/zig-x86_64-linux-0.16.0:$PATH"' >> ~/.bashrc
```

Mirrors: [community mirror list](https://ziglang.org/download/community-mirrors.txt)

## Configure Git

```bash
# persistent
git config --global core.editor gitdlg
# or with an absolute path:
git config --global core.editor /path/to/gitdlg

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
zig build test
./scripts/integration-test.sh
python3 scripts/tui-smoke-test.py
python3 scripts/terminal-app-compat-test.py
```


## License

See repository license (if present). Otherwise treat as personal / internal tooling until published.
