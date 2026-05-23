# Hermes Agent — BTRFS + SQLite WAL Fix (v5)

## Problem

SQLite in WAL mode experiences corruption on filesystems with Copy-on-Write
semantics (BTRFS, ZFS):

```
sqlite3.OperationalError: disk I/O error
PRAGMA integrity_check: Tree 16 page 16 cell 0: 2nd reference to page 77
```

These errors cause silent database corruption — corrupted B-tree indexes,
wrong index entry counts, and gateway crashes.

## Root Cause

- WAL mode relies on shared memory (`-shm` files) and sequential writes
- On BTRFS/ZFS, COW operations cause transient blocking during checkpoint
  races — manifesting as `disk i/O error`
- Under high concurrency (multiple gateway processes), writers compete for
  database locks — manifesting as `database is locked`
- The default SQLite timeout (1ms) is insufficient for these scenarios
- WAL retry logic handles transient errors but cannot fix structural corruption

## Solution (v5)

**Proactive BTRFS detection + protected fallback:**

1. **`_is_on_btrfs()`** — Detects BTRFS via `/proc/self/mountinfo`
2. **Skip WAL on BTRFS** — Force DELETE journal mode from the start
3. **`_WAL_TRANSIENT_MARKERS`** — Distinguishes transient from permanent errors
4. **`_try_fallback_delete()`** — Protected DELETE fallback that doesn't crash
5. **Env var configuration** — `HERMES_SQLITE_BUSY_TIMEOUT`, `HERMES_SQLITE_WAL_RETRIES`, `HERMES_SQLITE_WAL_RETRY_DELAY`

## Testing

- 45 concurrent operations (readers + writers), 0 errors, 0.51s
- `PRAGMA integrity_check` passes after fix
- Kanban dispatcher runs without errors on BTRFS

## Installation

```bash
# Option 1: git am (preferred)
git -C ~/.hermes/hermes-agent am btrfs-sqlite-fix.patch

# Option 2: patch directly
patch -p1 -d ~/.hermes/hermes-agent < btrfs-sqlite-fix.patch
```

## Status

- **Not in upstream** (`NousResearch/hermes-agent`)
- Issue: [#30846](https://github.com/NousResearch/hermes-agent/issues/30846)
- Patch based on: `origin/main` (updated regularly)

## Files Changed

| File | Changes |
|------|---------|
| `hermes_state.py` | `_is_on_btrfs()`, `_WAL_TRANSIENT_MARKERS`, `_try_fallback_delete()`, env vars, proactive BTRFS detection |
| `hermes_cli/kanban_db.py` | Pass `db_path` to `apply_wal_with_fallback()` |
| `tools/terminal_tool.py` | `_safe_getcwd()` helper |
