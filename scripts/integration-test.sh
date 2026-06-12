#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

zig build
zig build test

BIN="$ROOT/zig-out/bin/gitdlg"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cd "$WORK"
git init -q
git config user.email "gitdlg@test.local"
git config user.name "gitdlg test"

echo "sample" > file.txt
git add file.txt
git commit -q -m "bootstrap"

echo "updated" >> file.txt
git add file.txt

MSG_FILE="$WORK/.git/COMMIT_EDITMSG"
cat > "$MSG_FILE" <<'EOF'
# Please enter the commit message for your changes.
#
feat: gitdlg integration

Body line for integration test.
EOF

"$BIN" --batch-save "$MSG_FILE"
git commit -F "$MSG_FILE"

test "$(git log -1 --pretty=%s)" = "feat: gitdlg integration"
test "$(git log -1 --pretty=%b | tr -d '\r')" = "Body line for integration test."

echo "integration test passed"
