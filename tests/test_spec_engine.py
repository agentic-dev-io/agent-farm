"""
Tests for the Spec Engine.

Tests the Python SpecEngine API, seed data integrity,
and regression tests for specific fixed bugs.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import duckdb

from agent_farm.duckdb_utils import (
    load_duckdb_extensions,
)
from agent_farm.extensions import DUCKDB_EXTENSIONS

SPEC_SQL_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "agent_farm", "sql", "spec")


@pytest.fixture
def spec_engine():
    """Create a fully initialized SpecEngine instance."""
    from agent_farm.spec_engine import SpecEngine

    con = duckdb.connect(":memory:")
    load_duckdb_extensions(con, DUCKDB_EXTENSIONS)
    engine = SpecEngine(con)
    engine.initialize()
    yield engine
    con.close()


class TestSpecEngineAPI:
    """Tests for the Python SpecEngine API against real seed data."""

    def test_spec_list_returns_seeded_agents(self, spec_engine):
        result = spec_engine.spec_list(kind="agent")
        assert len(result) >= 1
        names = [r["name"] for r in result]
        assert "pia" in names

    def test_spec_list_filters_by_kind(self, spec_engine):
        agents = spec_engine.spec_list(kind="agent")
        schemas = spec_engine.spec_list(kind="schema")
        assert all(r["kind"] == "agent" for r in agents)
        assert all(r["kind"] == "schema" for r in schemas)

    def test_spec_get_by_kind_name(self, spec_engine):
        result = spec_engine.spec_get(kind="agent", name="pia")
        assert result["name"] == "pia"
        assert result["kind"] == "agent"
        assert result["status"] == "active"

    def test_spec_get_by_id(self, spec_engine):
        specs = spec_engine.spec_list(kind="agent")
        spec_id = specs[0]["id"]
        result = spec_engine.spec_get(id=spec_id)
        assert result["id"] == spec_id

    def test_spec_search(self, spec_engine):
        result = spec_engine.spec_search("planner")
        names = [r["name"] for r in result]
        assert "pia" in names

    def test_validate_payload_against_spec(self, spec_engine):
        result = spec_engine.validate_payload_against_spec(
            kind="schema", name="agent_config_schema", payload={"name": "test", "role": "planner"}
        )
        assert "ok" in result or "note" in result

    def test_get_stats(self, spec_engine):
        result = spec_engine.get_stats()
        assert "specs_by_kind" in result
        assert "agent" in result["specs_by_kind"]


class TestSeedData:
    """Verify seed data covers all expected kinds and minimum counts."""

    def test_seed_coverage(self, spec_engine):
        stats = spec_engine.get_stats()["specs_by_kind"]
        assert stats["agent"]["total"] >= 1
        assert stats["skill"]["total"] >= 3
        assert stats["schema"]["total"] >= 3
        assert stats["org"]["total"] >= 5

    def test_pia_agent_has_payload(self, spec_engine):
        pia = spec_engine.spec_get(kind="agent", name="pia")
        assert pia["payload"] is not None
        payload = pia["payload"] if isinstance(pia["payload"], dict) else json.loads(pia["payload"])
        assert "name" in payload or "role" in payload


class TestSpecEngineRegressions:
    """Regression tests for specific fixed bugs."""

    def test_http_start_helper_uses_parameter_binding(self):
        from agent_farm.duckdb_utils import start_http_server

        class FakeConnection:
            def __init__(self):
                self.calls = []

            def execute(self, query, params):
                self.calls.append((query, params))
                return self

        fake = FakeConnection()
        start_http_server(fake, 9999, "secret")

        assert fake.calls == [
            ("SELECT httpserve_start(?, ?, ?)", ["0.0.0.0", 9999, "X-API-Key secret"])
        ]

    def test_get_spec_engine_is_cached_per_connection(self):
        from agent_farm import spec_engine as spec_module

        spec_module._spec_engines.clear()

        con1 = duckdb.connect(":memory:")
        con2 = duckdb.connect(":memory:")
        load_duckdb_extensions(con1, DUCKDB_EXTENSIONS)
        load_duckdb_extensions(con2, DUCKDB_EXTENSIONS)
        try:
            engine1 = spec_module.get_spec_engine(con1, quiet=True)
            engine1_again = spec_module.get_spec_engine(con1)
            engine2 = spec_module.get_spec_engine(con2, quiet=True)

            assert engine1 is engine1_again
            assert engine1 is not engine2

            with pytest.raises(ValueError, match="Multiple SpecEngine instances are active"):
                spec_module.get_spec_engine()
        finally:
            con1.close()
            con2.close()
            spec_module._spec_engines.clear()

    @pytest.fixture
    def intelligence_setup(self):
        from agent_farm.duckdb_utils import has_non_comment_content, split_sql_statements

        con = duckdb.connect(":memory:")
        filepath = os.path.join(SPEC_SQL_DIR, "intelligence.sql")
        with open(filepath, "r", encoding="utf-8") as f:
            sql_content = f.read()
        for stmt in split_sql_statements(sql_content):
            stmt = stmt.strip()
            if has_non_comment_content(stmt):
                con.sql(stmt)
        yield con
        con.close()

    def test_store_embedding_persists_chunk_index(self, intelligence_setup):
        from agent_farm.spec_engine import SpecEngine

        engine = SpecEngine(intelligence_setup)

        first = engine.store_embedding(
            "chunked content",
            [0.1, 0.2],
            "doc",
            chunk_index=3,
            metadata={"section": "intro"},
        )
        second = engine.store_embedding(
            "chunked content",
            [0.3, 0.4],
            "doc",
            chunk_index=3,
            metadata={"section": "updated"},
        )

        assert first["embedding_id"] == second["embedding_id"]
        row = intelligence_setup.execute(
            """
            SELECT chunk_index, embedding_model, metadata
            FROM spec_embeddings
            WHERE id = ?
            """,
            [first["embedding_id"]],
        ).fetchone()

        assert row[0] == 3
        assert row[1] == "default"
        assert json.loads(row[2]) == {"section": "updated"}

    def test_store_org_knowledge_supports_full_studio_and_ops_fields(self, intelligence_setup):
        from agent_farm.spec_engine import SpecEngine

        engine = SpecEngine(intelligence_setup)

        studio = engine.store_org_knowledge(
            "studio",
            "Decision body",
            options=[{"name": "A"}, {"name": "B"}],
            chosen_option="A",
            rationale="Clearer hierarchy",
            user_feedback={"approved": True},
            performance=0.8,
        )
        ops = engine.store_org_knowledge(
            "ops",
            "Deploy finished",
            artifact_refs=["artifacts/build.log"],
            metrics={"latency_ms": 82},
            duration_ms=1200,
        )

        studio_row = intelligence_setup.execute(
            """
            SELECT options, chosen_option, user_feedback, performance
            FROM knowledge_studio
            WHERE id = ?
            """,
            [studio["entry_id"]],
        ).fetchone()
        ops_row = intelligence_setup.execute(
            """
            SELECT artifact_refs, metrics, duration_ms
            FROM knowledge_ops
            WHERE id = ?
            """,
            [ops["entry_id"]],
        ).fetchone()

        assert json.loads(studio_row[0]) == [{"name": "A"}, {"name": "B"}]
        assert studio_row[1] == "A"
        assert json.loads(studio_row[2]) == {"approved": True}
        assert studio_row[3] == pytest.approx(0.8)

        assert ops_row[0] == ["artifacts/build.log"]
        assert json.loads(ops_row[1]) == {"latency_ms": 82}
        assert ops_row[2] == 1200

    def test_vector_search_methods_fail_clearly_without_vss(self, intelligence_setup):
        from agent_farm.spec_engine import SpecEngine

        engine = SpecEngine(intelligence_setup)

        with pytest.raises(RuntimeError, match="requires the DuckDB 'vss' extension"):
            engine.search_similar([0.1, 0.2])

        with pytest.raises(RuntimeError, match="requires the DuckDB 'vss' extension"):
            engine.hybrid_search("query", [0.1, 0.2])
