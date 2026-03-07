#!/usr/bin/env python3
"""Test script for DuckDB macros"""

import json
import os
import sys

import duckdb
import pytest


def split_sql_statements(sql_content):
    """Split SQL content into statements, respecting string literals."""
    statements = []
    current = []
    in_string = False
    string_char = None

    i = 0
    while i < len(sql_content):
        char = sql_content[i]

        # Handle string literals
        if char in ("'", '"') and not in_string:
            in_string = True
            string_char = char
            current.append(char)
        elif char == string_char and in_string:
            # Check for escaped quote
            if i + 1 < len(sql_content) and sql_content[i + 1] == string_char:
                current.append(char)
                current.append(char)
                i += 1
            else:
                in_string = False
                string_char = None
                current.append(char)
        elif char == ";" and not in_string:
            # End of statement
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    # Don't forget last statement if no trailing semicolon
    if current:
        stmt = "".join(current).strip()
        if stmt:
            statements.append(stmt)

    return statements


def test_macros():
    con = duckdb.connect(":memory:")

    # Load required extensions
    print("Loading extensions...")
    extensions = ["httpfs", "http_client", "json", "shellfs"]
    for ext in extensions:
        try:
            con.sql(f"INSTALL {ext};")
            con.sql(f"LOAD {ext};")
            print(f"  [OK] {ext}")
        except Exception:
            try:
                con.sql(f"INSTALL {ext} FROM community;")
                con.sql(f"LOAD {ext};")
                print(f"  [OK] {ext} (community)")
            except Exception as e:
                print(f"  [SKIP] {ext}: {e}")

    # Register UDFs (getenv etc. – needed by macros); requires numpy for DuckDB create_function
    try:
        from agent_farm.udfs import register_udfs

        register_udfs(con)
    except Exception as e:
        pytest.skip(f"UDFs not available: {e}")

    # Create agent infrastructure tables (macros reference these)
    try:
        from agent_farm.schemas import AGENT_TABLES_SQL

        for stmt in AGENT_TABLES_SQL.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                try:
                    con.sql(stmt)
                except Exception:
                    pass
        print("  Agent tables created")
    except ImportError:
        print("  [WARN] Could not import schemas for agent tables")

    # Load macros from sql/ directory (macros are split across multiple files)
    import glob

    from agent_farm.main import SQL_LOAD_ORDER

    print("\nLoading macros...")
    sql_dir = os.path.join("src", "agent_farm", "sql")
    all_files = [os.path.basename(p) for p in glob.glob(os.path.join(sql_dir, "*.sql"))]
    sql_files = [os.path.join(sql_dir, f) for f in SQL_LOAD_ORDER if f in all_files]
    sql_files += sorted(
        p
        for p in glob.glob(os.path.join(sql_dir, "*.sql"))
        if os.path.basename(p) not in SQL_LOAD_ORDER
    )
    if not sql_files:
        pytest.skip(f"No SQL files found in {sql_dir}")

    statements = []
    for sql_file in sql_files:
        print(f"  Loading {os.path.basename(sql_file)}...")
        with open(sql_file, "r", encoding="utf-8") as f:
            sql = f.read()
        statements.extend(split_sql_statements(sql))

    errors = []
    success = 0
    for stmt in statements:
        # Skip comment-only statements
        lines = [
            line for line in stmt.split("\n") if line.strip() and not line.strip().startswith("--")
        ]
        if not lines:
            continue
        try:
            con.sql(stmt)
            success += 1
        except Exception as e:
            errors.append((stmt[:60], str(e)))

    print(f"  Loaded {success} statements, {len(errors)} errors")
    if errors:
        print("\n  Errors:")
        for stmt, err in errors[:5]:  # Show first 5 errors
            print(f"    - {stmt}... -> {err[:80]}")

    # Test individual macros
    print("\n" + "=" * 50)
    print("Testing macros:")
    print("=" * 50)

    tests = [
        ("url_encode", "SELECT url_encode('hello world & test=1')"),
        ("now_iso", "SELECT now_iso()"),
        ("now_unix", "SELECT now_unix()"),
    ]

    passed = 0
    failed = 0

    for name, query in tests:
        try:
            result = con.sql(query).fetchone()[0]
            # Truncate long results
            result_str = str(result)[:100]
            print(f"  [PASS] {name}: {result_str}...")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    assert failed == 0, f"{failed} macro tests failed"


def test_init_farm_bootstrap_smoke():
    from agent_farm.cli import init_farm

    con, engine, _ = init_farm(":memory:", quiet=True)
    columns = {row[0] for row in con.execute("DESCRIBE agent_sessions").fetchall()}

    assert engine.is_initialized() is True
    assert {"agent_id", "context", "messages"}.issubset(columns)


def test_ollama_base_uses_env(monkeypatch):
    from agent_farm.cli import init_farm

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example.test:1234")
    con, _, _ = init_farm(":memory:", quiet=True)

    assert con.execute("SELECT ollama_base()").fetchone()[0] == "http://example.test:1234"


def test_agent_run_udf_is_registered():
    from agent_farm.cli import init_farm

    con, _, _ = init_farm(":memory:", quiet=True)
    result = con.execute("SELECT agent_run('missing-agent', 'hello', 1)").fetchone()[0]

    assert "missing-agent" in result


def test_approval_request_lifecycle():
    from agent_farm.cli import init_farm

    con, _, _ = init_farm(":memory:", quiet=True)
    created = con.execute(
        """
        SELECT request_approval(
            'sess-approval',
            'shell_run',
            '{"cmd":"rm -rf /"}',
            'dangerous command'
        )
        """
    ).fetchone()[0]
    created_json = json.loads(created)
    approval_id = created_json["approval_id"]

    stored = con.execute(
        "SELECT status, tool_name FROM pending_approvals WHERE id = ?",
        [approval_id],
    ).fetchone()
    assert stored == ("pending", "shell_run")

    resolved = con.execute(
        "SELECT resolve_approval(?, 'approved', 'pytest')",
        [approval_id],
    ).fetchone()[0]
    resolved_json = json.loads(resolved)
    assert resolved_json["status"] == "approved"

    final_row = con.execute(
        "SELECT status, decision, resolved_by FROM pending_approvals WHERE id = ?",
        [approval_id],
    ).fetchone()
    assert final_row == ("approved", "approved", "pytest")


def test_radio_messages_persist_across_restart(tmp_path):
    from agent_farm.cli import init_farm

    db_path = tmp_path / "radio-test.duckdb"

    con, _, _ = init_farm(str(db_path), quiet=True)
    published = con.execute(
        "SELECT radio_transmit_message('builds', '{\"state\":\"queued\"}')"
    ).fetchone()[0]
    assert json.loads(published)["published"] is True
    con.close()

    con, _, _ = init_farm(str(db_path), quiet=True)
    listened = con.execute("SELECT radio_listen('builds', 10)").fetchone()[0]
    listened_json = json.loads(listened)
    assert listened_json["payload"]["state"] == "queued"

    empty = con.execute("SELECT radio_listen('builds', 10)").fetchone()[0]
    assert json.loads(empty)["no_message"] is True


if __name__ == "__main__":
    sys.exit(0 if test_macros() else 1)
