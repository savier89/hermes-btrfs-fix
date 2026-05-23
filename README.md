# Hermes Agent — BTRFS + SQLite WAL Fix

## Problem

SQLite in WAL mode conflicts with BTRFS (Copy-on-Write semantics), causing:

```
sqlite3.OperationalError: disk I/O error
```

This leads to corruption of `state.db` and `kanban.db`.

## Cause

BTRFS COW changes disk blocks on write, which breaks SQLite WAL mode direct I/O operations. The same issue is known for ZFS and F2FS.

## Solution

The patch adds proactive BTRFS detection and forces `journal_mode=DELETE`, preventing the error entirely.

### Changed Files

- `hermes_state.py` — added `_is_on_btrfs()` and proactive fallback
- `hermes_cli/kanban_db.py` — pass DB path for detection
- `tools/terminal_tool.py` — fix `FileNotFoundError` in cleanup thread

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

## Official Status

Hermes Agent already has a built-in fallback to `journal_mode=DELETE` on `disk i/o error`, but it triggers AFTER the error occurs. This patch adds proactive detection, preventing the error from happening in the first place.

## Links

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [BTRFS COW](https://btrfs.wiki.kernel.org/index.php/Copy-on_Write)

---

# Hermes Agent — BTRFS + SQLite WAL Fix

## Проблема

SQLite в WAL mode конфликтует с BTRFS (Copy-on-Write семантика), что вызывает:

```
sqlite3.OperationalError: disk I/O error
```

Это приводит к повреждению БД `state.db` и `kanban.db`.

## Причина

BTRFS COW меняет блоки диска при записи, что ломает прямые операции SQLite WAL mode. Аналогичная проблема известна для ZFS и F2FS.

## Решение

Патч добавляет проактивную детекцию BTRFS и принудительное переключение на `journal_mode=DELETE`, предотвращая ошибку вообще.

### Изменённые файлы

- `hermes_state.py` — добавлена `_is_on_btrfs()` и проактивный fallback
- `hermes_cli/kanban_db.py` — передача пути БД для детекции
- `tools/terminal_tool.py` — фикс `FileNotFoundError` в треде очистки

## Установка

```bash
# Способ 1: git am (рекомендуется)
cd ~/.hermes/hermes-agent
git am btrfs-sqlite-fix.patch

# Способ 2: скрипт автоматической проверки
bash apply-btrfs-fix.sh
```

## Автоматическое применение после обновления

```bash
# Добавьте в ~/.bashrc или ~/.zshrc
alias hermes-update='hermes update && ~/.hermes/scripts/apply-btrfs-fix.sh'
```

## Официальный статус

Hermes Agent уже имеет встроенный fallback на `journal_mode=DELETE` при `disk i/o error`, но он срабатывает ПОСЛЕ ошибки. Этот патч добавляет проактивную детекцию, предотвращающую ошибку.

## Ссылки

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [BTRFS COW](https://btrfs.wiki.kernel.org/index.php/Copy-on_Write)
