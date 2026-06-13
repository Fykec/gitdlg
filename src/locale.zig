const std = @import("std");

pub const Lang = enum {
    en,
    zh,
};

pub const Strings = struct {
    subject_placeholder: []const u8,
    body_placeholder: []const u8,
    confirm_button: []const u8,
    cancel_button: []const u8,
    footer_hint: []const u8,
    terminal_too_small: []const u8,
};

pub const Messages = struct {
    ui: Strings,
    usage: []const u8,
    no_tty: []const u8,
};

/// Resolve UI language from OS locale env vars. Defaults to English.
pub fn detect(environ_map: *std.process.Environ.Map) Lang {
    const keys = [_][]const u8{ "LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE" };
    for (keys) |key| {
        if (environ_map.get(key)) |value| {
            if (value.len == 0 or std.mem.eql(u8, value, "C") or std.mem.eql(u8, value, "POSIX")) {
                continue;
            }
            if (isChineseLocale(value)) return .zh;
            return .en;
        }
    }
    return .en;
}

pub fn messages(lang: Lang) Messages {
    return switch (lang) {
        .zh => .{
            .ui = .{
                .subject_placeholder = "主题",
                .body_placeholder = "正文",
                .confirm_button = "确认(Ctrl+Enter)",
                .cancel_button = "取消(Esc)",
                .footer_hint = "Ctrl+Enter 确认 | Esc 取消",
                .terminal_too_small = "终端窗口过小，请放大后继续编辑 (Esc 取消)",
            },
            .usage =
                \\gitdlg - 图形化 git commit 消息编辑器
                \\
                \\用法:
                \\  gitdlg <COMMIT_EDITMSG 路径>
                \\  GIT_EDITOR=gitdlg git commit
                \\
                \\快捷键:
                \\  Tab / Shift+Tab  切换 主题 / 正文 / 确认 / 取消
                \\  Ctrl+Enter/Ctrl+J  确认
                \\  Enter            在确认按钮上确认
                \\  Esc / Ctrl+C     取消
                \\
            ,
            .no_tty =
                \\gitdlg: 需要交互式终端 (TTY)。
                \\
                \\请在终端里执行 git commit。
                \\
            ,
        },
        .en => .{
            .ui = .{
                .subject_placeholder = "Subject",
                .body_placeholder = "Body",
                .confirm_button = "Confirm(Ctrl+Enter)",
                .cancel_button = "Cancel(Esc)",
                .footer_hint = "Ctrl+Enter confirm | Esc cancel",
                .terminal_too_small = "Terminal too small; enlarge to edit (Esc to cancel)",
            },
            .usage =
                \\gitdlg - dialog-style git commit message editor
                \\
                \\Usage:
                \\  gitdlg <path-to-COMMIT_EDITMSG>
                \\  GIT_EDITOR=gitdlg git commit
                \\
                \\Keys:
                \\  Tab / Shift+Tab    Cycle Subject, Body, Confirm, Cancel
                \\  Ctrl+Enter/Ctrl+J  Confirm
                \\  Enter on Confirm   Confirm
                \\  Esc / Ctrl+C       Cancel
                \\
            ,
            .no_tty =
                \\gitdlg: an interactive terminal (TTY) is required.
                \\
                \\Please run git commit from a terminal.
                \\
            ,
        },
    };
}

fn isChineseLocale(value: []const u8) bool {
    var segment = value;
    while (segment.len > 0) {
        const part = nextLocaleSegment(&segment);
        if (part.len >= 2 and part[0] == 'z' and part[1] == 'h') return true;
        if (part.len >= 5 and std.ascii.eqlIgnoreCase(part[0..5], "yue")) return true;
    }
    return false;
}

fn nextLocaleSegment(rest: *[]const u8) []const u8 {
    var end: usize = 0;
    while (end < rest.len) : (end += 1) {
        const c = rest.*[end];
        if (c == '.' or c == '@' or c == ':' or c == ';') break;
    }
    const part = rest.*[0..end];
    rest.* = if (end < rest.len) rest.*[end + 1 ..] else "";
    return part;
}

test "detect chinese locales" {
    const gpa = std.testing.allocator;

    {
        var map = std.process.Environ.Map.init(gpa);
        defer map.deinit();
        try map.put("LANG", "zh_CN.UTF-8");
        try std.testing.expect(detect(&map) == .zh);
    }
    {
        var map = std.process.Environ.Map.init(gpa);
        defer map.deinit();
        try map.put("LANG", "en_US.UTF-8");
        try std.testing.expect(detect(&map) == .en);
    }
    {
        var map = std.process.Environ.Map.init(gpa);
        defer map.deinit();
        try map.put("LANGUAGE", "zh_CN:en");
        try std.testing.expect(detect(&map) == .zh);
    }
}

test "default english when unset" {
    var map = std.process.Environ.Map.init(std.testing.allocator);
    defer map.deinit();
    try std.testing.expect(detect(&map) == .en);
}
