# Hermes Agent — SQLite WAL Retry Fix

## Problem

SQLite in WAL mode can experience transient locking errors under high concurrency
or on filesystems with Copy-on-Write semantics (BTRFS, ZFS):

```
sqlite3.OperationalError: database is locked
sqlite3.OperationalError: disk I/O error
```

These errors occur during WAL initialization (`PRAGMA journal_mode=WAL`) and
write transactions (`BEGIN IMMEDIATE`), causing gateway crashes and stale task
claims.

## Root Cause

- WAL mode relies on shared memory (`-shm` files) and sequential writes
- On BTRFS/ZFS, COW operations can cause transient blocking during checkpoint races
- Under high concurrency, multiple writers compete for database locks
- The default SQLite timeout (1 second) is insufficient for these scenarios
- The existing fallback only handled permanent filesystem incompatibility (NFS/SMB)

## Solution

**Retry logic + increased busy_timeout** for transient WAL setup errors:

1. Set `busy_timeout=30000` (30 seconds) on all connections
2. Retry WAL setup up to 3 times with 1 second delay
3. Fall back to DELETE mode only after exhausting retries
4. Distinguish transient errors (retry) from incompatible filesystems (immediate fallback)

### Configuration

Users can override defaults via environment variables:

```bash
export HERMES_SQLITE_BUSY_TIMEOUT=30000  # milliseconds (default: 30000)
export HERMES_SQLITE_WAL_RETRIES=3       # max attempts (default: 3)
export HERMES_SQLITE_WAL_RETRY_DELAY=1.0 # seconds between attempts (default: 1.0)
```

### Changed Files

- `hermes_state.py` — retry logic + busy_timeout + transient error classification
- `tools/terminal_tool.py` — `_safe_getcwd()` helper (fixes FileNotFoundError)

## Installation

```bash
# Method 1: git am (recommended)
cd ~/.hermes/hermes-agent
git am btrfs-sqlite-fix.patch

# Method 2: automatic check script
bash apply-btrfs-fix.sh
```

## Links

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Issue #30846](https://github.com/NousResearch/hermes-agent/issues/30846)
- [PR #30700](https://github.com/NousResearch/hermes-agent/pull/30700) — related retry approach
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [SQLite Performance on Btrfs](https://wiki.tnonline.net/w/Blog/SQLite_Performance_on_Btrfs)

---

# Hermes Agent — SQLite WAL Retry Fix (RU)

## Проблема

SQLite в WAL mode может испытывать транзентные ошибки блокировки при высокой
конкурентности или на файловых системах с Copy-on-Write (BTRFS, ZFS):

```
sqlite3.OperationalError: database is locked
sqlite3.OperationalError: disk I/O error
```

## Причина

- WAL mode полагается на shared memory и последовательные записи
- На BTRFS/ZFS COW операции вызывают временные блокировки
- При высокой конкурентности писатели конкурируют за блоки
- Дефолтный таймаут SQLite (1 сек) недостаточен

## Решение

**Retry-логика + увеличенный busy_timeout** для транзентных ошибок WAL:

1. `busy_timeout=30000` (30 секунд) для всех соединений
2. До 3 попыток с задержкой 1 секунда
3. Fallback на DELETE только после исчерпания попыток

### Конфигурация

```bash
export HERMES_SQLITE_BUSY_TIMEOUT=30000  # миллисекунды
export HERMES_SQLITE_WAL_RETRIES=3       # макс попыток
export HERMES_SQLITE_WAL_RETRY_DELAY=1.0 # секунды между попытками
```
