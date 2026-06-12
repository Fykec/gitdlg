const std = @import("std");
const vaxis = @import("vaxis");

pub const MultiLineInput = struct {
    buf: std.ArrayList(u8) = .empty,
    cursor: usize = 0,

    pub fn deinit(self: *MultiLineInput, alloc: std.mem.Allocator) void {
        self.buf.deinit(alloc);
    }

    pub fn setContent(self: *MultiLineInput, alloc: std.mem.Allocator, text: []const u8) !void {
        self.buf.clearRetainingCapacity();
        self.cursor = 0;
        if (text.len == 0) return;
        try self.buf.appendSlice(alloc, text);
        self.cursor = self.buf.items.len;
    }

    pub fn bytes(self: *const MultiLineInput) []const u8 {
        return self.buf.items;
    }

    pub fn update(self: *MultiLineInput, alloc: std.mem.Allocator, key: vaxis.Key) !void {
        if (key.matches(vaxis.Key.backspace, .{})) {
            if (self.cursor == 0) return;
            const prev = prevCodepointStart(self.buf.items, self.cursor);
            try self.buf.replaceRange(alloc, prev, self.cursor - prev, &.{});
            self.cursor = prev;
            return;
        }
        if (key.matches(vaxis.Key.delete, .{})) {
            if (self.cursor >= self.buf.items.len) return;
            const next = nextCodepointEnd(self.buf.items, self.cursor);
            try self.buf.replaceRange(alloc, self.cursor, next - self.cursor, &.{});
            return;
        }
        if (key.matches(vaxis.Key.left, .{}) or key.matches('b', .{ .ctrl = true })) {
            if (self.cursor > 0) self.cursor = prevCodepointStart(self.buf.items, self.cursor);
            return;
        }
        if (key.matches(vaxis.Key.right, .{}) or key.matches('f', .{ .ctrl = true })) {
            if (self.cursor < self.buf.items.len) self.cursor = nextCodepointEnd(self.buf.items, self.cursor);
            return;
        }
        if (key.matches(vaxis.Key.up, .{})) {
            self.moveVertical(-1);
            return;
        }
        if (key.matches(vaxis.Key.down, .{})) {
            self.moveVertical(1);
            return;
        }
        if (key.matches(vaxis.Key.home, .{}) or key.matches('a', .{ .ctrl = true })) {
            self.cursor = lineStart(self.buf.items, self.cursor);
            return;
        }
        if (key.matches(vaxis.Key.end, .{}) or key.matches('e', .{ .ctrl = true })) {
            self.cursor = lineEnd(self.buf.items, self.cursor);
            return;
        }
        if (key.matches(vaxis.Key.enter, .{})) {
            try self.buf.insert(alloc, self.cursor, '\n');
            self.cursor += 1;
            return;
        }
        if (key.text) |typed| {
            if (std.mem.eql(u8, typed, "\t")) return;
            try self.buf.insertSlice(alloc, self.cursor, typed);
            self.cursor += typed.len;
        }
    }

    pub fn draw(
        self: *const MultiLineInput,
        win: vaxis.Window,
        focused: bool,
        body_placeholder: []const u8,
    ) void {
        if (self.buf.items.len == 0) {
            if (focused) {
                win.showCursor(0, 0);
            }
            if (!focused) {
                _ = win.print(&.{.{ .text = body_placeholder, .style = placeholderStyle() }}, .{
                    .row_offset = 0,
                    .wrap = .none,
                });
            }
            return;
        }

        const text_style: vaxis.Style = .{};

        var y: u16 = 0;
        var line_start: usize = 0;
        var cursor_row: u16 = 0;
        var cursor_col: u16 = 0;
        var cursor_pos_known = false;

        const buf = self.buf.items;
        var i: usize = 0;
        while (i <= buf.len) : (i += 1) {
            const at_eol = i == buf.len or buf[i] == '\n';
            if (!at_eol) continue;
            if (y >= win.height) break;

            const line = buf[line_start..i];
            _ = win.print(&.{.{ .text = line, .style = text_style }}, .{
                .row_offset = y,
                .wrap = .none,
            });

            if (focused and self.cursor >= line_start and self.cursor <= i) {
                cursor_row = y;
                cursor_col = @intCast(win.gwidth(buf[line_start..self.cursor]));
                cursor_pos_known = true;
            }

            y += 1;
            line_start = i + 1;
        }

        if (focused) {
            if (cursor_pos_known) {
                win.showCursor(cursor_col, cursor_row);
            } else if (y < win.height) {
                win.showCursor(0, y);
            }
        }
    }

    fn moveVertical(self: *MultiLineInput, direction: i32) void {
        const col = self.cursor - lineStart(self.buf.items, self.cursor);
        const line_info = lineIndexAt(self.buf.items, self.cursor);
        const target_line: isize = @as(isize, @intCast(line_info.line)) + direction;
        if (target_line < 0) {
            self.cursor = 0;
            return;
        }

        var line_no: usize = 0;
        var line_start: usize = 0;
        var i: usize = 0;
        while (i <= self.buf.items.len) : (i += 1) {
            if (i == self.buf.items.len or self.buf.items[i] == '\n') {
                if (@as(isize, @intCast(line_no)) == target_line) {
                    const line_len = i - line_start;
                    const target_col = @min(col, line_len);
                    self.cursor = line_start + target_col;
                    return;
                }
                line_no += 1;
                line_start = i + 1;
            }
        }
        self.cursor = self.buf.items.len;
    }
};

fn placeholderStyle() vaxis.Style {
    return .{ .dim = true };
}

fn lineStart(content: []const u8, cursor: usize) usize {
    var i = cursor;
    while (i > 0 and content[i - 1] != '\n') i -= 1;
    return i;
}

fn lineEnd(content: []const u8, cursor: usize) usize {
    var i = cursor;
    while (i < content.len and content[i] != '\n') i += 1;
    return i;
}

fn lineIndexAt(content: []const u8, cursor: usize) struct { line: usize, col: usize } {
    var line: usize = 0;
    var line_start: usize = 0;
    var i: usize = 0;
    while (i <= content.len) : (i += 1) {
        if (i == content.len or content[i] == '\n') {
            if (cursor >= line_start and cursor <= i) {
                return .{ .line = line, .col = cursor - line_start };
            }
            line += 1;
            line_start = i + 1;
        }
    }
    return .{ .line = line, .col = 0 };
}

fn prevCodepointStart(content: []const u8, cursor: usize) usize {
    if (cursor == 0) return 0;
    var i = cursor - 1;
    while (i > 0 and (content[i] & 0xc0) == 0x80) i -= 1;
    return i;
}

fn nextCodepointEnd(content: []const u8, cursor: usize) usize {
    if (cursor >= content.len) return content.len;
    var i = cursor + 1;
    while (i < content.len and (content[i] & 0xc0) == 0x80) i += 1;
    return i;
}

test "multiline insert and newline" {
    const gpa = std.testing.allocator;
    var input: MultiLineInput = .{};
    defer input.deinit(gpa);

    try input.setContent(gpa, "hello");
    try input.buf.appendSlice(gpa, "!");
    input.cursor = input.buf.items.len;
    try std.testing.expectEqualStrings("hello!", input.bytes());

    try input.buf.append(gpa, '\n');
    try std.testing.expectEqualStrings("hello!\n", input.bytes());
}
