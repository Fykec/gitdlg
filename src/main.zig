const std = @import("std");
const gitdlg = @import("gitdlg");

pub const std_options: std.Options = .{
    .log_level = .warn,
};

pub fn main(init: std.process.Init) !u8 {
    const io = init.io;
    const alloc = init.gpa;
    const arena_alloc = init.arena.allocator();
    const msg = gitdlg.locale.messages(gitdlg.locale.detect(init.environ_map));

    const args = try init.minimal.args.toSlice(arena_alloc);
    if (args.len < 2) {
        try printErr(io, msg.usage);
        return 1;
    }

    if (std.mem.eql(u8, args[1], "--help") or std.mem.eql(u8, args[1], "-h")) {
        try printErr(io, msg.usage);
        return 0;
    }

    if (std.mem.eql(u8, args[1], "--batch-save")) {
        const batch_path = if (args.len > 2) args[2] else {
            try printErr(io, "error: --batch-save requires a file path\n");
            return 1;
        };
        const parsed = try gitdlg.commit.readMessageFile(alloc, io, batch_path);
        defer {
            alloc.free(parsed.subject);
            alloc.free(parsed.body);
        }
        try gitdlg.commit.writeMessageFile(alloc, io, batch_path, parsed.subject, parsed.body);
        return 0;
    }

    const path = gitdlg.commit.findMessagePath(args) orelse {
        try printErr(io, "error: missing commit message file path\n");
        return 1;
    };

    const result = gitdlg.editor.run(alloc, io, init.environ_map, path) catch |err| {
        switch (err) {
            gitdlg.tty_attach.AttachError.NoTty => {
                try printErr(io, msg.no_tty);
                return 1;
            },
            error.FileNotFound => {
                try printErr(io, "error: file not found: ");
                try printErr(io, path);
                try printErr(io, "\n");
                return 1;
            },
            else => |e| {
                try printErr(io, "error: ");
                try printErr(io, @errorName(e));
                try printErr(io, ": ");
                try printErr(io, path);
                try printErr(io, "\n");
                return 1;
            },
        }
    };

    return switch (result) {
        .saved => 0,
        .cancelled => 0,
    };
}

fn printErr(io: std.Io, msg: []const u8) !void {
    var buffer: [512]u8 = undefined;
    var stderr_writer: std.Io.File.Writer = .init(.stderr(), io, &buffer);
    try stderr_writer.interface.print("{s}", .{msg});
    try stderr_writer.interface.flush();
}
