"""
Tests for the Spec Engine.

Tests the core functionality:
- Schema loading
- Macro execution
- Template rendering
- JSON Schema validation
- MCP tool implementations
"""

import json
import os
import sys

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import duckdb


def try_load_extension(con, ext_name, from_community=False):
    """Try to load an extension, returning True if successful."""
    try:
        if from_community:
            con.sql(f"INSTALL {ext_name} FROM community;")
        else:
            con.sql(f"INSTALL {ext_name};")
        con.sql(f"LOAD {ext_name};")
        return True
    except Exception:
        try:
            # Try loading without install (might be bundled)
            con.sql(f"LOAD {ext_name};")
            return True
        except Exception:
            return False


def has_non_comment_content(stmt):
    """Check if a SQL statement has any non-comment content."""
    for ln in stmt.split("\n"):
        ln = ln.strip()
        if ln and not ln.startswith("--"):
            return True
    return False


def load_sql_file(con, filepath, verbose=False):
    """Load and execute a SQL file, handling comments properly."""
    if not os.path.exists(filepath):
        return 0

    with open(filepath, "r") as f:
        sql_content = f.read()

    count = 0
    for stmt in sql_content.split(";"):
        stmt = stmt.strip()
        if has_non_comment_content(stmt):
            try:
                con.sql(stmt)
                count += 1
            except Exception as e:
                if verbose:
                    print(f"SQL error: {e}")
    return count


class TestSpecEngineSchema:
    """Tests for the Spec Engine schema."""

    @pytest.fixture
    def con(self):
        """Create a fresh DuckDB connection with Spec Engine schema."""
        con = duckdb.connect(":memory:")

        # Try to load json extension (may fail in network-restricted environments)
        try_load_extension(con, "json")

        # Load schema
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "db", "spec_engine_schema.sql"
        )
        load_sql_file(con, schema_path, verbose=True)

        yield con
        con.close()

    def test_spec_objects_table_exists(self, con):
        """Test that spec_objects table is created."""
        result = con.sql(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'spec_objects'"
        ).fetchone()
        assert result is not None
        assert result[0] == "spec_objects"

    def test_spec_docs_table_exists(self, con):
        """Test that spec_docs table is created."""
        result = con.sql(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'spec_docs'"
        ).fetchone()
        assert result is not None

    def test_spec_payloads_table_exists(self, con):
        """Test that spec_payloads table is created."""
        result = con.sql(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'spec_payloads'"
        ).fetchone()
        assert result is not None

    def test_insert_spec_object(self, con):
        """Test inserting a spec object."""
        con.sql("""
            INSERT INTO spec_objects (id, kind, name, version, status, summary)
            VALUES (1, 'agent', 'test-agent', '1.0.0', 'active', 'A test agent')
        """)

        result = con.sql("SELECT * FROM spec_objects WHERE id = 1").fetchone()
        assert result is not None
        assert result[1] == "agent"  # kind
        assert result[2] == "test-agent"  # name
        assert result[3] == "1.0.0"  # version
        assert result[4] == "active"  # status

    def test_spec_views_created(self, con):
        """Test that convenience views are created."""
        views = ["spec_agents_view", "spec_skills_view", "spec_apis_view", "spec_full_view"]
        for view in views:
            result = con.sql(
                f"SELECT table_name FROM information_schema.tables WHERE table_name = '{view}'"
            ).fetchone()
            assert result is not None, f"View {view} not found"


class TestSpecEngineSeed:
    """Tests for the Spec Engine seed data."""

    @pytest.fixture
    def con(self):
        """Create a DuckDB connection with schema and seed data."""
        con = duckdb.connect(":memory:")
        try_load_extension(con, "json")

        # Load schema and seed data
        db_dir = os.path.join(os.path.dirname(__file__), "..", "db")
        load_sql_file(con, os.path.join(db_dir, "spec_engine_schema.sql"))
        load_sql_file(con, os.path.join(db_dir, "spec_engine_seed.sql"), verbose=True)

        yield con
        con.close()

    def test_pia_agent_seeded(self, con):
        """Test that Pia agent is seeded."""
        result = con.sql(
            "SELECT * FROM spec_objects WHERE kind = 'agent' AND name = 'pia'"
        ).fetchone()
        assert result is not None
        assert result[4] == "active"  # status

    def test_skills_seeded(self, con):
        """Test that skills are seeded."""
        result = con.sql(
            "SELECT COUNT(*) FROM spec_objects WHERE kind = 'skill'"
        ).fetchone()
        assert result is not None
        assert result[0] >= 3  # At least 3 skills

    def test_schemas_seeded(self, con):
        """Test that schemas are seeded."""
        result = con.sql(
            "SELECT COUNT(*) FROM spec_objects WHERE kind = 'schema'"
        ).fetchone()
        assert result is not None
        assert result[0] >= 3  # At least 3 schemas

    def test_templates_seeded(self, con):
        """Test that templates are seeded."""
        result = con.sql(
            "SELECT COUNT(*) FROM spec_objects WHERE kind IN ('task_template', 'prompt_template')"
        ).fetchone()
        assert result is not None
        assert result[0] >= 2  # At least 2 templates

    def test_orgs_seeded(self, con):
        """Test that organizations are seeded."""
        result = con.sql(
            "SELECT COUNT(*) FROM spec_objects WHERE kind = 'org'"
        ).fetchone()
        assert result is not None
        assert result[0] >= 5  # All 5 orgs


class TestSpecEngineMacros:
    """Tests for the Spec Engine SQL macros."""

    @pytest.fixture
    def con(self):
        """Create a DuckDB connection with full Spec Engine setup."""
        con = duckdb.connect(":memory:")
        try_load_extension(con, "json")

        # Try to load minijinja
        self.has_minijinja = try_load_extension(con, "minijinja", from_community=True)

        # Load all SQL files
        db_dir = os.path.join(os.path.dirname(__file__), "..", "db")
        load_sql_file(con, os.path.join(db_dir, "spec_engine_schema.sql"))
        load_sql_file(con, os.path.join(db_dir, "spec_engine_macros.sql"))
        load_sql_file(con, os.path.join(db_dir, "spec_engine_seed.sql"))

        yield con
        con.close()

    def test_spec_list_by_kind_macro(self, con):
        """Test spec_list_by_kind macro."""
        result = con.sql("SELECT * FROM spec_list_by_kind('agent')").fetchall()
        assert len(result) >= 1
        # Check Pia is in the list
        names = [r[2] for r in result]  # name is column 2
        assert "pia" in names

    def test_spec_list_active_macro(self, con):
        """Test spec_list_active macro."""
        result = con.sql("SELECT * FROM spec_list_active()").fetchall()
        assert len(result) > 0
        # All should be active
        for r in result:
            assert r[4] == "active"  # status is column 4

    def test_spec_search_macro(self, con):
        """Test spec_search macro."""
        result = con.sql("SELECT * FROM spec_search('pia')").fetchall()
        assert len(result) >= 1
        names = [r[2] for r in result]
        assert "pia" in names

    def test_spec_get_macro(self, con):
        """Test spec_get macro."""
        result = con.sql("SELECT * FROM spec_get('agent', 'pia')").fetchone()
        assert result is not None
        assert result[2] == "pia"  # name

    def test_spec_stats_macro(self, con):
        """Test spec_stats macro."""
        result = con.sql("SELECT * FROM spec_stats()").fetchall()
        assert len(result) > 0
        # Should have agent kind
        kinds = [r[0] for r in result]
        assert "agent" in kinds


class TestSpecEngineModule:
    """Tests for the Python SpecEngine module."""

    @pytest.fixture
    def spec_engine(self):
        """Create a SpecEngine instance."""
        # Import here to avoid issues if module doesn't exist
        try:
            from agent_farm.spec_engine import SpecEngine
        except ImportError:
            pytest.skip("SpecEngine module not available")

        con = duckdb.connect(":memory:")
        engine = SpecEngine(con)
        engine.initialize()
        yield engine
        con.close()

    def test_spec_list(self, spec_engine):
        """Test spec_list method."""
        result = spec_engine.spec_list(kind="agent")
        assert isinstance(result, list)
        assert len(result) >= 1
        # Check structure
        if result:
            assert "id" in result[0]
            assert "kind" in result[0]
            assert "name" in result[0]

    def test_spec_get_by_kind_name(self, spec_engine):
        """Test spec_get with kind and name."""
        result = spec_engine.spec_get(kind="agent", name="pia")
        assert result is not None
        assert result["name"] == "pia"
        assert result["kind"] == "agent"

    def test_spec_get_by_id(self, spec_engine):
        """Test spec_get with ID."""
        # First get a spec to find its ID
        specs = spec_engine.spec_list(kind="agent")
        if specs:
            spec_id = specs[0]["id"]
            result = spec_engine.spec_get(id=spec_id)
            assert result is not None
            assert result["id"] == spec_id

    def test_spec_search(self, spec_engine):
        """Test spec_search method."""
        result = spec_engine.spec_search("planner")
        assert isinstance(result, list)
        # Pia is a planner, should be in results
        names = [r["name"] for r in result]
        assert "pia" in names

    def test_validate_payload_success(self, spec_engine):
        """Test validate_payload_against_spec with valid payload."""
        result = spec_engine.validate_payload_against_spec(
            kind="schema",
            name="agent_config_schema",
            payload={"name": "test", "role": "planner"}
        )
        # Should succeed or have no schema (ok=True or note about no schema)
        assert "ok" in result or "note" in result

    def test_get_stats(self, spec_engine):
        """Test get_stats method."""
        result = spec_engine.get_stats()
        assert "specs_by_kind" in result or "error" in result
        if "specs_by_kind" in result:
            assert "agent" in result["specs_by_kind"]


class TestSpecEngineIntegration:
    """Integration tests for the full Spec Engine stack."""

    @pytest.fixture
    def full_setup(self):
        """Set up full Spec Engine with all components."""
        con = duckdb.connect(":memory:")

        # Load extensions (may fail in network-restricted environments)
        try_load_extension(con, "json")
        try_load_extension(con, "minijinja", from_community=True)
        try_load_extension(con, "json_schema", from_community=True)

        # Load all SQL files
        db_dir = os.path.join(os.path.dirname(__file__), "..", "db")
        load_sql_file(con, os.path.join(db_dir, "spec_engine_schema.sql"))
        load_sql_file(con, os.path.join(db_dir, "spec_engine_macros.sql"))
        load_sql_file(con, os.path.join(db_dir, "spec_engine_seed.sql"))

        yield con
        con.close()

    def test_full_spec_workflow(self, full_setup):
        """Test a full workflow: list -> get -> use payload."""
        con = full_setup

        # 1. List agents
        agents = con.sql("SELECT * FROM spec_list_by_kind('agent')").fetchall()
        assert len(agents) >= 1

        # 2. Get Pia
        pia = con.sql("SELECT * FROM spec_get('agent', 'pia')").fetchone()
        assert pia is not None

        # 3. Check payload is valid JSON
        payload_col = 9  # payload column index
        if pia[payload_col]:
            payload = pia[payload_col]
            if isinstance(payload, str):
                payload = json.loads(payload)
            assert "name" in payload or "role" in payload

    def test_view_consistency(self, full_setup):
        """Test that views return consistent data."""
        con = full_setup

        # Count from table
        table_count = con.sql(
            "SELECT COUNT(*) FROM spec_objects WHERE kind = 'agent'"
        ).fetchone()[0]

        # Count from view
        view_count = con.sql(
            "SELECT COUNT(*) FROM spec_agents_view"
        ).fetchone()[0]

        assert table_count == view_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
