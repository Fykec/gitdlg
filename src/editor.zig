const std = @import("std");
const vaxis = @import("vaxis");
const commit = @import("commit.zig");
const locale = @import("locale.zig");
const multiline = @import("multiline.zig");
const tty_attach = @import("tty_attach.zig");

const MultiLineInput = multiline.MultiLineInput;
const TextInput = vaxis.widgets.TextInput;
const Cell = vaxis.Cell;

pub const Result = union(enum) {
    saved,
    cancelled,
};

const Focus = enum {
    subject,
    body,
    confirm,
    cancel,


    fn isButton(self: Focus) bool {
        return self == .confirm or self == .cancel;
    }

    /// Vertical focus move (Tab companion; not shown in UI hints).
    fn moveFocusVertical(self: Focus, dir: VerticalDir) Focus {
        return switch (dir) {
            .up => switch (self) {
                .subject => .cancel,
                .body => .subject,
                .confirm, .cancel => .body,
            },
            .down => switch (self) {
                .subject => .body,
                .body => .confirm,
                .confirm, .cancel => .subject,
            },
        };
    }
};

const VerticalDir = enum { up, down };
const ArrowDir = enum { up, down, left, right };

/// Default terminal colors; use SGR attributes only for hierarchy/focus.
const ui_style = struct {
    const border = struct {
        fn normal() Cell.Style {
            return .{};
        }
        fn focused() Cell.Style {
            return .{ .bold = true };
        }
    };

    const muted = Cell.Style{ .dim = true };
    const button_focus = Cell.Style{ .reverse = true };
};

const HitRect = struct {
    x: u16,
    y: u16,
    w: u16,
    h: u16,

    fn contains(self: HitRect, col: i16, row: i16) bool {
        if (self.w == 0 or self.h == 0) return false;
        if (col < 0 or row < 0) return false;
        const c: u16 = @intCast(col);
        const r: u16 = @intCast(row);
        return c >= self.x and c < self.x + self.w and r >= self.y and r < self.y + self.h;
    }
};

const LayoutMode = enum {
    full,
    no_body,
    no_buttons,
    too_small,
};

const LayoutDims = struct {
    subject_top: u16 = 1,
    subject_h: u16 = 3,
    field_x: u16 = 2,
    field_pad_right: u16 = 2,
    button_w: u16 = 22,
    button_h: u16 = 3,
    button_gap: u16 = 4,

    fn buttonsTotal(self: LayoutDims) u16 {
        return self.button_w * 2 + self.button_gap;
    }

    fn bodyTop(self: LayoutDims) u16 {
        return self.subject_top + self.subject_h + 1;
    }

    fn minPanelWForSubject(self: LayoutDims) u16 {
        return self.field_x + 1 + self.field_pad_right;
    }

    /// Subject rows + one footer row (panel-local row index `ph - 1`).
    fn minPanelHForSubject(self: LayoutDims) u16 {
        return self.subject_top + self.subject_h + 1;
    }

    /// Buttons at `btn_row..btn_row+2`, footer at `ph - 1` → need `btn_row + 2 < ph`.
    fn buttonsFitHeight(self: LayoutDims, ph: u16, btn_row: u16) bool {
        return btn_row + self.button_h <= ph;
    }
};

const layout_dims: LayoutDims = .{};

const ComputedLayout = struct {
    mode: LayoutMode,
    subject: HitRect,
    body: HitRect,
    confirm: HitRect,
    cancel: HitRect,
    field_w: u16,
    body_top: u16,
    body_h: u16,
    btn_row: u16,
    buttons_x: u16,
    frame_x: u16,
    frame_y: u16,
    frame_w: u16,
    frame_h: u16,

    fn compute(term_w: u16, term_h: u16) ComputedLayout {
        if (term_w == 0 or term_h == 0) return .tooSmall();

        const frame = dialog_layout.frameRect(term_w, term_h);
        const panel_x: u16 = frame.x + 1;
        const panel_y: u16 = frame.y + 1;
        const pw: u16 = if (frame.w > 2) frame.w - 2 else 1;
        const ph: u16 = if (frame.h > 2) frame.h - 2 else 1;
        const field_w: u16 = if (pw > layout_dims.field_x + layout_dims.field_pad_right)
            pw - layout_dims.field_x - layout_dims.field_pad_right
        else
            1;

        if (pw < layout_dims.minPanelWForSubject() or ph < layout_dims.minPanelHForSubject()) {
            return .tooSmall();
        }

        const buttons_wide = pw >= layout_dims.buttonsTotal();
        const full_btn_row = if (ph > 4) ph - 4 else 0;
        const compact_btn_row = layout_dims.bodyTop();
        const full_body_h: u16 = if (full_btn_row > layout_dims.bodyTop() + 1)
            full_btn_row - layout_dims.bodyTop() - 1
        else
            0;

        const show_body = buttons_wide and
            full_body_h >= 1 and
            layout_dims.buttonsFitHeight(ph, full_btn_row);
        const show_buttons = if (show_body)
            true
        else
            buttons_wide and layout_dims.buttonsFitHeight(ph, compact_btn_row);

        const mode: LayoutMode = if (show_body)
            .full
        else if (show_buttons)
            .no_body
        else
            .no_buttons;

        const btn_row: u16 = if (show_body) full_btn_row else if (show_buttons) compact_btn_row else 0;
        const body_h: u16 = if (show_body) full_body_h else 0;
        const buttons_x: u16 = if (pw > layout_dims.buttonsTotal())
            (pw - layout_dims.buttonsTotal()) / 2
        else
            0;

        const subject = hitRect(
            panel_x,
            panel_y,
            layout_dims.field_x,
            layout_dims.subject_top,
            field_w,
            layout_dims.subject_h,
        );
        const body = if (show_body)
            hitRect(panel_x, panel_y, layout_dims.field_x, layout_dims.bodyTop(), field_w, body_h)
        else
            HitRect{ .x = 0, .y = 0, .w = 0, .h = 0 };
        const confirm = if (show_buttons)
            hitRect(panel_x, panel_y, buttons_x, btn_row, layout_dims.button_w, layout_dims.button_h)
        else
            HitRect{ .x = 0, .y = 0, .w = 0, .h = 0 };
        const cancel = if (show_buttons)
            hitRect(
                panel_x,
                panel_y,
                buttons_x + layout_dims.button_w + layout_dims.button_gap,
                btn_row,
                layout_dims.button_w,
                layout_dims.button_h,
            )
        else
            HitRect{ .x = 0, .y = 0, .w = 0, .h = 0 };

        return .{
            .mode = mode,
            .subject = subject,
            .body = body,
            .confirm = confirm,
            .cancel = cancel,
            .field_w = field_w,
            .body_top = layout_dims.bodyTop(),
            .body_h = body_h,
            .btn_row = btn_row,
            .buttons_x = buttons_x,
            .frame_x = frame.x,
            .frame_y = frame.y,
            .frame_w = frame.w,
            .frame_h = frame.h,
        };
    }

    fn tooSmall() ComputedLayout {
        return .{
            .mode = .too_small,
            .subject = .{ .x = 0, .y = 0, .w = 0, .h = 0 },
            .body = .{ .x = 0, .y = 0, .w = 0, .h = 0 },
            .confirm = .{ .x = 0, .y = 0, .w = 0, .h = 0 },
            .cancel = .{ .x = 0, .y = 0, .w = 0, .h = 0 },
            .field_w = 0,
            .body_top = 0,
            .body_h = 0,
            .btn_row = 0,
            .buttons_x = 0,
            .frame_x = 0,
            .frame_y = 0,
            .frame_w = 0,
            .frame_h = 0,
        };
    }

    fn showsBody(self: ComputedLayout) bool {
        return self.mode == .full;
    }

    fn showsButtons(self: ComputedLayout) bool {
        return self.mode == .full or self.mode == .no_body;
    }

    fn focusCycle(self: ComputedLayout, focus: Focus, reverse: bool) Focus {
        const order = switch (self.mode) {
            .full => &[_]Focus{ .subject, .body, .confirm, .cancel },
            .no_body => &[_]Focus{ .subject, .confirm, .cancel },
            .no_buttons, .too_small => &[_]Focus{ .subject},
        };
        var i: usize = 0;
        while (i < order.len) : (i += 1) {
            if (order[i] == focus) {
                if (reverse) return if (i == 0) order[order.len - 1] else order[i - 1];
                return if (i + 1 >= order.len) order[0] else order[i + 1];
            }
        }
        return order[0];
    }

    fn clampFocus(self: ComputedLayout, focus: Focus) Focus {
        return switch (self.mode) {
            .full => focus,
            .no_body => switch (focus) {
                .body => .subject,
                else => focus,
            },
            .no_buttons, .too_small => .subject,
        };
    }

    fn moveFocusVertical(self: ComputedLayout, focus: Focus, dir: VerticalDir) Focus {
        return switch (self.mode) {
            .full => focus.moveFocusVertical(dir),
            .no_body => switch (dir) {
                .up => switch (focus) {
                    .subject => .cancel,
                    .confirm, .cancel => .subject,
                    else => focus,
                },
                .down => switch (focus) {
                    .subject => .confirm,
                    .confirm, .cancel => .subject,
                    else => focus,
                },
            },
            .no_buttons, .too_small => focus,
        };
    }

    fn enterFromSubject(self: ComputedLayout) Focus {
        return switch (self.mode) {
            .full => .body,
            .no_body => .confirm,
            .no_buttons, .too_small => .subject,
        };
    }

    fn hitRect(px: u16, py: u16, x: u16, y: u16, w: u16, h: u16) HitRect {
        return .{ .x = px + x, .y = py + y, .w = w, .h = h };
    }
};

/// Below max size the dialog fills the terminal; above max it caps and centers.
const DialogLayout = struct {
    max_w: u16 = 80,
    /// Derived from `max_w` via golden ratio (see `goldenMaxHeight`).
    max_h: u16 = goldenMaxHeight(80),

    fn frameRect(self: DialogLayout, term_w: u16, term_h: u16) struct { x: u16, y: u16, w: u16, h: u16 } {
        const w = @min(term_w, self.max_w);
        const h = @min(term_h, self.max_h);
        return .{
            .x = if (term_w > w) (term_w - w) / 2 else 0,
            .y = if (term_h > h) (term_h - h) / 2 else 0,
            .w = @max(@as(u16, 1), w),
            .h = @max(@as(u16, 1), h),
        };
    }
};

/// φ = (1 + √5) / 2. Terminal glyphs are ~2× taller than wide, so a visually
/// golden landscape box with width `max_w` columns has row budget ≈ max_w / (2φ).
/// One minor golden cut — divide by (φ + 1) = φ² — keeps the dialog from feeling too tall:
///   max_h ≈ max_w / (2φ²) ≈ 15 (too tight)
/// Use the equivalent closed form max_w / (φ² + 1) = max_w / (φ + 2) ≈ 22 for width 80.
fn goldenMaxHeight(max_w: u16) u16 {
    const phi: f64 = (1.0 + @sqrt(5.0)) / 2.0;
    const w = @as(f64, @floatFromInt(max_w));
    const h = w / (phi * phi + 1.0);
    const min_h: u16 = 13; // smallest frame that still fits body + buttons
    return @max(min_h, @as(u16, @intFromFloat(@round(h))));
}

const dialog_layout: DialogLayout = .{};

const MouseAction = union(enum) {
    none,
    focus: Focus,
    save,
    cancel,
};

const Event = union(enum) {
    key_press: vaxis.Key,
    mouse: vaxis.Mouse,
    winsize: vaxis.Winsize,
};

pub fn run(
    alloc: std.mem.Allocator,
    io: std.Io,
    environ_map: *std.process.Environ.Map,
    path: []const u8,
) !Result {
    try tty_attach.attachStdioToTty(io);

    const original_raw = try commit.readMessageFileRaw(alloc, io, path);
    defer alloc.free(original_raw);

    const parsed = try commit.parseMessage(alloc, original_raw);
    defer {
        alloc.free(parsed.subject);
        alloc.free(parsed.body);
    }

    var buffer: [1024]u8 = undefined;
    var tty = vaxis.Tty.init(io, &buffer) catch return tty_attach.AttachError.NoTty;
    defer tty.deinit();

    const writer = tty.writer();

    var vx = try vaxis.init(io, alloc, environ_map, .{
        .kitty_keyboard_flags = if (isAppleTerminal(environ_map))
            .{}
        else
            .{ .report_events = true },
    });
    defer vx.deinit(alloc, tty.writer());

    var loop: vaxis.Loop(Event) = .init(io, &tty, &vx);
    try loop.start();
    defer loop.stop();

    try vx.enterAltScreen(writer);
    try vx.queryTerminal(tty.writer(), .fromSeconds(1));
    applyTerminalCompat(&vx, environ_map);
    if (!vx.state.in_band_resize) try loop.installResizeHandler();
    // Cell-based mouse reporting: reliable hit testing; vxfw disables pixel mode for the same reason.
    vx.caps.sgr_pixels = false;
    try vx.setMouseMode(writer, true);

    // vaxis starts at 0×0 until resize; some terminal emulators may not emit winsize before first draw.
    try applyTerminalSize(alloc, &vx, &tty, writer, readTerminalSize(&tty));

    var subject_input = TextInput.init(alloc);
    defer subject_input.deinit();
    try subject_input.insertSliceAtCursor(parsed.subject);

    var body_input: MultiLineInput = .{};
    defer body_input.deinit(alloc);
    try body_input.setContent(alloc, parsed.body);

    var focus: Focus = .subject;
    const ui = locale.messages(locale.detect(environ_map)).ui;

    const render = struct {
        fn do(
            vx_ptr: *vaxis.Vaxis,
            writer_ptr: *std.Io.Writer,
            focus_val: Focus,
            strings: locale.Strings,
            subject: *TextInput,
            body: *MultiLineInput,
        ) !void {
            draw(vx_ptr, focus_val, strings, subject, body);
            try vx_ptr.render(writer_ptr);
            try writer_ptr.flush();
        }
    }.do;

    try render(&vx, writer, focus, ui, &subject_input, &body_input);

    while (true) {
        const event = try loop.nextEvent();
        const layout = ComputedLayout.compute(vx.window().width, vx.window().height);
        switch (event) {
            .key_press => |key| {
                if (shouldSave(key)) {
                    try saveMessage(alloc, io, path, &subject_input, &body_input);
                    return .saved;
                }
                if (shouldCancel(key)) {
                    return try cancelCommit(io, path, original_raw);
                }

                if (tabDirection(key)) |reverse| {
                    focus = layout.focusCycle(focus, reverse);
                } else if (focus.isButton()) {
                    if (!layout.showsButtons()) {
                        focus = .subject;
                    } else if (arrowDirection(key)) |dir| {
                        focus = switch (dir) {
                            .left => if (focus == .cancel) .confirm else focus,
                            .right => if (focus == .confirm) .cancel else focus,
                            .up => layout.moveFocusVertical(focus, .up),
                            .down => layout.moveFocusVertical(focus, .down),
                        };
                    } else if (key.matches(vaxis.Key.enter, .{}) or key.matches(' ', .{})) {
                        if (focus == .confirm) {
                            try saveMessage(alloc, io, path, &subject_input, &body_input);
                            return .saved;
                        }
                        return try cancelCommit(io, path, original_raw);
                    }
                } else switch (focus) {
                    .subject => {
                        if (key.matches(vaxis.Key.enter, .{})) {
                            focus = layout.enterFromSubject();
                        } else {
                            try subject_input.update(.{ .key_press = key });
                        }
                    },
                    .body => {
                        if (layout.showsBody()) {
                            try body_input.update(alloc, key);
                        } else {
                            focus = .subject;
                        }
                    },
                    .confirm, .cancel => {},
                }
            },
            .mouse => |mouse| {
                switch (handleMouseClick(&vx, mouse)) {
                    .none => {},
                    .focus => |next| focus = next,
                    .save => {
                        try saveMessage(alloc, io, path, &subject_input, &body_input);
                        return .saved;
                    },
                    .cancel => return try cancelCommit(io, path, original_raw),
                }
            },
            .winsize => |ws| try applyTerminalSize(alloc, &vx, &tty, writer, ws),
        }

        focus = layout.clampFocus(focus);
        try render(&vx, writer, focus, ui, &subject_input, &body_input);
    }
}

fn handleMouseClick(vx: *vaxis.Vaxis, mouse: vaxis.Mouse) MouseAction {
    if (mouse.button != .left) return .none;
    // Accept press or release: some macOS trackpad/terminal combos report one or the other.
    if (mouse.type != .press and mouse.type != .release) return .none;

    const win = vx.window();
    const layout = ComputedLayout.compute(win.width, win.height);
    if (layout.mode == .too_small) return .none;

    if (layout.confirm.contains(mouse.col, mouse.row)) return .save;
    if (layout.cancel.contains(mouse.col, mouse.row)) return .cancel;
    if (layout.subject.contains(mouse.col, mouse.row)) return .{ .focus = .subject };
    if (layout.body.contains(mouse.col, mouse.row)) return .{ .focus = .body };
    return .none;
}

fn readTerminalSize(tty: *vaxis.Tty) vaxis.Winsize {
    return normalizeWinsize(tty.getWinsize() catch .{
        .rows = 24,
        .cols = 80,
        .x_pixel = 0,
        .y_pixel = 0,
    });
}

fn normalizeWinsize(ws: vaxis.Winsize) vaxis.Winsize {
    return .{
        .rows = if (ws.rows > 0) ws.rows else 24,
        .cols = if (ws.cols > 0) ws.cols else 80,
        .x_pixel = ws.x_pixel,
        .y_pixel = ws.y_pixel,
    };
}

fn applyTerminalSize(
    alloc: std.mem.Allocator,
    vx: *vaxis.Vaxis,
    tty: *vaxis.Tty,
    writer: *std.Io.Writer,
    ws: vaxis.Winsize,
) !void {
    var effective = normalizeWinsize(ws);
    if (ws.rows == 0 or ws.cols == 0) effective = readTerminalSize(tty);
    try vx.resize(alloc, writer, effective);
}

fn shouldSave(key: vaxis.Key) bool {
    if (key.matches('s', .{ .ctrl = true })) return true;
    if (key.matches(vaxis.Key.enter, .{ .ctrl = true })) return true;
    if (key.matches('j', .{ .ctrl = true })) return true;
    return false;
}

fn shouldCancel(key: vaxis.Key) bool {
    if (key.matches('c', .{ .ctrl = true })) return true;
    if (key.matches(vaxis.Key.escape, .{})) return true;
    return false;
}

fn saveMessage(
    alloc: std.mem.Allocator,
    io: std.Io,
    path: []const u8,
    subject_input: *TextInput,
    body_input: *MultiLineInput,
) !void {
    var scratch: [4096]u8 = undefined;
    const subject = copySubject(subject_input, &scratch);
    try commit.writeMessageFile(alloc, io, path, subject, body_input.bytes());
}

/// Restore COMMIT_EDITMSG to what git originally opened (vim `:q!` semantics).
fn cancelCommit(io: std.Io, path: []const u8, original_raw: []const u8) !Result {
    try commit.restoreMessageFile(io, path, original_raw);
    return .cancelled;
}

/// macOS Terminal.app misreports xterm explicit-width during capability probes.
/// vaxis then emits OSC 66 for CJK, which Terminal.app does not render.
fn isAppleTerminal(environ_map: *std.process.Environ.Map) bool {
    const term_program = environ_map.get("TERM_PROGRAM") orelse return false;
    return std.mem.eql(u8, term_program, "Apple_Terminal");
}

fn applyTerminalCompat(vx: *vaxis.Vaxis, environ_map: *std.process.Environ.Map) void {
    if (!isAppleTerminal(environ_map)) return;

    vx.caps.explicit_width = false;
    vx.caps.scaled_text = false;
    vx.caps.kitty_keyboard = false;
    vx.caps.unicode = .wcwidth;
    vx.screen.width_method = .wcwidth;
    vx.sgr = .legacy;
}

fn draw(
    vx: *vaxis.Vaxis,
    focus: Focus,
    ui: locale.Strings,
    subject_input: *TextInput,
    body_input: *MultiLineInput,
) void {
    const win = vx.window();
    win.clear();

    const layout = ComputedLayout.compute(win.width, win.height);
    if (layout.mode == .too_small) {
        drawTooSmallHint(win, ui.terminal_too_small);
        return;
    }

    const panel = win.child(.{
        .x_off = layout.frame_x,
        .y_off = layout.frame_y,
        .width = layout.frame_w,
        .height = layout.frame_h,
        .border = .{
            .where = .all,
            .style = ui_style.border.focused(),
        },
    });

    const ph = panel.height;

    const subject_box = panel.child(.{
        .x_off = layout_dims.field_x,
        .y_off = layout_dims.subject_top,
        .width = layout.field_w,
        .height = layout_dims.subject_h,
        .border = .{
            .where = .all,
            .style = if (focus == .subject) ui_style.border.focused() else ui_style.border.normal(),
        },
    });
    drawSubjectInput(subject_box, subject_input, focus == .subject, ui.subject_placeholder);

    if (layout.showsBody()) {
        const body_box = panel.child(.{
            .x_off = layout_dims.field_x,
            .y_off = layout.body_top,
            .width = layout.field_w,
            .height = layout.body_h,
            .border = .{
                .where = .all,
                .style = if (focus == .body) ui_style.border.focused() else ui_style.border.normal(),
            },
        });
        body_input.draw(body_box, focus == .body, ui.body_placeholder);
    }

    if (layout.showsButtons()) {
        drawButton(
            panel,
            layout.buttons_x,
            layout.btn_row,
            layout_dims.button_w,
            ui.confirm_button,
            focus == .confirm,
        );
        drawButton(
            panel,
            layout.buttons_x + layout_dims.button_w + layout_dims.button_gap,
            layout.btn_row,
            layout_dims.button_w,
            ui.cancel_button,
            focus == .cancel,
        );
    }

    if (ph > 0) {
        printAt(panel, ph - 1, 2, ui.footer_hint, ui_style.muted);
    }

    if (focus.isButton()) win.hideCursor();
}

fn drawSubjectInput(
    box: vaxis.Window,
    input: *TextInput,
    focused: bool,
    placeholder: []const u8,
) void {
    // TextInput only ever increases draw_offset; after a narrow resize it stays
    // too large and the field shows only ellipses until we recalculate from zero.
    input.draw_offset = 0;
    input.draw(box);
    if (!focused) box.hideCursor();
    if (focused or !subjectIsEmpty(input)) return;
    printAt(box, 0, 0, placeholder, placeholderStyle());
}

fn subjectIsEmpty(input: *const TextInput) bool {
    return input.buf.firstHalf().len + input.buf.secondHalf().len == 0;
}

fn placeholderStyle() Cell.Style {
    return ui_style.muted;
}

fn drawTooSmallHint(win: vaxis.Window, message: []const u8) void {
    win.hideCursor();
    const row: u16 = if (win.height > 0) win.height / 2 else 0;
    const text_w = win.gwidth(message);
    const col: u16 = if (win.width > text_w) (win.width - text_w) / 2 else 0;
    printAt(win, row, col, message, ui_style.border.focused());
}

fn drawButton(
    panel: vaxis.Window,
    x: u16,
    y: u16,
    width: u16,
    text: []const u8,
    focused: bool,
) void {
    if (width < 4 or y + 3 > panel.height or x + width > panel.width) return;

    const border_style = if (focused) ui_style.border.focused() else ui_style.border.normal();
    const text_style: Cell.Style = if (focused) ui_style.button_focus else .{};

    drawRectBorder(panel, x, y, width, 3, border_style);

    const inner_x = x + 1;
    const inner_y = y + 1;
    const inner_w = width - 2;
    const text_w = panel.gwidth(text);
    const start_col: u16 = inner_x + if (text_w > 0 and text_w <= inner_w) (inner_w - text_w) / 2 else 0;
    printAt(panel, inner_y, start_col, text, text_style);
}

fn drawRectBorder(panel: vaxis.Window, x: u16, y: u16, w: u16, h: u16, style: Cell.Style) void {
    if (w < 2 or h < 2) return;
    if (x + w > panel.width or y + h > panel.height) return;

    const tl: Cell.Character = .{ .grapheme = "┌", .width = 1 };
    const tr: Cell.Character = .{ .grapheme = "┐", .width = 1 };
    const bl: Cell.Character = .{ .grapheme = "└", .width = 1 };
    const br: Cell.Character = .{ .grapheme = "┘", .width = 1 };
    const hz: Cell.Character = .{ .grapheme = "─", .width = 1 };
    const vt: Cell.Character = .{ .grapheme = "│", .width = 1 };

    panel.writeCell(x, y, .{ .char = tl, .style = style });
    panel.writeCell(x + w - 1, y, .{ .char = tr, .style = style });
    panel.writeCell(x, y + h - 1, .{ .char = bl, .style = style });
    panel.writeCell(x + w - 1, y + h - 1, .{ .char = br, .style = style });

    var c: u16 = 1;
    while (c + 1 < w) : (c += 1) {
        panel.writeCell(x + c, y, .{ .char = hz, .style = style });
        panel.writeCell(x + c, y + h - 1, .{ .char = hz, .style = style });
    }
    var r: u16 = 1;
    while (r + 1 < h) : (r += 1) {
        panel.writeCell(x, y + r, .{ .char = vt, .style = style });
        panel.writeCell(x + w - 1, y + r, .{ .char = vt, .style = style });
    }
}

fn arrowDirection(key: vaxis.Key) ?ArrowDir {
    if (key.matches(vaxis.Key.up, .{}) or key.matches(vaxis.Key.kp_up, .{})) return .up;
    if (key.matches(vaxis.Key.down, .{}) or key.matches(vaxis.Key.kp_down, .{})) return .down;
    if (key.matches(vaxis.Key.left, .{}) or key.matches(vaxis.Key.kp_left, .{})) return .left;
    if (key.matches(vaxis.Key.right, .{}) or key.matches(vaxis.Key.kp_right, .{})) return .right;
    return null;
}

fn tabDirection(key: vaxis.Key) ?bool {
    if (key.matches(vaxis.Key.tab, .{ .shift = true })) return true;
    if (key.matches(vaxis.Key.tab, .{})) return false;
    if (key.text) |text| {
        if (std.mem.eql(u8, text, "\t")) return key.mods.shift;
    }
    return null;
}

fn printAt(win: vaxis.Window, row: u16, col: u16, text: []const u8, style: Cell.Style) void {
    if (row >= win.height) return;
    _ = win.print(&.{.{ .text = text, .style = style }}, .{
        .row_offset = row,
        .col_offset = col,
        .wrap = .none,
    });
}

fn copySubject(input: *TextInput, scratch: []u8) []const u8 {
    const first = input.buf.firstHalf();
    const second = input.buf.secondHalf();
    const total = first.len + second.len;
    std.debug.assert(total <= scratch.len);
    @memcpy(scratch[0..first.len], first);
    @memcpy(scratch[first.len..total], second);
    return scratch[0..total];
}

test "mouse hit regions align with dialog layout" {
    const layout = ComputedLayout.compute(84, 30);
    try std.testing.expectEqual(LayoutMode.full, layout.mode);
    try std.testing.expect(layout.subject.contains(@intCast(layout.subject.x), @intCast(layout.subject.y)));
    try std.testing.expect(layout.confirm.contains(@intCast(layout.confirm.x + 1), @intCast(layout.confirm.y + 1)));
    try std.testing.expect(!layout.subject.contains(@intCast(layout.confirm.x + 1), @intCast(layout.confirm.y + 1)));
}

test "apple terminal detection" {
    var map = try std.testing.environ.createMap(std.testing.allocator);
    defer map.deinit();
    try map.put("TERM_PROGRAM", "Apple_Terminal");
    try std.testing.expect(isAppleTerminal(&map));
    try map.put("TERM_PROGRAM", "ghostty");
    try std.testing.expect(!isAppleTerminal(&map));
}

test "layout degrades as terminal shrinks" {
    const full = ComputedLayout.compute(80, 24);
    try std.testing.expectEqual(LayoutMode.full, full.mode);
    try std.testing.expect(full.showsBody());
    try std.testing.expect(full.showsButtons());

    const no_body = ComputedLayout.compute(80, 10);
    try std.testing.expectEqual(LayoutMode.no_body, no_body.mode);
    try std.testing.expect(!no_body.showsBody());
    try std.testing.expect(no_body.showsButtons());

    const no_buttons = ComputedLayout.compute(40, 10);
    try std.testing.expectEqual(LayoutMode.no_buttons, no_buttons.mode);
    try std.testing.expect(!no_buttons.showsButtons());

    const tiny = ComputedLayout.compute(4, 4);
    try std.testing.expectEqual(LayoutMode.too_small, tiny.mode);
}

test "focus cycle respects layout mode" {
    const full = ComputedLayout.compute(80, 24);
    try std.testing.expectEqual(Focus.body, full.focusCycle(.subject, false));
    try std.testing.expectEqual(Focus.subject, full.focusCycle(.cancel, false));

    const compact = ComputedLayout.compute(80, 10);
    try std.testing.expectEqual(Focus.confirm, compact.focusCycle(.subject, false));
    try std.testing.expectEqual(Focus.subject, compact.clampFocus(.body));
}

test "golden max dialog height" {
    try std.testing.expectEqual(@as(u16, 22), goldenMaxHeight(80));
    try std.testing.expectEqual(dialog_layout.max_h, goldenMaxHeight(dialog_layout.max_w));
}

test "dialog frame caps and centers on large terminals" {
    const frame = dialog_layout.frameRect(120, 40);
    try std.testing.expectEqual(@as(u16, 80), frame.w);
    try std.testing.expectEqual(@as(u16, 22), frame.h);
    try std.testing.expectEqual(@as(u16, 20), frame.x);
    try std.testing.expectEqual(@as(u16, 9), frame.y);

    const layout = ComputedLayout.compute(120, 40);
    try std.testing.expectEqual(LayoutMode.full, layout.mode);
    try std.testing.expectEqual(@as(u16, 80), layout.frame_w);
    try std.testing.expectEqual(@as(u16, 10), layout.body_h);
}

test "dialog fills terminal below max size" {
    const frame = dialog_layout.frameRect(80, 24);
    try std.testing.expectEqual(@as(u16, 80), frame.w);
    try std.testing.expectEqual(@as(u16, 22), frame.h);
    try std.testing.expectEqual(@as(u16, 0), frame.x);
    try std.testing.expectEqual(@as(u16, 1), frame.y);

    const short = dialog_layout.frameRect(80, 18);
    try std.testing.expectEqual(@as(u16, 18), short.h);
    try std.testing.expectEqual(@as(u16, 0), short.x);
}
