#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

zig build
zig build test
python3 "$ROOT/scripts/tui-smoke-test.py"

if [[ "${RUN_GHOSTTY_WINDOW:-}" == "1" ]]; then
  echo "Opening Ghostty for manual visual check (close window when done)..."
  open -na Ghostty.app --args -e bash -lc \
    "cd '$ROOT' && ./zig-out/bin/gitdlg '${TMPDIR:-/tmp}/gitdlg-smoke/COMMIT_EDITMSG' || true; echo; echo 'Smoke UI loaded. Press Esc to cancel.'; read -n 1"
fi

echo "smoke tests passed"
