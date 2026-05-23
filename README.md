# Hermes Agent — BTRFS + SQLite WAL Fix

## Problem

SQLite in WAL mode on BTRFS filesystems can experience `disk I/O error` due to
BTRFS Copy-on-Write (COW) semantics interacting with concurrent write operations.

```
sqlite3.OperationalError: disk I/O error
```

This leads to corruption of `state.db` and `kanban.db`, gateway crashes, and
stale task claims.

## Root Cause

- WAL mode relies on shared memory (`-shm` files) and sequential writes
- BTRFS COW operations can modify disk blocks after WAL records them
- Without proper `busy_timeout`, concurrent writers block each other indefinitely
- The default SQLite timeout (1000ms) is insufficient for BTRFS COW conflicts

## Solution

**WAL mode + `busy_timeout=5000` + retry logic** — tested and proven to work on
BTRFS (400/400 concurrent operations, 0 errors). Falls back to DELETE mode only
if WAL truly fails.

### Testing

- **System:** Arch Linux, BTRFS (compress=zstd:3, ssd), SQLite 3.53.1
- **Test:** 5 concurrent writers + 3 readers, 50 operations each
- **Result:** 400 operations, 0 errors, 0.50s total
- **Conclusion:** WAL mode works on BTRFS with proper busy_timeout

### Configuration

Users can override the default busy_timeout:

```bash
export HERMES_SQLITE_BUSY_TIMEOUT=10000  # milliseconds
```

### Changed Files

- `hermes_state.py` — `_is_on_btrfs()` detection + WAL with busy_timeout + retry
- `hermes_cli/kanban_db.py` — pass `db_path` for BTRFS detection
- `tools/terminal_tool.py` — `_safe_getcwd()` helper (fixes FileNotFoundError)

## Installation

```bash
# Method 1: git am (recommended)
cd ~/.hermes/hermes-agent
git am btrfs-sqlite-fix.patch

# Method 2: automatic check script
bash apply-btrfs-fix.sh
```

## Automatic Application After Update

```bash
# Add to ~/.bashrc or ~/.zshrc
alias hermes-update='hermes update && ~/.hermes/scripts/apply-btrfs-fix.sh'
```

## Links

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Issue #30846](https://github.com/NousResearch/hermes-agent/issues/30846)
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [SQLite Performance on Btrfs](https://wiki.tnonline.net/w/Blog/SQLite_Performance_on_Btrfs)
- [FreshRSS #3853](https://github.com/FreshRSS/FreshRSS/issues/3853) — similar issue

---

# Hermes Agent — BTRFS + SQLite WAL Fix (RU)

## Проблема

SQLite в WAL mode на файловой системе BTRFS может испытывать ошибки
`disk I/O error` из-за взаимодействия BTRFS Copy-on-Write (COW) семантики
с конкурентными операциями записи.

## Причина

- WAL mode полагается на shared memory (`-shm` файлы) и последовательные записи
- COW операции BTRFS могут изменять блоки диска после записи WAL
- Без правильного `busy_timeout`, конкурентные писатели блокируют друг друга
- Дефолтный таймаут SQLite (1000мс) недостаточен для разрешения конфликтов COW

## Решение

**WAL mode + `busy_timeout=5000` + retry-логика** — протестировано и работает
на BTRFS (400/400 конкурентных операций, 0 ошибок). Fallback на DELETE mode
только если WAL действительно не работает.

### Тестирование

- **Система:** Arch Linux, BTRFS (compress=zstd:3, ssd), SQLite 3.53.1
- **Тест:** 5 писателей + 3 читателя, по 50 операций каждый
- **Результат:** 400 операций, 0 ошибок, 0.50s всего

### Конфигурация

```bash
export HERMES_SQLITE_BUSY_TIMEOUT=10000  # миллисекунды
```
