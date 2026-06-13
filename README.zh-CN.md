# gitdlg

**git dialog** — 面向 Git 提交信息的 TUI 对话框编辑器。

基于 Zig 0.16 与 [libvaxis](https://github.com/rockorager/libvaxis)。作为 `$GIT_EDITOR` / `core.editor` 使用时，用 Subject + Body 表单替代纯文本编辑。

[English README](README.md)

<p align="center">
  <img src="./assets/gitdlg-screenshot.jpg" alt="gitdlg 对话框提交信息编辑器" width="900">
</p>

## 功能

- 居中对话框：Subject + Body
- Tab / Shift+Tab 切换焦点（主题 → 正文 → 确认 → 取消）
- 确认 / 取消按钮及快捷键
- 解析 `COMMIT_EDITMSG` 中以 `#` 开头的注释行
- 取消时恢复 Git 打开的原始文件（类似 vim `:q!`，退出码 0）
- 配色跟随终端默认色（仅 bold / dim / reverse）
- 界面随 locale 切换：默认英文；`LANG` / `LC_*` 为 `zh*` 时显示中文
- 兼容 macOS Terminal.app 中文 Subject 显示

## 构建与安装

需要 [Zig](https://ziglang.org/) **0.16+**。

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

**安装 Zig 0.16（x86_64 示例）：**

```bash
curl -fsSL -o /tmp/zig.tar.xz \
  https://ziglang.org/download/0.16.0/zig-x86_64-linux-0.16.0.tar.xz
tar -xf /tmp/zig.tar.xz -C ~/.local/opt
export PATH="$HOME/.local/opt/zig-x86_64-linux-0.16.0:$PATH"
zig version   # 应输出 0.16.0
```

**国内镜像：** 可从 [Zig 社区镜像列表](https://ziglang.org/download/community-mirrors.txt) 选取。例如：

```bash
curl -fsSL -o /tmp/zig.tar.xz \
  https://fs.liujiacai.net/zigbuilds/0.16.0/zig-x86_64-linux-0.16.0.tar.xz
tar -xf /tmp/zig.tar.xz -C ~/.local/opt
export PATH="$HOME/.local/opt/zig-x86_64-linux-0.16.0:$PATH"
```

完整包大小应为 **55,478,392 字节**；若不符，请换镜像或改用官方源重试。

将 `export PATH=...` 写入 `~/.bashrc` 或 `~/.zshrc`，以便新终端也能找到 `zig`。

**编译并安装：**

```bash
cd /path/to/gitdlg
zig build -Doptimize=ReleaseFast
mkdir -p ~/.local/bin
install -m 755 zig-out/bin/gitdlg ~/.local/bin/gitdlg
gitdlg --help
```

## 配置 Git

```bash
# 长期使用
git config --global core.editor gitdlg
# 或绝对路径：
git config --global core.editor /path/to/gitdlg

# 单次
GIT_EDITOR=gitdlg git commit
```

### Cursor / VS Code

TUI 需要真实终端。请在**集成终端**里执行 `git commit` 打开对话框。

若从**源代码管理面板**提交，请开启 **Terminal Git Editor**（`git.terminalGitEditor`: `true`），或：

```bash
git config --global core.editor /path/to/scripts/gitdlg-wrapper.sh
```

wrapper 会在 Git 无 controlling TTY 时把 stdio 接到 `/dev/tty`。

无 TTY 时 Git 会报错 `there was a problem with the editor`，对话框不会出现。

### macOS Terminal.app

在 `TERM_PROGRAM=Apple_Terminal` 下会关闭 vaxis 的 explicit-width 渲染，避免中文 Subject 不显示。

## 快捷键

| 按键 | 作用 |
|------|------|
| Tab / Shift+Tab | 切换 主题 → 正文 → 确认 → 取消 |
| 确认/取消上 ↑↓←→ | 在按钮间移动 |
| Ctrl+Enter / Ctrl+J | 确认（保存） |
| 按钮上 Enter / Space | 确认或取消 |
| Esc / Ctrl+C | 取消（恢复原始 `COMMIT_EDITMSG`） |

说明：终端常占用 `Ctrl+S`，确认请优先用 **Ctrl+Enter**。

## 测试

```bash
zig build test
./scripts/integration-test.sh
python3 scripts/tui-smoke-test.py
python3 scripts/terminal-app-compat-test.py
```

## 布局

| 终端尺寸 | 行为 |
|----------|------|
| 足够大 | Subject + Body + 按钮 |
| 中等 | Subject + 按钮（隐藏 Body） |
| 较小 | 仅 Subject |
| 过小 | 居中提示；Esc 取消 |

对话框最大约 **80×22**；终端更大时居中显示。

## 目录

| 路径 | 说明 |
|------|------|
| `src/commit.zig` | 解析 / 格式化 / 恢复 `COMMIT_EDITMSG` |
| `src/multiline.zig` | Body 输入 |
| `src/editor.zig` | vaxis 对话框 UI |
| `src/locale.zig` | 文案与 `--help` |
| `src/main.zig` | CLI 入口 |
| `scripts/gitdlg-wrapper.sh` | GUI Git 客户端 TTY 包装 |
| `skills/gitdlg/` | Agent skill（安装见下） |

### Cursor Agent skill

Skill 源码在 `skills/gitdlg/`（随仓库发布）。启用方式：

```bash
mkdir -p .cursor/skills
ln -sf ../../skills/gitdlg .cursor/skills/gitdlg
```

全局可用：`ln -sf /path/to/gitdlg/skills/gitdlg ~/.cursor/skills/gitdlg`
