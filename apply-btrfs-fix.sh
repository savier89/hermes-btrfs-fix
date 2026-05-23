#!/usr/bin/env bash
# Apply BTRFS + SQLite WAL fix after hermes update
# Usage: ./apply-btrfs-fix.sh

set -euo pipefail

PATCH_FILE="$HOME/.hermes/patches/btrfs-sqlite-fix.patch"
HERMES_DIR="$HOME/.hermes/hermes-agent"
STATE_FILE="$HERMES_DIR/hermes_state.py"
TERMINAL_FILE="$HERMES_DIR/tools/terminal_tool.py"

# Check if patch file exists
if [[ ! -f "$PATCH_FILE" ]]; then
    echo "ERROR: Patch file not found: $PATCH_FILE"
    exit 1
fi

# Check if our patch is already applied (v3 markers)
if grep -q "_WAL_TRANSIENT_MARKERS" "$STATE_FILE" 2>/dev/null; then
    echo "OK: BTRFS fix (v3) already applied — skipping."
    exit 0
fi

# Check if old patch is applied (v1/v2 markers)
if grep -q "_is_on_btrfs" "$STATE_FILE" 2>/dev/null; then
    echo "WARN: Old BTRFS fix (v1/v2) detected. Removing and applying v3..."
    # Revert old changes before applying new patch
    git -C "$HERMES_DIR" checkout -- "$STATE_FILE" "$TERMINAL_FILE" 2>/dev/null || true
fi

# Check if upstream already has the fix (PR #30700 merged)
if grep -q "_WAL_SETUP_MAX_ATTEMPTS" "$STATE_FILE" 2>/dev/null; then
    echo "OK: Official fix already present in upstream — skipping."
    exit 0
fi

# Apply the patch
echo "Applying BTRFS + SQLite WAL fix (v3)..."
if git -C "$HERMES_DIR" am "$PATCH_FILE" 2>/dev/null; then
    echo "DONE: Patch applied successfully via git am."
else
    echo "WARN: git am failed, trying patch directly..."
    if patch -p1 -d "$HERMES_DIR" < "$PATCH_FILE"; then
        echo "DONE: Patch applied via patch command."
    else
        echo "ERROR: Failed to apply patch."
        exit 1
    fi
fi

# Restart gateway to apply changes
echo "Restarting hermes-gateway..."
systemctl --user restart hermes-gateway 2>/dev/null || echo "WARN: Could not restart gateway"

echo "DONE: BTRFS fix applied and gateway restarted."
