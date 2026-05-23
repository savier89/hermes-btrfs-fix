#!/usr/bin/env bash
# Apply BTRFS + SQLite WAL fix after hermes update
# Usage: ./apply-btrfs-fix.sh

set -euo pipefail

PATCH_FILE="$HOME/.hermes/patches/btrfs-sqlite-fix.patch"
HERMES_DIR="$HOME/.hermes/hermes-agent"
STATE_FILE="$HERMES_DIR/hermes_state.py"

# Check if patch file exists
if [[ ! -f "$PATCH_FILE" ]]; then
    echo "ERROR: Patch file not found: $PATCH_FILE"
    exit 1
fi

# Check if official fix is already in place
if grep -q "_is_on_btrfs" "$STATE_FILE" 2>/dev/null; then
    echo "OK: Official BTRFS fix already present — skipping."
    exit 0
fi

# Check if our patch is already applied
if git -C "$HERMES_DIR" log --oneline -1 | grep -q "BTRFS COW + SQLite WAL"; then
    echo "OK: Local patch already applied — skipping."
    exit 0
fi

# Apply the patch
echo "Applying BTRFS + SQLite WAL fix..."
if git -C "$HERMES_DIR" am "$PATCH_FILE" 2>/dev/null; then
    echo "DONE: Patch applied successfully."
else
    echo "WARN: git am failed, trying patch directly..."
    if patch -p1 -d "$HERMES_DIR" < "$PATCH_FILE"; then
        echo "DONE: Patch applied via patch command."
    else
        echo "ERROR: Failed to apply patch."
        exit 1
    fi
fi
