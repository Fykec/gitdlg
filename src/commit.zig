const std = @import("std");

pub const Parsed = struct {
    subject: []const u8,
    body: []const u8,
};

/// Split a git commit message buffer into subject and body.
/// Lines starting with `#` are treated as comments and ignored.
pub fn parseMessage(allocator: std.mem.Allocator, content: []const u8) !Parsed {
    var lines: std.ArrayList([]const u8) = .empty;
    defer lines.deinit(allocator);

    var iter = std.mem.splitScalar(u8, content, '\n');
    while (iter.next()) |raw_line| {
        const line = std.mem.trimEnd(u8, raw_line, "\r");
        const trimmed = std.mem.trim(u8, line, " \t");
        if (trimmed.len == 0) continue;
        if (trimmed[0] == '#') continue;
        try lines.append(allocator, trimmed);
    }

    if (lines.items.len == 0) {
        return .{
            .subject = try allocator.dupe(u8, ""),
            .body = try allocator.dupe(u8, ""),
        };
    }

    const subject = try allocator.dupe(u8, lines.items[0]);
    if (lines.items.len == 1) {
        return .{
            .subject = subject,
            .body = try allocator.dupe(u8, ""),
        };
    }

    var body: std.ArrayList(u8) = .empty;
    defer body.deinit(allocator);

    var i: usize = 1;
    while (i < lines.items.len) : (i += 1) {
        try body.appendSlice(allocator, lines.items[i]);
        if (i + 1 < lines.items.len) try body.append(allocator, '\n');
    }

    return .{
        .subject = subject,
        .body = try body.toOwnedSlice(allocator),
    };
}

/// Format subject/body the way git expects in COMMIT_EDITMSG.
pub fn formatMessage(allocator: std.mem.Allocator, subject: []const u8, body: []const u8) ![]u8 {
    const trimmed_subject = std.mem.trim(u8, subject, " \t\r\n");
    const trimmed_body = std.mem.trim(u8, body, " \t\r\n");

    if (trimmed_body.len == 0) {
        if (trimmed_subject.len == 0) return try allocator.dupe(u8, "");
        var out: std.ArrayList(u8) = .empty;
        defer out.deinit(allocator);
        try out.appendSlice(allocator, trimmed_subject);
        try out.append(allocator, '\n');
        return try out.toOwnedSlice(allocator);
    }

    var out: std.ArrayList(u8) = .empty;
    defer out.deinit(allocator);
    try out.appendSlice(allocator, trimmed_subject);
    try out.append(allocator, '\n');
    try out.append(allocator, '\n');
    try out.appendSlice(allocator, trimmed_body);
    if (!std.mem.endsWith(u8, trimmed_body, "\n")) {
        try out.append(allocator, '\n');
    }
    return try out.toOwnedSlice(allocator);
}

pub fn writeMessageFile(
    allocator: std.mem.Allocator,
    io: std.Io,
    path: []const u8,
    subject: []const u8,
    body: []const u8,
) !void {
    const content = try formatMessage(allocator, subject, body);
    defer allocator.free(content);
    try writeFileContent(io, path, content);
}

pub fn readMessageFileRaw(allocator: std.mem.Allocator, io: std.Io, path: []const u8) ![]u8 {
    return readFileContent(allocator, io, path);
}

pub fn restoreMessageFile(io: std.Io, path: []const u8, content: []const u8) !void {
    try writeFileContent(io, path, content);
}

fn writeFileContent(io: std.Io, path: []const u8, content: []const u8) !void {
    if (std.fs.path.isAbsolute(path)) {
        var file = try std.Io.Dir.createFileAbsolute(io, path, .{ .truncate = true });
        defer file.close(io);
        try file.writeStreamingAll(io, content);
        return;
    }
    try std.Io.Dir.cwd().writeFile(io, .{
        .sub_path = path,
        .data = content,
        .flags = .{ .truncate = true },
    });
}

pub fn readMessageFile(allocator: std.mem.Allocator, io: std.Io, path: []const u8) !Parsed {
    const content = try readFileContent(allocator, io, path);
    defer allocator.free(content);
    return parseMessage(allocator, content);
}

fn readFileContent(allocator: std.mem.Allocator, io: std.Io, path: []const u8) ![]u8 {
    var file = try openMessageFile(io, path);
    defer file.close(io);

    const stat = try file.stat(io);
    if (stat.size == 0) return try allocator.dupe(u8, "");

    var read_buf: [4096]u8 = undefined;
    var reader = file.reader(io, &read_buf);
    return reader.interface.readAlloc(allocator, @intCast(stat.size));
}

fn openMessageFile(io: std.Io, path: []const u8) !std.Io.File {
    if (std.fs.path.isAbsolute(path)) {
        return std.Io.Dir.openFileAbsolute(io, path, .{});
    }
    return std.Io.Dir.cwd().openFile(io, path, .{});
}

/// Git may prepend `+line` arguments before the file path.
pub fn findMessagePath(args: []const []const u8) ?[]const u8 {
    var i: isize = @as(isize, @intCast(args.len)) - 1;
    while (i >= 1) : (i -= 1) {
        const arg = args[@intCast(i)];
        if (arg.len == 0) continue;
        if (arg[0] == '-' or arg[0] == '+') continue;
        return arg;
    }
    return null;
}

test "parse git template with comments" {
    const gpa = std.testing.allocator;
    const input =
        \\# Please enter the commit message for your changes.
        \\# On branch main
        \\
        \\feat: add gitdlg
        \\
        \\Body paragraph one.
        \\Body paragraph two.
        \\
    ;

    const parsed = try parseMessage(gpa, input);
    defer {
        gpa.free(parsed.subject);
        gpa.free(parsed.body);
    }

    try std.testing.expectEqualStrings("feat: add gitdlg", parsed.subject);
    try std.testing.expectEqualStrings("Body paragraph one.\nBody paragraph two.", parsed.body);
}

test "parse chinese subject" {
    const gpa = std.testing.allocator;
    const input =
        \\# Please enter the commit message.
        \\
        \\修复：中文主题展示
        \\
        \\正文第一段。
        \\
    ;

    const parsed = try parseMessage(gpa, input);
    defer {
        gpa.free(parsed.subject);
        gpa.free(parsed.body);
    }

    try std.testing.expectEqualStrings("修复：中文主题展示", parsed.subject);
    try std.testing.expectEqualStrings("正文第一段。", parsed.body);
}

test "format message roundtrip" {
    const gpa = std.testing.allocator;
    const formatted = try formatMessage(gpa, "subject", "line one\nline two");
    defer gpa.free(formatted);

    try std.testing.expectEqualStrings("subject\n\nline one\nline two\n", formatted);

    const parsed = try parseMessage(gpa, formatted);
    defer {
        gpa.free(parsed.subject);
        gpa.free(parsed.body);
    }
    try std.testing.expectEqualStrings("subject", parsed.subject);
    try std.testing.expectEqualStrings("line one\nline two", parsed.body);
}

test "empty message" {
    const gpa = std.testing.allocator;
    const parsed = try parseMessage(gpa, "# comment only\n");
    defer {
        gpa.free(parsed.subject);
        gpa.free(parsed.body);
    }
    try std.testing.expectEqualStrings("", parsed.subject);
    try std.testing.expectEqualStrings("", parsed.body);
}

test "find message path skips vim args" {
    const args = [_][]const u8{ "gitdlg", "+3", "/tmp/COMMIT_EDITMSG" };
    try std.testing.expectEqualStrings("/tmp/COMMIT_EDITMSG", findMessagePath(&args).?);
}

test "restore message file preserves raw bytes" {
    const io = std.testing.io;
    const path = "/tmp/gitdlg-restore-test";
    const raw = "# comment\n\nfeat: amend me\n\nbody line\n";
    try restoreMessageFile(io, path, raw);
    try restoreMessageFile(io, path, "edited");
    try restoreMessageFile(io, path, raw);
    defer std.Io.Dir.cwd().deleteFile(io, path) catch {};
    const read_back = try readMessageFileRaw(std.testing.allocator, io, path);
    defer std.testing.allocator.free(read_back);
    try std.testing.expectEqualStrings(raw, read_back);
}

test "write and read message file" {
    const gpa = std.testing.allocator;
    const io = std.testing.io;

    const tmp_path = "/tmp/gitdlg-test-msg";
    try writeMessageFile(gpa, io, tmp_path, "feat: test", "details here");
    defer std.Io.Dir.cwd().deleteFile(io, tmp_path) catch {};

    const parsed = try readMessageFile(gpa, io, tmp_path);
    defer {
        gpa.free(parsed.subject);
        gpa.free(parsed.body);
    }

    try std.testing.expectEqualStrings("feat: test", parsed.subject);
    try std.testing.expectEqualStrings("details here", parsed.body);
}

test "write absolute path" {
    const io = std.testing.io;
    const path = "/tmp/gitdlg-abs-write-test";
    defer std.Io.Dir.cwd().deleteFile(io, path) catch {};
    try restoreMessageFile(io, path, "hello\n");
    var file = try std.Io.Dir.openFileAbsolute(io, path, .{});
    defer file.close(io);
    const stat = try file.stat(io);
    try std.testing.expect(stat.size == 6);
}
