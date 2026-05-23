# Hermes Agent — SQLite WAL Retry Fix

## Problem

SQLite in WAL mode experiences transient locking errors under high concurrency
or on filesystems with Copy-on-Write semantics (BTRFS, ZFS):

```
sqlite3.OperationalError: database is locked
```

These errors occur during WAL initialization (`PRAGMA journal_mode=WAL`) and
write transactions (`BEGIN IMMEDIATE`), causing gateway crashes and stale task
claims.

**Note:** The actual error is `database is locked`, NOT `disk I/O error` as
initially reported. The root cause is transient concurrency contention, not
BTRFS COW semantics per se.

## Root Cause

- WAL mode relies on shared memory (`-shm` files) and sequential writes
- On BTRFS/ZFS, COW operations can cause transient blocking during checkpoint
  races
- Under high concurrency, multiple writers compete for database locks
- The default SQLite timeout (1 second) is insufficient for these scenarios
- The existing fallback only handled permanent filesystem incompatibility
  (NFS/SMB), not transient locking errors

## Solution

**Retry logic + increased busy_timeout** for transient WAL setup errors:

1. Set `busy_timeout=30000` (30 seconds) on all connections
2. Retry WAL setup up to 3 times with 1 second delay
3. Fall back to DELETE mode only after exhausting retries
4. Distinguish transient errors (retry) from incompatible filesystems
   (immediate fallback)

### Configuration

Users can override defaults via environment variables:

```bash
export HERMES_SQLITE_BUSY_TIMEOUT=30000  # milliseconds (default: 30000)
export HERMES_SQLITE_WAL_RETRIES=3       # max attempts (default: 3)
export HERMES_SQLITE_WAL_RETRY_DELAY=1.0 # seconds between attempts (default: 1.0)
```

### Changed Files

- `hermes_state.py` — retry logic + busy_timeout + transient error classification
- `tools/terminal_tool.py` — `_safe_getcwd()` helper (protects against
  FileNotFoundError when current working directory is deleted while a subprocess
  is running)

## Installation

```bash
# Method 1: Direct patch (recommended)
cd ~/.hermes/hermes-agent
patch -p1 < btrfs-sqlite-fix.patch

# Method 2: Automatic check script
bash apply-btrfs-fix.sh

# Method 3: git am (if hermes-agent is a git repo)
cd ~/.hermes/hermes-agent
git am btrfs-sqlite-fix.patch
```

After applying, restart the gateway:

```bash
systemctl --user restart hermes-gateway
```

## Testing

Patch v3 tested with:
- Basic concurrency (5W + 3R): 320/320 operations, 0 errors
- High concurrency (10W + 5R): 750/750 operations, 0 errors
- Multi-process (5 processes): 250/250 operations, 0 errors

## Links

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Issue #30846](https://github.com/NousResearch/hermes-agent/issues/30846)
- [PR #30700](https://github.com/NousResearch/hermes-agent/pull/30700) — related retry approach in upstream
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [SQLite Performance on Btrfs](https://wiki.tnonline.net/w/Blog/SQLite_Performance_on_Btrfs)

---

# Hermes Agent — SQLite WAL Retry Fix (RU)

## Проблема

SQLite в WAL mode испытывает транзентные ошибки блокировки при высокой
конкурентности или на файловых системах с Copy-on-Write (BTRFS, ZFS):

```
sqlite3.OperationalError: database is locked
```

**Примечание:** Реальная ошибка — `database is locked`, а НЕ `disk I/O error`,
как изначально сообщалось. Причина — транзентная конкуренция блокировок, а не
семантика COW BTRFS.

## Причина

- WAL mode полагается на shared memory и последовательные записи
- На BTRFS/ZFS COW операции вызывают временные блокировки во время checkpoint
- При высокой конкурентности писатели конкурируют за блоки
- Дефолтный таймаут SQLite (1 сек) недостаточен
- Существующий fallback обрабатывал только перманентную несовместимость (NFS/SMB),
  а не транзентные ошибки блокировки

## Решение

**Retry-логика + увеличенный busy_timeout** для транзентных ошибок WAL:

1. `busy_timeout=30000` (30 секунд) для всех соединений
2. До 3 попыток с задержкой 1 секунда
3. Fallback на DELETE только после исчерпания попыток
4. Разделение transient ошибок (retry) и несовместимых ФС (немедленный fallback)

### Конфигурация

```bash
export HERMES_SQLITE_BUSY_TIMEOUT=30000  # миллисекунды
export HERMES_SQLITE_WAL_RETRIES=3       # макс попыток
export HERMES_SQLITE_WAL_RETRY_DELAY=1.0 # секунды между попытками
```

### Изменённые файлы

- `hermes_state.py` — retry-логика + busy_timeout + классификация ошибок
- `tools/terminal_tool.py` — `_safe_getcwd()` (защита от FileNotFoundError
  при удалении текущей директории во время работы subprocess)

## Установка

```bash
# Способ 1: Прямой патч (рекомендуется)
cd ~/.hermes/hermes-agent
patch -p1 < btrfs-sqlite-fix.patch

# Способ 2: Автоматический скрипт
bash apply-btrfs-fix.sh

# Способ 3: git am (если hermes-agent — git репозиторий)
cd ~/.hermes/hermes-agent
git am btrfs-sqlite-fix.patch
```

После применения перезапустите gateway:

```bash
systemctl --user restart hermes-gateway
```

## Тестирование

Патч v3 протестирован:
- Базовая конкурентность (5W + 3R): 320/320 операций, 0 ошибок
- Высокая конкурентность (10W + 5R): 750/750 операций, 0 ошибок
- Мультипроцессная (5 процессов): 250/250 операций, 0 ошибок

## Ссылки

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Issue #30846](https://github.com/NousResearch/hermes-agent/issues/30846)
- [PR #30700](https://github.com/NousResearch/hermes-agent/pull/30700) — связанный PR в upstream
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [SQLite Performance on Btrfs](https://wiki.tnonline.net/w/Blog/SQLite_Performance_on_Btrfs)
