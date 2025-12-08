#!/usr/bin/env python3
"""Install DuckDB extensions with error handling."""
import duckdb

con = duckdb.connect()

# Core extensions (from default repo)
core_ext = ['httpfs', 'json', 'icu', 'vss', 'ducklake', 'lindel']
for ext in core_ext:
    try:
        con.sql(f'INSTALL {ext};')
        print(f'[OK] {ext}')
    except Exception as e:
        print(f'[SKIP] {ext}: {e}')

# Community extensions
community_ext = ['http_client', 'duckdb_mcp', 'jsonata', 'shellfs', 'zipfs']
for ext in community_ext:
    try:
        con.sql(f'INSTALL {ext} FROM community;')
        print(f'[OK] {ext}')
    except Exception as e:
        print(f'[SKIP] {ext}: {e}')

print('Extension installation complete!')
