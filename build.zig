const std = @import("std");
const builtin = @import("builtin");

comptime {
    const current = builtin.zig_version;
    const min = std.SemanticVersion{ .major = 0, .minor = 16, .patch = 0 };
    if (current.order(min) == .lt) {
        @compileError(std.fmt.comptimePrint(
            "gitdlg requires Zig >= 0.16.0 (detected {}.{}).\n" ++
            "Install zig 0.16: curl -fsSL https://ziglang.org/download/0.16.0/zig-linux-x86_64-0.16.0.tar.xz | tar xJ",
            .{ current.major, current.minor },
        ));
    }
}

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const vaxis_dep = b.dependency("vaxis", .{
        .target = target,
        .optimize = optimize,
    });

    const mod = b.createModule(.{
        .root_source_file = b.path("src/root.zig"),
        .target = target,
        .optimize = optimize,
        .imports = &.{
            .{ .name = "vaxis", .module = vaxis_dep.module("vaxis") },
        },
    });

    const exe = b.addExecutable(.{
        .name = "gitdlg",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
            .imports = &.{
                .{ .name = "gitdlg", .module = mod },
                .{ .name = "vaxis", .module = vaxis_dep.module("vaxis") },
            },
        }),
    });
    b.installArtifact(exe);

    const run_step = b.step("run", "Run gitdlg");
    const run_cmd = b.addRunArtifact(exe);
    run_step.dependOn(&run_cmd.step);
    run_cmd.step.dependOn(b.getInstallStep());
    if (b.args) |args| run_cmd.addArgs(args);

    const tests = b.addTest(.{ .root_module = mod });
    const run_tests = b.addRunArtifact(tests);
    const test_step = b.step("test", "Run unit tests");
    test_step.dependOn(&run_tests.step);
}
