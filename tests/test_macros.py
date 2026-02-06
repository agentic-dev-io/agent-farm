#!/usr/bin/env python3
"""Test script for DuckDB macros"""

import sys

import duckdb


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
            if stmt and not stmt.startswith("--"):
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    # Don't forget last statement if no trailing semicolon
    if current:
        stmt = "".join(current).strip()
        if stmt and not stmt.startswith("--"):
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

    # Register getenv UDF (needed by some macros)
    import os

    con.create_function("getenv", lambda name: os.getenv(name) if name else None, [str], str,
                        null_handling="special")

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

    print("\nLoading macros...")
    sql_dir = os.path.join("src", "agent_farm", "sql")
    sql_files = sorted(glob.glob(os.path.join(sql_dir, "*.sql")))
    if not sql_files:
        print(f"  No SQL files found in {sql_dir}")
        return False

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

    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if test_macros() else 1)
