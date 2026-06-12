#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

zig build
zig build test

python3 "$ROOT/scripts/terminal-app-compat-test.py"

echo "terminal.app compat tests passed"
