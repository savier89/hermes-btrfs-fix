# Hermes Agent — SQLite WAL Retry Fix

## Problem

SQLite in WAL mode experiences transient locking errors under high concurrency
or on filesystems with Copy-on-Write semantics (BTRFS, ZFS):

```
sqlite3.OperationalError: disk I/O error
sqlite3.OperationalError: database is locked
```

These errors occur during WAL initialization (`PRAGMA journal_mode=WAL`) and
can also affect the DELETE fallback (`PRAGMA journal_mode=DELETE`), causing
gateway crashes and stale task claims.

## Root Cause

- WAL mode relies on shared memory (`-shm` files) and sequential writes
- On BTRFS/ZFS, COW operations cause transient blocking during checkpoint
  races — manifesting as `disk I/O error`
- Under high concurrency (multiple gateway processes), writers compete for
  database locks — manifesting as `database is locked`
- The default SQLite timeout (1 second) is insufficient for these scenarios
- The existing fallback only handled permanent filesystem incompatibility
  (NFS/SMB), not transient locking errors
- **v3 bug:** After WAL retries were exhausted, the fallback to DELETE mode
  was NOT protected — `PRAGMA journal_mode=DELETE` could also fail with
  `disk I/O error` on BTRFS, crashing the caller

## Solution

**Retry logic + protected fallback** for transient WAL setup errors:

1. Set `busy_timeout=30000` (30 seconds) on all connections
2. Retry WAL setup up to 3 times with 1 second delay
3. **v4:** Protected DELETE fallback — if `PRAGMA journal_mode=DELETE` also
   fails, check current mode and continue instead of crashing
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

- `hermes_state.py` — retry logic + busy_timeout + protected DELETE fallback
  (`_try_fallback_delete()`) + transient error classification
- `tools/terminal_tool.py` — `_safe_getcwd()` helper (protects against
  FileNotFoundError when current working directory is deleted while a subprocess
  is running)

### v4 Changes

Compared to v3:
- Added `_try_fallback_delete()` — wraps `PRAGMA journal_mode=DELETE` in
  try/except. If it fails, checks current mode via `PRAGMA journal_mode` and
  returns whatever SQLite has, instead of crashing
- Removed `disk i/o error` from `_WAL_INCOMPAT_MARKERS` (kept only in
  `_WAL_TRANSIENT_MARKERS` — it's transient on BTRFS, not a permanent
  filesystem incompatibility)

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

After applying, restart all gateway services:

```bash
systemctl --user restart hermes-gateway hermes-gateway-coder hermes-gateway-researcher
```

## Testing

Patch v4 tested with:
- Basic concurrency (5W + 3R): 320/320 operations, 0 errors
- High concurrency (10W + 5R): 750/750 operations, 0 errors
- Multi-process (5 processes): 250/250 operations, 0 errors
- **Live test:** 3 concurrent gateways (default + coder + researcher) on BTRFS,
  0 `disk I/O error` crashes after v4

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
sqlite3.OperationalError: disk I/O error
sqlite3.OperationalError: database is locked
```

Ошибки возникают при инициализации WAL (`PRAGMA journal_mode=WAL`) и могут
поражать fallback на DELETE (`PRAGMA journal_mode=DELETE`), вызывая краш
gateway и зависание задач.

## Причина

- WAL mode полагается на shared memory и последовательные записи
- На BTRFS/ZFS COW операции вызывают временные блокировки при checkpoint race
  — проявляется как `disk I/O error`
- При высокой конкурентности (несколько gateway) писатели конкурируют за блоки
  — проявляется как `database is locked`
- Дефолтный таймаут SQLite (1 сек) недостаточен
- Существующий fallback обрабатывал только перманентную несовместимость (NFS/SMB),
  а не транзентные ошибки
- **Баг v3:** После исчерпания retry, fallback на DELETE НЕ был защищён —
  `PRAGMA journal_mode=DELETE` тоже мог упасть с `disk I/O error` на BTRFS,
  убивая вызывающий код

## Решение

**Retry-логика + защищённый fallback** для транзентных ошибок WAL:

1. `busy_timeout=30000` (30 секунд) для всех соединений
2. До 3 попыток с задержкой 1 секунда
3. **v4:** Защищённый fallback на DELETE — если `PRAGMA journal_mode=DELETE`
   тоже падает, проверяется текущий режим и работа продолжается вместо краша
4. Разделение transient ошибок (retry) и несовместимых ФС (немедленный fallback)

### Конфигурация

```bash
export HERMES_SQLITE_BUSY_TIMEOUT=30000  # миллисекунды
export HERMES_SQLITE_WAL_RETRIES=3       # макс попыток
export HERMES_SQLITE_WAL_RETRY_DELAY=1.0 # секунды между попытками
```

### Изменённые файлы

- `hermes_state.py` — retry-логика + busy_timeout + защищённый fallback на DELETE
  (`_try_fallback_delete()`) + классификация ошибок
- `tools/terminal_tool.py` — `_safe_getcwd()` (защита от FileNotFoundError
  при удалении текущей директории во время работы subprocess)

### Изменения v4

По сравнению с v3:
- Добавлен `_try_fallback_delete()` — оборачивает `PRAGMA journal_mode=DELETE`
  в try/except. Если падает, проверяет текущий режим через `PRAGMA journal_mode`
  и возвращает то, что есть, вместо краша
- Убран `disk i/o error` из `_WAL_INCOMPAT_MARKERS` (оставлен только в
  `_WAL_TRANSIENT_MARKERS` — это транзентная ошибка на BTRFS, а не перманентная
  несовместимость ФС)

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

После применения перезапустите все gateway:

```bash
systemctl --user restart hermes-gateway hermes-gateway-coder hermes-gateway-researcher
```

## Тестирование

Патч v4 протестирован:
- Базовая конкурентность (5W + 3R): 320/320 операций, 0 ошибок
- Высокая конкурентность (10W + 5R): 750/750 операций, 0 ошибок
- Мультипроцессная (5 процессов): 250/250 операций, 0 ошибок
- **Live тест:** 3 concurrent gateway (default + coder + researcher) на BTRFS,
  0 `disk I/O error` после v4

## Ссылки

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Issue #30846](https://github.com/NousResearch/hermes-agent/issues/30846)
- [PR #30700](https://github.com/NousResearch/hermes-agent/pull/30700) — связанный PR в upstream
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [SQLite Performance on Btrfs](https://wiki.tnonline.net/w/Blog/SQLite_Performance_on_Btrfs)
