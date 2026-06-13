# gitdlg

**git dialog** — 面向 Git 提交信息的 TUI 对话框编辑器。

Python 3 标准库实现（`curses`，无需 pip、无需编译）。作为 `$GIT_EDITOR` / `core.editor` 使用时，用 Subject + Body 表单替代纯文本编辑。

[English README](README.md)

<p align="center">
  <img src="./assets/gitdlg-usage.png" alt="gitdlg 对话框提交信息编辑器" width="900">
</p>

## 功能

- 居中对话框：Subject + Body
- Tab / Shift+Tab 切换焦点（主题 → 正文 → 确认 → 取消）
- 确认 / 取消按钮及快捷键
- 解析 `COMMIT_EDITMSG` 中以 `#` 开头的注释行
- 取消时恢复 Git 打开的原始文件（类似 vim `:q!`，退出码 0）
- 配色跟随终端默认色（仅 bold / dim / reverse）
- 界面随 locale 切换：默认英文；`LANG` / `LC_*` 为 `zh*` 时显示中文
- 兼容 macOS / Linux 终端（含 Terminal.app 中文显示）

## 安装

需要 **Python 3.9+**（自带 `curses`，macOS / Linux 一般已满足）。

**单文件分发**：只需拷贝 `gitdlg.py` 一个文件。

```bash
cp gitdlg.py ~/.local/bin/gitdlg
chmod +x ~/.local/bin/gitdlg
gitdlg --help
```

或直接配置绝对路径：

```bash
git config --global core.editor /path/to/gitdlg.py
```

## 配置 Git

```bash
# 长期使用
git config --global core.editor gitdlg
# 或绝对路径：
git config --global core.editor /path/to/gitdlg.py

# 单次
GIT_EDITOR=gitdlg git commit
```

## 快捷键

| 按键 | 作用 |
|------|------|
| Tab / Shift+Tab | 切换 主题 → 正文 → 确认 → 取消 |
| 确认/取消上 ↑↓←→ | 在按钮间移动 |
| Ctrl+S | 确认（保存） |
| 按钮上 Enter | 确认或取消 |
| Esc | 取消（恢复原始 `COMMIT_EDITMSG`） |

## 测试

```bash
python3 scripts/test_gitdlg.py
chmod +x scripts/integration-test.sh
./scripts/integration-test.sh
```
