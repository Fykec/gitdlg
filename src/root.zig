pub const commit = @import("commit.zig");
pub const locale = @import("locale.zig");
pub const multiline = @import("multiline.zig");
pub const editor = @import("editor.zig");
pub const tty_attach = @import("tty_attach.zig");

test {
    @import("std").testing.refAllDecls(@This());
}
