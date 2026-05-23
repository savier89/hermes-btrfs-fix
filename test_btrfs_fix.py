#!/usr/bin/env python3
"""
Tests for BTRFS + SQLite WAL retry fix (patch v3).

Standalone tests that mock the upstream dependencies.
Mimics the test approach from upstream PR #30700.
"""

import sqlite3
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Create minimal stubs for upstream dependencies
sys.modules['agent'] = MagicMock()
sys.modules['utils'] = MagicMock()
sys.modules['hermes_logging'] = MagicMock()
sys.modules['hermes_constants'] = MagicMock()
sys.modules['hermes_time'] = MagicMock()


def test_busy_timeout_is_at_least_30s():
    """Verify STATE_DB_BUSY_TIMEOUT_MS >= 30000."""
    import hermes_state
    assert hasattr(hermes_state, '_STATE_DB_BUSY_TIMEOUT_MS'), \
        "Missing _STATE_DB_BUSY_TIMEOUT_MS constant"
    assert hermes_state._STATE_DB_BUSY_TIMEOUT_MS >= 30_000, \
        f"busy_timeout too low: {hermes_state._STATE_DB_BUSY_TIMEOUT_MS}"
    print(f"  ✓ busy_timeout = {hermes_state._STATE_DB_BUSY_TIMEOUT_MS}ms (>= 30s)")


def test_transient_markers_exist():
    """Verify _WAL_TRANSIENT_MARKERS contains expected markers."""
    import hermes_state
    assert hasattr(hermes_state, '_WAL_TRANSIENT_MARKERS'), \
        "Missing _WAL_TRANSIENT_MARKERS"
    markers = hermes_state._WAL_TRANSIENT_MARKERS
    assert "database is locked" in markers
    assert "disk i/o error" in markers
    assert "database is busy" in markers
    print(f"  ✓ Transient markers: {len(markers)} defined")


def test_retry_succeeds_after_transient_failures():
    """Test that retry logic succeeds after transient failures."""
    import hermes_state

    # Create a mock connection that fails twice then succeeds
    mock_conn = Mock()
    fail_count = [0]

    def mock_execute(sql):
        if "journal_mode=WAL" in sql:
            fail_count[0] += 1
            if fail_count[0] < 3:
                raise sqlite3.OperationalError("database is locked")
        elif "busy_timeout" in sql:
            pass  # Ignore busy_timeout setting
    mock_conn.execute = mock_execute

    # Patch time.sleep to speed up test
    with patch('time.sleep', return_value=None):
        result = hermes_state.apply_wal_with_fallback(mock_conn, db_label="test")

    assert result == "wal", f"Expected 'wal', got '{result}'"
    assert fail_count[0] == 3, f"Expected 3 attempts, got {fail_count[0]}"
    print(f"  ✓ Retry succeeded after {fail_count[0]-1} transient failures")


def test_fallback_after_exhausted_retries():
    """Test fallback to DELETE after all retries exhausted."""
    import hermes_state

    mock_conn = Mock()

    def mock_execute(sql):
        if "journal_mode=WAL" in sql:
            raise sqlite3.OperationalError("database is locked")
        elif "journal_mode=DELETE" in sql:
            pass  # Fallback succeeds
        elif "busy_timeout" in sql:
            pass
    mock_conn.execute = mock_execute

    with patch('time.sleep', return_value=None):
        with patch.object(hermes_state, '_log_wal_fallback_once') as mock_log:
            result = hermes_state.apply_wal_with_fallback(mock_conn, db_label="test")

    assert result == "delete", f"Expected 'delete', got '{result}'"
    mock_log.assert_called_once()
    print(f"  ✓ Fallback to DELETE after exhausted retries")


def test_reraise_non_transient_error():
    """Test that non-transient errors are immediately raised."""
    import hermes_state

    mock_conn = Mock()

    def mock_execute(sql):
        if "journal_mode=WAL" in sql:
            raise sqlite3.OperationalError("no such table: main")
        elif "busy_timeout" in sql:
            pass
    mock_conn.execute = mock_execute

    with patch('time.sleep', return_value=None):
        try:
            hermes_state.apply_wal_with_fallback(mock_conn, db_label="test")
            assert False, "Should have raised OperationalError"
        except sqlite3.OperationalError as e:
            assert "no such table" in str(e)
    print(f"  ✓ Non-transient error reraised correctly")


def test_incompatible_fallback_immediate():
    """Test immediate fallback for incompatible filesystems (NFS/SMB)."""
    import hermes_state

    mock_conn = Mock()
    execute_count = [0]

    def mock_execute(sql):
        execute_count[0] += 1
        if "journal_mode=WAL" in sql:
            raise sqlite3.OperationalError("locking protocol")
        elif "journal_mode=DELETE" in sql:
            pass
        elif "busy_timeout" in sql:
            pass
    mock_conn.execute = mock_execute

    with patch('time.sleep', return_value=None):
        with patch.object(hermes_state, '_log_wal_fallback_once') as mock_log:
            result = hermes_state.apply_wal_with_fallback(mock_conn, db_label="test")

    assert result == "delete", f"Expected 'delete', got '{result}'"
    # Should only have a few executes: busy_timeout + WAL (then immediate fallback)
    assert execute_count[0] < 5, "Should fallback immediately, not retry"
    print(f"  ✓ Immediate fallback for incompatible filesystem")


def test_safe_getcwd_exists():
    """Verify _safe_getcwd helper exists in terminal_tool."""
    from tools.terminal_tool import _safe_getcwd
    # Should return a valid path even if CWD is deleted
    result = _safe_getcwd()
    assert result and len(result) > 0
    print(f"  ✓ _safe_getcwd() returns: {result[:50]}...")


def main():
    print("Running BTRFS + SQLite WAL fix tests...\n")

    tests = [
        test_busy_timeout_is_at_least_30s,
        test_transient_markers_exist,
        test_retry_succeeds_after_transient_failures,
        test_fallback_after_exhausted_retries,
        test_reraise_non_transient_error,
        test_incompatible_fallback_immediate,
        test_safe_getcwd_exists,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
    print("All tests passed!")


if __name__ == "__main__":
    main()
