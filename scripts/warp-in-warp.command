#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export TERM_PROGRAM=WarpTerminal
export LANG="${LANG:-zh_CN.UTF-8}"
echo "=== gitdlg Warp self-test ==="
python3 scripts/warp-garbage-test.py
echo
echo "Manual check: run in this Warp window:"
echo "  GIT_EDITOR=\"python3 $ROOT/gitdlg.py\" git commit"
echo "Subject should stay empty until you type."
