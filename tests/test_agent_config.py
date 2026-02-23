#!/usr/bin/env python3
"""Test script for Secure Desktop Agent config tables and macros."""

import sys

import duckdb


def test_agent_tables():
    """Test that agent config tables can be created."""
    con = duckdb.connect(":memory:")

    # Create tables
    con.sql("""
        CREATE TABLE IF NOT EXISTS agent_config (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL DEFAULT 'Desktop Agent',
            role VARCHAR NOT NULL DEFAULT 'assistant',
            security_profile VARCHAR NOT NULL DEFAULT 'standard',
            model_backend VARCHAR NOT NULL DEFAULT 'ollama_local',
            model_name VARCHAR DEFAULT 'llama3.2',
            consent_given BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id VARCHAR PRIMARY KEY,
            agent_id VARCHAR,
            path VARCHAR NOT NULL,
            name VARCHAR,
            mode VARCHAR NOT NULL DEFAULT 'readOnly',
            allowed_patterns VARCHAR[],
            denied_patterns VARCHAR[]
        );

        CREATE TABLE IF NOT EXISTS security_policy (
            agent_id VARCHAR PRIMARY KEY,
            shell_enabled BOOLEAN DEFAULT FALSE,
            shell_allowlist VARCHAR[],
            shell_blocklist VARCHAR[] DEFAULT [
                'rm -rf', 'rm -r /', 'mkfs', 'dd if='
            ],
            web_enabled BOOLEAN DEFAULT TRUE,
            allowed_domains VARCHAR[],
            blocked_domains VARCHAR[],
            sensitive_patterns VARCHAR[] DEFAULT [
                '*.env', '.env*', '*credentials*'
            ]
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            timestamp TIMESTAMP DEFAULT now(),
            entry_type VARCHAR NOT NULL,
            tool_name VARCHAR,
            parameters JSON,
            result JSON,
            decision VARCHAR,
            violations VARCHAR[]
        );
    """)

    print("[PASS] Agent tables created successfully")


def test_agent_config_insert():
    """Test inserting and querying agent config."""
    con = duckdb.connect(":memory:")

    # Create tables
    con.sql("""
        CREATE TABLE agent_config (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            security_profile VARCHAR NOT NULL,
            model_backend VARCHAR NOT NULL,
            model_name VARCHAR
        );

        CREATE TABLE workspaces (
            id VARCHAR PRIMARY KEY,
            agent_id VARCHAR,
            path VARCHAR NOT NULL,
            name VARCHAR,
            mode VARCHAR NOT NULL
        );

        CREATE TABLE security_policy (
            agent_id VARCHAR PRIMARY KEY,
            shell_enabled BOOLEAN DEFAULT FALSE,
            shell_blocklist VARCHAR[]
        );
    """)

    # Insert test data
    con.sql("""
        INSERT INTO agent_config VALUES
            ('agent-1', 'Test Agent', 'code', 'standard', 'ollama_local', 'llama3.2');

        INSERT INTO workspaces VALUES
            ('ws-1', 'agent-1', '/home/user/projects', 'Projects', 'writer'),
            ('ws-2', 'agent-1', '/home/user/docs', 'Docs', 'readOnly');

        INSERT INTO security_policy VALUES
            ('agent-1', FALSE, ['rm -rf', 'mkfs']);
    """)

    # Query and verify
    result = con.sql(
        "SELECT name, role, security_profile FROM agent_config WHERE id = 'agent-1'"
    ).fetchone()
    assert result == ("Test Agent", "code", "standard"), f"Unexpected result: {result}"

    ws_count = con.sql("SELECT COUNT(*) FROM workspaces WHERE agent_id = 'agent-1'").fetchone()[0]
    assert ws_count == 2, f"Expected 2 workspaces, got {ws_count}"

    shell = con.sql(
        "SELECT shell_enabled FROM security_policy WHERE agent_id = 'agent-1'"
    ).fetchone()[0]
    assert shell is False, f"Expected shell_enabled=False, got {shell}"

    print("[PASS] Agent config insert/query works")


def test_path_in_workspace_logic():
    """Test workspace path checking logic."""
    con = duckdb.connect(":memory:")

    # Simple path check macro
    con.sql("""
        CREATE MACRO path_in_workspace(check_path, workspace_path) AS (
            starts_with(check_path, workspace_path) OR
            starts_with(check_path, workspace_path || '/')
        )
    """)

    tests = [
        ("/home/user/projects/myfile.py", "/home/user/projects", True),
        ("/home/user/projects/sub/file.py", "/home/user/projects", True),
        ("/home/user/other/file.py", "/home/user/projects", False),
        ("/etc/passwd", "/home/user/projects", False),
    ]

    for check_path, ws_path, expected in tests:
        result = con.sql(f"SELECT path_in_workspace('{check_path}', '{ws_path}')").fetchone()[0]
        assert result == expected, (
            f"path_in_workspace('{check_path}', '{ws_path}') = {result}, expected {expected}"
        )

    print("[PASS] Path workspace checking works")


def test_blocked_command_logic():
    """Test shell command blocklist logic."""
    con = duckdb.connect(":memory:")

    con.sql("""
        CREATE TABLE security_policy (
            agent_id VARCHAR PRIMARY KEY,
            shell_blocklist VARCHAR[]
        );

        INSERT INTO security_policy VALUES
            ('agent-1', ['rm -rf', 'mkfs', 'dd if=']);
    """)

    # Check if command is blocked
    con.sql("""
        CREATE MACRO is_blocked_command(agent_id_param, cmd) AS (
            EXISTS (
                SELECT 1 FROM security_policy
                CROSS JOIN LATERAL unnest(shell_blocklist) AS t(blocked)
                WHERE agent_id = agent_id_param
                AND lower(cmd) LIKE '%' || lower(blocked) || '%'
            )
        )
    """)

    tests = [
        ("agent-1", "rm -rf /", True),
        ("agent-1", "ls -la", False),
        ("agent-1", "mkfs.ext4 /dev/sda", True),
        ("agent-1", "git status", False),
        ("agent-1", "sudo dd if=/dev/zero of=/dev/sda", True),
    ]

    for agent_id, cmd, expected in tests:
        result = con.sql(f"SELECT is_blocked_command('{agent_id}', '{cmd}')").fetchone()[0]
        assert result == expected, (
            f"is_blocked_command('{agent_id}', '{cmd}') = {result}, expected {expected}"
        )

    print("[PASS] Blocked command checking works")


def test_audit_log():
    """Test audit logging."""
    con = duckdb.connect(":memory:")

    con.sql("""
        CREATE SEQUENCE audit_seq START 1;

        CREATE TABLE audit_log (
            id INTEGER DEFAULT nextval('audit_seq'),
            session_id VARCHAR NOT NULL,
            timestamp TIMESTAMP DEFAULT now(),
            entry_type VARCHAR NOT NULL,
            tool_name VARCHAR,
            parameters JSON,
            decision VARCHAR
        );
    """)

    # Insert audit entries
    con.sql("""
        INSERT INTO audit_log (session_id, entry_type, tool_name, parameters, decision)
        VALUES
            ('sess-1', 'tool_call', 'fs_read', '{"path": "/home/user/file.txt"}', 'allow'),
            ('sess-1', 'tool_call', 'shell_run', '{"cmd": "rm -rf /"}', 'deny'),
            ('sess-1', 'tool_call', 'fs_list', '{"path": "/home/user"}', 'allow');
    """)

    # Query audit log
    denied = con.sql("SELECT COUNT(*) FROM audit_log WHERE decision = 'deny'").fetchone()[0]
    assert denied == 1, f"Expected 1 denied entry, got {denied}"

    total = con.sql("SELECT COUNT(*) FROM audit_log WHERE session_id = 'sess-1'").fetchone()[0]
    assert total == 3, f"Expected 3 total entries, got {total}"

    print("[PASS] Audit logging works")


def main():
    print("=" * 50)
    print("Testing Secure Desktop Agent Config")
    print("=" * 50 + "\n")

    tests = [
        test_agent_tables,
        test_agent_config_insert,
        test_path_in_workspace_logic,
        test_blocked_command_logic,
        test_audit_log,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
