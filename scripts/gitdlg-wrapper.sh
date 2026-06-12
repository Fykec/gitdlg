#!/usr/bin/env bash
# Re-attach stdio to the controlling terminal before launching gitdlg.
# Use when Git is started from a GUI without a controlling TTY:
#   git config core.editor /path/to/scripts/gitdlg-wrapper.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/zig-out/bin/gitdlg"

if [ -t 0 ] && [ -t 1 ]; then
  exec "$BIN" "$@"
fi

exec </dev/tty >/dev/tty 2>&1
exec "$BIN" "$@"
