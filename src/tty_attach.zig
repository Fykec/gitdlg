const std = @import("std");
const posix = std.posix;
const builtin = @import("builtin");

pub const AttachError = error{
    NoTty,
};

/// Git often spawns $GIT_EDITOR without a controlling terminal on stdin.
/// Re-attach stdio to /dev/tty so vaxis can open and read the terminal.
pub fn attachStdioToTty(io: std.Io) AttachError!void {
    if (builtin.os.tag == .windows) return;

    const stdin = std.Io.File.stdin();
    if (stdin.isTty(io) catch false) return;

    var file = std.Io.Dir.openFileAbsolute(io, "/dev/tty", .{ .mode = .read_write }) catch return error.NoTty;
    const tty_fd = file.handle;

    dupFd(tty_fd, posix.STDIN_FILENO) catch return error.NoTty;
    dupFd(tty_fd, posix.STDOUT_FILENO) catch return error.NoTty;
    dupFd(tty_fd, posix.STDERR_FILENO) catch return error.NoTty;

    if (tty_fd > posix.STDERR_FILENO) file.close(io);
}

fn dupFd(old_fd: posix.fd_t, new_fd: posix.fd_t) !void {
    while (true) {
        switch (posix.errno(posix.system.dup2(old_fd, new_fd))) {
            .SUCCESS => return,
            .INTR => continue,
            else => return error.SystemResources,
        }
    }
}
