#!/usr/bin/env python3
"""Test script for DuckDB extensions loading"""
import duckdb
import sys

def test_extensions():
    con = duckdb.connect(':memory:')

    extensions = [
        'httpfs', 'http_client', 'json', 'icu',
        'jsonata', 'duckpgq', 'bitfilters', 'lindel',
        'vss', 'htmlstringify', 'lsh', 'shellfs', 'zipfs',
        'radio', 'duckdb_mcp'
    ]

    print(f"DuckDB version: {duckdb.__version__}")
    print("\nTesting extensions:")

    success = []
    failed = []

    for ext in extensions:
        try:
            con.sql(f"INSTALL {ext};")
            con.sql(f"LOAD {ext};")
            print(f"  [OK] {ext}")
            success.append(ext)
        except Exception as e:
            try:
                con.sql(f"INSTALL {ext} FROM community;")
                con.sql(f"LOAD {ext};")
                print(f"  [OK] {ext} (community)")
                success.append(ext)
            except Exception as e2:
                print(f"  [FAIL] {ext}: {e2}")
                failed.append((ext, str(e2)))

    print(f"\nSummary: {len(success)}/{len(extensions)} extensions loaded")
    if failed:
        print(f"Failed: {[f[0] for f in failed]}")

    return len(failed) == 0

if __name__ == "__main__":
    sys.exit(0 if test_extensions() else 1)
