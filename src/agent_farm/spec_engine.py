"""
Spec Engine - DuckDB-based Specification Management System

The Spec Engine is the central "Spec-OS" for all agents, managing:
- Agents, skills, workflows
- APIs/protocols (HTTP/MCP/OpenAPI/GraphQL)
- JSON Schemas (for validation)
- Prompt/plan templates (MiniJinja)
- Task templates, UIs, Open-Responses

MCP Tools exposed:
- spec_list: List specs by kind with optional filters
- spec_get: Get a single spec by ID or kind+name
- spec_search: Search specs by query string
- render_from_template: Render MiniJinja templates
- validate_payload_against_spec: Validate JSON against schemas
- mcp_query_remote: Query remote MCP servers
- mcp_call_remote_tool: Call remote MCP tools
"""

import json
import os
import sys
from pathlib import Path
from threading import Lock
from typing import Any

import duckdb


class SpecEngine:
    """
    The Spec Engine manages all specifications in the Agent Farm.
    Uses DuckDB with extensions: minijinja, json_schema, duckdb_mcp, httpserver.
    """

    def __init__(self, con: duckdb.DuckDBPyConnection, db_path: str | None = None):
        """
        Initialize the Spec Engine.

        Args:
            con: DuckDB connection to use
            db_path: Optional path to persist the database
        """
        self.con = con
        self.db_path = db_path or os.environ.get("SPEC_ENGINE_DB", "db/spec_engine.db")
        self._initialized = False

    def initialize(self) -> None:
        """
        Initialize the Spec Engine database, loading extensions, schema, macros, and seed data.
        """
        if self._initialized:
            return

        print("Initializing Spec Engine...", file=sys.stderr)

        # Load extensions
        self._load_extensions()

        # Load schema
        self._load_schema()

        # Register internal UDFs before loading SQL macros that depend on them.
        self._register_internal_udfs()

        # Load macros
        self._load_macros()

        # Load seed data (if tables are empty)
        self._load_seed_data()

        self._initialized = True
        print("Spec Engine initialized successfully.", file=sys.stderr)

    def _load_extensions(self) -> None:
        """Load required DuckDB extensions."""
        extensions = [
            ("minijinja", True),  # Template rendering
            ("json_schema", True),  # JSON Schema validation
            ("duckdb_mcp", True),  # MCP integration
            ("httpserver", False),  # HTTP API (optional)
            ("json", True),  # JSON support
            ("httpfs", False),  # HTTP filesystem
            ("http_client", False),  # HTTP client
        ]

        for ext, required in extensions:
            try:
                # Try standard install first
                self.con.sql(f"INSTALL {ext};")
                self.con.sql(f"LOAD {ext};")
                print(f"Spec Engine: Loaded {ext}", file=sys.stderr)
            except Exception:
                try:
                    # Try community install
                    self.con.sql(f"INSTALL {ext} FROM community;")
                    self.con.sql(f"LOAD {ext};")
                    print(f"Spec Engine: Loaded {ext} from community", file=sys.stderr)
                except Exception as e:
                    if required:
                        print(f"Spec Engine: REQUIRED extension {ext} failed: {e}", file=sys.stderr)
                    else:
                        print(
                            f"Spec Engine: Optional extension {ext} skipped: {e}", file=sys.stderr
                        )

    def _has_non_comment_content(self, stmt: str) -> bool:
        """Check if a SQL statement has any non-comment content."""
        for ln in stmt.split("\n"):
            ln = ln.strip()
            if ln and not ln.startswith("--"):
                return True
        return False

    def _render_template(self, template_str: str | None, context_json: str | None) -> str | None:
        """Render a MiniJinja template via parameter binding."""
        if not template_str:
            return None

        context_json = context_json or "{}"
        result = self.con.execute(
            "SELECT minijinja_render(?, ?)",
            [template_str, context_json],
        ).fetchone()
        return result[0] if result else None

    def _register_internal_udfs(self) -> None:
        """Register internal helper UDFs used by SQL macros."""

        def spec_render_template_udf(template_name: str, context_json: str) -> str | None:
            template = self.con.execute(
                """
                SELECT p.payload->>'template'
                FROM spec_objects o
                JOIN spec_payloads p ON p.object_id = o.id
                WHERE o.kind IN ('task_template', 'prompt_template')
                  AND o.name = ?
                  AND o.status = 'active'
                ORDER BY o.version DESC
                LIMIT 1
                """,
                [template_name],
            ).fetchone()
            return self._render_template(template[0] if template else None, context_json)

        def spec_render_template_version_udf(
            template_name: str,
            version_name: str,
            context_json: str,
        ) -> str | None:
            template = self.con.execute(
                """
                SELECT p.payload->>'template'
                FROM spec_objects o
                JOIN spec_payloads p ON p.object_id = o.id
                WHERE o.kind IN ('task_template', 'prompt_template')
                  AND o.name = ?
                  AND o.version = ?
                LIMIT 1
                """,
                [template_name, version_name],
            ).fetchone()
            return self._render_template(template[0] if template else None, context_json)

        def spec_render_direct_udf(template_str: str, context_json: str) -> str | None:
            return self._render_template(template_str, context_json)

        internal_udfs = [
            ("spec_render_template_udf", spec_render_template_udf, [str, str]),
            (
                "spec_render_template_version_udf",
                spec_render_template_version_udf,
                [str, str, str],
            ),
            ("spec_render_direct_udf", spec_render_direct_udf, [str, str]),
        ]

        for name, func, params in internal_udfs:
            try:
                self.con.remove_function(name)
            except Exception:
                pass
            self.con.create_function(
                name,
                func,
                params,
                str,
                null_handling="special",
            )

    def _next_id(self, sequence_name: str) -> int:
        """Get the next ID from a known sequence."""
        return self.con.execute(f"SELECT nextval('{sequence_name}')").fetchone()[0]

    def _load_sql_file(self, filepath: str) -> int:
        """Load and execute a SQL file, returning number of statements executed."""
        if not os.path.exists(filepath):
            print(f"Spec Engine: SQL file not found: {filepath}", file=sys.stderr)
            return 0

        with open(filepath, "r", encoding="utf-8") as f:
            sql_content = f.read()

        # Split into statements
        statements = self._split_sql(sql_content)
        executed = 0
        errors: list[str] = []

        for stmt in statements:
            stmt = stmt.strip()
            # Check for non-comment content (handles statements starting with comments)
            if not self._has_non_comment_content(stmt):
                continue
            try:
                self.con.sql(stmt)
                executed += 1
            except Exception as e:
                errors.append(f"{e}\n  Statement: {stmt[:100]}...")

        if errors:
            joined = "\n".join(errors[:20])
            raise RuntimeError(f"Spec Engine: Error in {filepath}:\n{joined}")

        return executed

    def _split_sql(self, sql_content: str) -> list[str]:
        """Split SQL content into statements, respecting string literals."""
        statements = []
        current = []
        in_string = False
        string_char = None

        i = 0
        while i < len(sql_content):
            char = sql_content[i]

            if char in ("'", '"') and not in_string:
                in_string = True
                string_char = char
                current.append(char)
            elif char == string_char and in_string:
                if i + 1 < len(sql_content) and sql_content[i + 1] == string_char:
                    current.append(char)
                    current.append(char)
                    i += 1
                else:
                    in_string = False
                    string_char = None
                    current.append(char)
            elif char == ";" and not in_string:
                stmt = "".join(current).strip()
                # Use _has_non_comment_content to properly check for real SQL
                if stmt and self._has_non_comment_content(stmt):
                    statements.append(stmt)
                current = []
            else:
                current.append(char)
            i += 1

        if current:
            stmt = "".join(current).strip()
            if stmt and self._has_non_comment_content(stmt):
                statements.append(stmt)

        return statements

    def _load_schema(self) -> None:
        """Load the Spec Engine schema including intelligence layer."""
        db_dir = Path(__file__).parent / "sql" / "spec"

        # Core schema
        schema_path = db_dir / "schema.sql"
        count = self._load_sql_file(str(schema_path))
        print(f"Spec Engine: Loaded schema ({count} statements)", file=sys.stderr)

        # Intelligence layer (embeddings, knowledge bases)
        intel_path = db_dir / "intelligence.sql"
        if intel_path.exists():
            intel_count = self._load_sql_file(str(intel_path))
            print(
                f"Spec Engine: Loaded intelligence layer ({intel_count} statements)",
                file=sys.stderr,
            )

    def _load_macros(self) -> None:
        """Load the Spec Engine macros including RAG macros."""
        db_dir = Path(__file__).parent / "sql" / "spec"

        # Core macros
        macros_path = db_dir / "macros.sql"
        count = self._load_sql_file(str(macros_path))
        print(f"Spec Engine: Loaded macros ({count} macros)", file=sys.stderr)

        # RAG/hybrid search macros
        rag_path = db_dir / "rag.sql"
        if rag_path.exists():
            rag_count = self._load_sql_file(str(rag_path))
            print(f"Spec Engine: Loaded RAG macros ({rag_count} macros)", file=sys.stderr)

    def _load_seed_data(self) -> None:
        """Load seed data if tables are empty."""
        try:
            result = self.con.sql("SELECT COUNT(*) FROM spec_objects").fetchone()
            if result and result[0] > 0:
                print(
                    f"Spec Engine: {result[0]} specs already exist, skipping seed", file=sys.stderr
                )
                return
        except Exception:
            pass  # Table might not exist yet

        db_dir = Path(__file__).parent / "sql" / "spec"
        seed_path = db_dir / "seed.sql"
        count = self._load_sql_file(str(seed_path))
        print(f"Spec Engine: Loaded seed data ({count} statements)", file=sys.stderr)

    # =========================================================================
    # MCP Tool Implementations
    # =========================================================================

    def spec_list(
        self,
        kind: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        List specs by kind with optional filters.

        Args:
            kind: Filter by spec kind (agent, skill, api, etc.)
            status: Filter by status (draft, active, deprecated)
            limit: Maximum number of results

        Returns:
            List of spec objects with id, kind, name, version, status, summary
        """
        query = "SELECT id, kind, name, version, status, summary FROM spec_objects WHERE 1=1"
        params = []

        if kind:
            query += " AND kind = ?"
            params.append(kind)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY kind, name, version DESC LIMIT ?"
        params.append(limit)

        result = self.con.execute(query, params).fetchall()
        columns = ["id", "kind", "name", "version", "status", "summary"]
        return [dict(zip(columns, row)) for row in result]

    def spec_get(
        self,
        id: int | None = None,
        kind: str | None = None,
        name: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a single spec by ID or by kind+name.

        Args:
            id: Spec ID (if provided, kind/name/version are ignored)
            kind: Spec kind
            name: Spec name
            version: Spec version (optional, defaults to latest)

        Returns:
            Full spec object with id, kind, name, version, status, summary, doc, payload, schema_ref
        """
        if id is not None:
            query = """
                SELECT
                    o.id, o.kind, o.name, o.version, o.status, o.summary,
                    o.created_at, o.updated_at,
                    d.doc,
                    p.payload,
                    p.schema_ref
                FROM spec_objects o
                LEFT JOIN spec_docs d ON d.object_id = o.id
                LEFT JOIN spec_payloads p ON p.object_id = o.id
                WHERE o.id = ?
            """
            result = self.con.execute(query, [id]).fetchone()
        elif kind and name:
            query = """
                SELECT
                    o.id, o.kind, o.name, o.version, o.status, o.summary,
                    o.created_at, o.updated_at,
                    d.doc,
                    p.payload,
                    p.schema_ref
                FROM spec_objects o
                LEFT JOIN spec_docs d ON d.object_id = o.id
                LEFT JOIN spec_payloads p ON p.object_id = o.id
                WHERE o.kind = ? AND o.name = ?
            """
            params = [kind, name]
            if version:
                query += " AND o.version = ?"
                params.append(version)
            else:
                query += " ORDER BY o.version DESC"
            query += " LIMIT 1"
            result = self.con.execute(query, params).fetchone()
        else:
            return None

        if not result:
            return None

        columns = [
            "id",
            "kind",
            "name",
            "version",
            "status",
            "summary",
            "created_at",
            "updated_at",
            "doc",
            "payload",
            "schema_ref",
        ]
        spec = dict(zip(columns, result))

        # Parse JSON payload if it's a string
        if spec.get("payload") and isinstance(spec["payload"], str):
            try:
                spec["payload"] = json.loads(spec["payload"])
            except json.JSONDecodeError:
                pass

        # Convert timestamps to strings
        for ts_field in ["created_at", "updated_at"]:
            if spec.get(ts_field):
                spec[ts_field] = str(spec[ts_field])

        return spec

    def spec_search(
        self, query: str, kind: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Search specs by query string.

        Splits multi-word queries so all words must match (AND logic), making
        'web search' find ddg_instant, brave_search etc. even when the words
        are not adjacent in the summary.

        Args:
            query: Search query (searches name, summary, and docs)
            kind: Optional kind filter (e.g. 'macro', 'agent', 'skill')
            limit: Maximum number of results

        Returns:
            List of matching specs
        """
        words = [w.strip() for w in query.lower().split() if w.strip()]
        if not words:
            return []

        # Build AND condition: every word must appear in name OR summary OR doc
        word_clauses = " AND ".join(
            f"(LOWER(o.name) LIKE '%' || ? || '%' "
            f"OR LOWER(o.summary) LIKE '%' || ? || '%' "
            f"OR LOWER(COALESCE(d.doc,'')) LIKE '%' || ? || '%')"
            for _ in words
        )
        kind_clause = "AND o.kind = ?" if kind else ""
        search_query = f"""
            SELECT DISTINCT o.id, o.kind, o.name, o.version, o.status, o.summary
            FROM spec_objects o
            LEFT JOIN spec_docs d ON d.object_id = o.id
            WHERE {word_clauses}
            {kind_clause}
            ORDER BY
                CASE WHEN LOWER(o.name) LIKE ? || '%' THEN 0 ELSE 1 END,
                o.kind, o.name
            LIMIT ?
        """
        params = []
        for w in words:
            params.extend([w, w, w])
        if kind:
            params.append(kind)
        params.extend([words[0], limit])

        result = self.con.execute(search_query, params).fetchall()
        columns = ["id", "kind", "name", "version", "status", "summary"]
        return [dict(zip(columns, row)) for row in result]

    def render_from_template(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Render a MiniJinja template with context.

        Args:
            template_name: Name of the template spec
            context: Context dictionary for template rendering

        Returns:
            Dict with 'rendered' key containing the rendered string
        """
        try:
            # Get the template from spec_payloads
            template_query = """
                SELECT p.payload->>'template'
                FROM spec_objects o
                JOIN spec_payloads p ON p.object_id = o.id
                WHERE o.kind IN ('task_template', 'prompt_template')
                  AND o.name = ?
                  AND o.status = 'active'
                ORDER BY o.version DESC
                LIMIT 1
            """
            result = self.con.execute(template_query, [template_name]).fetchone()

            if not result or not result[0]:
                return {"error": f"Template '{template_name}' not found", "rendered": None}

            template_str = result[0]

            # Render using minijinja
            render_query = "SELECT minijinja_render(?, ?)"
            context_json = json.dumps(context)
            rendered = self.con.execute(render_query, [template_str, context_json]).fetchone()

            if rendered:
                return {"rendered": rendered[0]}
            return {"error": "Rendering failed", "rendered": None}

        except Exception as e:
            return {"error": str(e), "rendered": None}

    def validate_payload_against_spec(
        self,
        kind: str,
        name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate a JSON payload against a spec's schema.

        Args:
            kind: Spec kind to validate against
            name: Spec name (should be a 'schema' kind or have schema_ref)
            payload: JSON payload to validate

        Returns:
            Dict with 'ok' boolean and 'errors' list
        """
        try:
            # If kind is 'schema', use that directly
            # Otherwise, look up the schema_ref
            if kind == "schema":
                schema_query = """
                    SELECT p.payload
                    FROM spec_objects o
                    JOIN spec_payloads p ON p.object_id = o.id
                    WHERE o.kind = 'schema'
                      AND o.name = ?
                      AND o.status = 'active'
                    ORDER BY o.version DESC
                    LIMIT 1
                """
                result = self.con.execute(schema_query, [name]).fetchone()
            else:
                # Get schema_ref from the spec
                ref_query = """
                    SELECT p.schema_ref
                    FROM spec_objects o
                    JOIN spec_payloads p ON p.object_id = o.id
                    WHERE o.kind = ?
                      AND o.name = ?
                      AND o.status = 'active'
                    ORDER BY o.version DESC
                    LIMIT 1
                """
                ref_result = self.con.execute(ref_query, [kind, name]).fetchone()
                if not ref_result or not ref_result[0]:
                    return {"ok": True, "errors": [], "note": "No schema_ref defined for this spec"}

                schema_ref = ref_result[0]

                # Now get the actual schema
                schema_query = """
                    SELECT p.payload
                    FROM spec_objects o
                    JOIN spec_payloads p ON p.object_id = o.id
                    WHERE o.kind = 'schema'
                      AND o.name = ?
                      AND o.status = 'active'
                    ORDER BY o.version DESC
                    LIMIT 1
                """
                result = self.con.execute(schema_query, [schema_ref]).fetchone()

            if not result or not result[0]:
                return {"ok": False, "errors": [f"Schema not found: {name}"]}

            schema_json = result[0]
            if isinstance(schema_json, str):
                schema_json = json.loads(schema_json)

            # Validate using json_schema extension
            validate_query = "SELECT json_schema_validate(?, ?)"
            payload_json = json.dumps(payload)
            schema_str = json.dumps(schema_json)

            validation_result = self.con.execute(
                validate_query, [schema_str, payload_json]
            ).fetchone()

            if validation_result and validation_result[0]:
                # Non-empty result means validation errors
                errors = validation_result[0]
                if isinstance(errors, str):
                    try:
                        errors = json.loads(errors)
                    except json.JSONDecodeError:
                        errors = [errors]
                return {"ok": False, "errors": errors if isinstance(errors, list) else [errors]}

            return {"ok": True, "errors": []}

        except Exception as e:
            return {"ok": False, "errors": [str(e)]}

    def mcp_query_remote(self, server: str, resource_uri: str) -> dict[str, Any]:
        """
        Query a remote MCP server for a resource.

        Args:
            server: MCP server name
            resource_uri: Resource URI to fetch

        Returns:
            Dict with resource data or error
        """
        try:
            query = "SELECT mcp_get_resource(?, ?)"
            result = self.con.execute(query, [server, resource_uri]).fetchone()
            if result:
                data = result[0]
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        pass
                return {"data": data}
            return {"error": "No result from remote MCP server"}
        except Exception as e:
            return {"error": str(e)}

    def mcp_call_remote_tool(
        self,
        server: str,
        tool: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call a remote MCP tool.

        Args:
            server: MCP server name
            tool: Tool name to call
            args: Arguments to pass to the tool

        Returns:
            Dict with tool result or error
        """
        try:
            query = "SELECT mcp_call_tool(?, ?, ?)"
            args_json = json.dumps(args)
            result = self.con.execute(query, [server, tool, args_json]).fetchone()
            if result:
                data = result[0]
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        pass
                return {"result": data}
            return {"error": "No result from remote MCP tool"}
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # HTTP Server Management
    # =========================================================================

    def start_http_server(self, port: int = 9999, api_key: str | None = None) -> bool:
        """
        Start the HTTP server for non-MCP clients.

        Args:
            port: Port to listen on
            api_key: Optional API key for authentication

        Returns:
            True if started successfully
        """
        try:
            auth = f"X-API-Key {api_key}" if api_key else ""
            auth_escaped = auth.replace("'", "''")
            self.con.sql(f"SELECT httpserve_start('0.0.0.0', {port}, '{auth_escaped}')")
            print(f"Spec Engine: HTTP server started on port {port}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"Spec Engine: Failed to start HTTP server: {e}", file=sys.stderr)
            return False

    def stop_http_server(self) -> bool:
        """Stop the HTTP server."""
        try:
            self.con.sql("SELECT httpserve_stop()")
            print("Spec Engine: HTTP server stopped", file=sys.stderr)
            return True
        except Exception as e:
            print(f"Spec Engine: Failed to stop HTTP server: {e}", file=sys.stderr)
            return False

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def spec_create(
        self,
        kind: str,
        name: str,
        summary: str,
        version: str = "1.0.0",
        status: str = "draft",
        doc: str | None = None,
        payload: dict[str, Any] | None = None,
        schema_ref: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new spec.

        Args:
            kind: Spec kind (agent, skill, api, etc.)
            name: Spec name
            summary: Brief description
            version: Version string (default: 1.0.0)
            status: Status (draft, active, deprecated)
            doc: Optional documentation (markdown)
            payload: Optional JSON payload
            schema_ref: Optional reference to a schema for validation

        Returns:
            Dict with created spec id or error
        """
        try:
            next_id = self._next_id("spec_objects_seq")

            # Insert spec object
            self.con.execute(
                """
                INSERT INTO spec_objects (id, kind, name, version, status, summary)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [next_id, kind, name, version, status, summary],
            )

            # Insert doc if provided
            if doc:
                doc_id = self._next_id("spec_docs_seq")
                self.con.execute(
                    "INSERT INTO spec_docs (id, object_id, doc) VALUES (?, ?, ?)",
                    [doc_id, next_id, doc],
                )

            # Insert payload if provided
            if payload is not None:
                payload_id = self._next_id("spec_payloads_seq")
                payload_json = json.dumps(payload) if isinstance(payload, dict) else payload
                self.con.execute(
                    "INSERT INTO spec_payloads (id, object_id, payload, schema_ref)"
                    " VALUES (?, ?, ?, ?)",
                    [payload_id, next_id, payload_json, schema_ref],
                )

            return {"id": next_id, "created": True}

        except Exception as e:
            return {"error": str(e), "created": False}

    def spec_update(
        self,
        id: int,
        version: str | None = None,
        status: str | None = None,
        summary: str | None = None,
        doc: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing spec.

        Args:
            id: Spec ID to update
            version: New version (optional)
            status: New status (optional)
            summary: New summary (optional)
            doc: New documentation (optional)
            payload: New payload (optional)

        Returns:
            Dict with success status or error
        """
        try:
            updates = []
            params = []

            if version:
                updates.append("version = ?")
                params.append(version)
            if status:
                updates.append("status = ?")
                params.append(status)
            if summary:
                updates.append("summary = ?")
                params.append(summary)

            if updates:
                updates.append("updated_at = current_timestamp")
                params.append(id)
                self.con.execute(
                    f"UPDATE spec_objects SET {', '.join(updates)} WHERE id = ?", params
                )

            if doc is not None:
                # Update or insert doc
                existing = self.con.execute(
                    "SELECT id FROM spec_docs WHERE object_id = ?", [id]
                ).fetchone()
                if existing:
                    self.con.execute("UPDATE spec_docs SET doc = ? WHERE object_id = ?", [doc, id])
                else:
                    doc_id = self._next_id("spec_docs_seq")
                    self.con.execute(
                        "INSERT INTO spec_docs (id, object_id, doc) VALUES (?, ?, ?)",
                        [doc_id, id, doc],
                    )

            if payload is not None:
                payload_json = json.dumps(payload) if isinstance(payload, dict) else payload
                existing = self.con.execute(
                    "SELECT id FROM spec_payloads WHERE object_id = ?", [id]
                ).fetchone()
                if existing:
                    self.con.execute(
                        "UPDATE spec_payloads SET payload = ? WHERE object_id = ?",
                        [payload_json, id],
                    )
                else:
                    payload_id = self._next_id("spec_payloads_seq")
                    self.con.execute(
                        "INSERT INTO spec_payloads (id, object_id, payload) VALUES (?, ?, ?)",
                        [payload_id, id, payload_json],
                    )

            return {"updated": True}

        except Exception as e:
            return {"error": str(e), "updated": False}

    def spec_delete(self, id: int) -> dict[str, Any]:
        """
        Delete a spec by ID.

        Args:
            id: Spec ID to delete

        Returns:
            Dict with success status or error
        """
        try:
            # Delete related records first (no foreign key cascade in our schema)
            self.con.execute("DELETE FROM spec_docs WHERE object_id = ?", [id])
            self.con.execute("DELETE FROM spec_payloads WHERE object_id = ?", [id])
            self.con.execute("DELETE FROM spec_objects WHERE id = ?", [id])
            return {"deleted": True}
        except Exception as e:
            return {"error": str(e), "deleted": False}

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the Spec Engine."""
        try:
            stats_query = """
                SELECT
                    kind,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'active') AS active,
                    COUNT(*) FILTER (WHERE status = 'draft') AS draft,
                    COUNT(*) FILTER (WHERE status = 'deprecated') AS deprecated
                FROM spec_objects
                GROUP BY kind
                ORDER BY kind
            """
            result = self.con.execute(stats_query).fetchall()
            stats = {}
            for row in result:
                stats[row[0]] = {
                    "total": row[1],
                    "active": row[2],
                    "draft": row[3],
                    "deprecated": row[4],
                }
            return {"specs_by_kind": stats}
        except Exception as e:
            return {"error": str(e)}

    def get_loaded_extensions(self) -> list[str]:
        """Get list of loaded DuckDB extensions."""
        try:
            result = self.con.execute(
                "SELECT extension_name FROM duckdb_extensions() WHERE loaded = true"
            ).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            print(f"Spec Engine: Error getting extensions: {e}", file=sys.stderr)
            return []

    def get_spec_kinds(self) -> list[str]:
        """Get list of all spec kinds in use."""
        try:
            result = self.con.execute(
                "SELECT DISTINCT kind FROM spec_objects ORDER BY kind"
            ).fetchall()
            return [row[0] for row in result]
        except Exception:
            return []

    def is_initialized(self) -> bool:
        """Check if the Spec Engine is initialized."""
        return self._initialized

    # =========================================================================
    # Meta-Learning Methods (Self-Improvement)
    # =========================================================================

    def record_usage(self, spec_id: int, was_success: bool) -> dict[str, Any]:
        """
        Record that a spec was used and whether it was successful.
        Updates use_count and success_rate.

        Args:
            spec_id: ID of the spec that was used
            was_success: Whether the usage was successful

        Returns:
            Dict with updated stats
        """
        try:
            # Get current values
            result = self.con.execute(
                "SELECT use_count, success_rate FROM spec_objects WHERE id = ?", [spec_id]
            ).fetchone()

            if not result:
                return {"error": f"Spec {spec_id} not found"}

            use_count, success_rate = result

            # Calculate new success rate
            if use_count == 0:
                new_success_rate = 1.0 if was_success else 0.0
            else:
                new_success_rate = (success_rate * use_count + (1.0 if was_success else 0.0)) / (
                    use_count + 1
                )

            # Update
            self.con.execute(
                """
                UPDATE spec_objects
                SET use_count = use_count + 1,
                    success_rate = ?,
                    updated_at = current_timestamp
                WHERE id = ?
                """,
                [new_success_rate, spec_id],
            )

            return {
                "spec_id": spec_id,
                "use_count": use_count + 1,
                "success_rate": new_success_rate,
            }

        except Exception as e:
            return {"error": str(e)}

    def record_feedback(
        self,
        spec_id: int,
        feedback_type: str,
        score: float = 0.0,
        context: dict | None = None,
        outcome: dict | None = None,
        notes: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Record feedback on a spec's usage.

        Args:
            spec_id: ID of the spec
            feedback_type: Type of feedback ('success', 'failure', 'error', 'user_correction')
            score: Numeric score (-1.0 to 1.0)
            context: JSON context of the usage
            outcome: JSON outcome/result
            notes: Human-readable notes
            session_id: Session ID

        Returns:
            Dict with feedback ID
        """
        try:
            feedback_id = self._next_id("spec_feedback_seq")

            self.con.execute(
                """
                INSERT INTO spec_feedback
                    (id, spec_id, session_id, feedback_type,
                     context, outcome, score, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    feedback_id,
                    spec_id,
                    session_id,
                    feedback_type,
                    json.dumps(context) if context else None,
                    json.dumps(outcome) if outcome else None,
                    score,
                    notes,
                ],
            )

            # Also update usage stats
            was_success = feedback_type == "success" or score > 0.5
            self.record_usage(spec_id, was_success)

            return {"feedback_id": feedback_id}

        except Exception as e:
            return {"error": str(e)}

    def create_relationship(
        self,
        from_id: int,
        to_id: int,
        rel_type: str,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        Create a relationship between two specs.

        Args:
            from_id: Source spec ID
            to_id: Target spec ID
            rel_type: Relationship type
                ('uses', 'extends', 'requires', 'implements', 'derived_from')
            metadata: Optional metadata about the relationship

        Returns:
            Dict with relationship ID
        """
        try:
            rel_id = self._next_id("spec_relationships_seq")

            self.con.execute(
                """
                INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (from_id, to_id, rel_type) DO UPDATE SET metadata = EXCLUDED.metadata
                """,
                [rel_id, from_id, to_id, rel_type, json.dumps(metadata) if metadata else None],
            )

            return {"relationship_id": rel_id}

        except Exception as e:
            return {"error": str(e)}

    def get_related_specs(self, spec_id: int) -> list[dict[str, Any]]:
        """
        Get all specs related to a given spec.

        Args:
            spec_id: Spec ID to find relations for

        Returns:
            List of related specs with relationship info
        """
        try:
            query = """
                SELECT
                    r.rel_type,
                    'outgoing' as direction,
                    o.id, o.kind, o.name, o.version, o.status, o.summary
                FROM spec_relationships r
                JOIN spec_objects o ON o.id = r.to_id
                WHERE r.from_id = ?
                UNION ALL
                SELECT
                    r.rel_type,
                    'incoming' as direction,
                    o.id, o.kind, o.name, o.version, o.status, o.summary
                FROM spec_relationships r
                JOIN spec_objects o ON o.id = r.from_id
                WHERE r.to_id = ?
            """
            result = self.con.execute(query, [spec_id, spec_id]).fetchall()

            columns = [
                "rel_type",
                "direction",
                "id",
                "kind",
                "name",
                "version",
                "status",
                "summary",
            ]
            return [dict(zip(columns, row)) for row in result]

        except Exception:
            return []

    def get_spec_performance(self, spec_id: int) -> dict[str, Any]:
        """
        Get performance metrics for a spec.

        Args:
            spec_id: Spec ID

        Returns:
            Dict with performance metrics
        """
        try:
            query = """
                SELECT
                    o.id, o.kind, o.name,
                    o.use_count,
                    o.success_rate,
                    o.confidence,
                    COUNT(f.id) AS feedback_count,
                    AVG(f.score) AS avg_score,
                    COUNT(a.id) AS adaptation_count
                FROM spec_objects o
                LEFT JOIN spec_feedback f ON f.spec_id = o.id
                LEFT JOIN spec_adaptations a ON a.spec_id = o.id
                WHERE o.id = ?
                GROUP BY o.id, o.kind, o.name, o.use_count, o.success_rate, o.confidence
            """
            result = self.con.execute(query, [spec_id]).fetchone()

            if not result:
                return {"error": f"Spec {spec_id} not found"}

            columns = [
                "id",
                "kind",
                "name",
                "use_count",
                "success_rate",
                "confidence",
                "feedback_count",
                "avg_score",
                "adaptation_count",
            ]
            return dict(zip(columns, result))

        except Exception as e:
            return {"error": str(e)}

    def get_specs_needing_improvement(
        self,
        min_usage: int = 5,
        max_success_rate: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Get specs that have low success rates and might need improvement.

        Args:
            min_usage: Minimum usage count to consider
            max_success_rate: Maximum success rate to include

        Returns:
            List of specs needing improvement
        """
        try:
            query = """
                SELECT
                    id, kind, name, version, status,
                    use_count, success_rate, confidence,
                    summary
                FROM spec_objects
                WHERE use_count >= ?
                  AND success_rate < ?
                  AND status = 'active'
                ORDER BY success_rate ASC, use_count DESC
            """
            result = self.con.execute(query, [min_usage, max_success_rate]).fetchall()

            columns = [
                "id",
                "kind",
                "name",
                "version",
                "status",
                "use_count",
                "success_rate",
                "confidence",
                "summary",
            ]
            return [dict(zip(columns, row)) for row in result]

        except Exception:
            return []

    def record_adaptation(
        self,
        spec_id: int,
        adaptation_type: str,
        reason: str,
        changes: dict,
        metrics_before: dict | None = None,
        metrics_after: dict | None = None,
    ) -> dict[str, Any]:
        """
        Record an adaptation made to a spec.

        Args:
            spec_id: Original spec ID
            adaptation_type: Type ('parameter_tune', 'prompt_improve', 'tool_add', 'merge', 'split')
            reason: Why the adaptation was made
            changes: JSON describing the changes
            metrics_before: Metrics before adaptation
            metrics_after: Metrics after adaptation

        Returns:
            Dict with adaptation ID
        """
        try:
            adaptation_id = self._next_id("spec_adaptations_seq")

            self.con.execute(
                """
                INSERT INTO spec_adaptations
                    (id, spec_id, adaptation_type, reason,
                     changes, metrics_before, metrics_after)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    adaptation_id,
                    spec_id,
                    adaptation_type,
                    reason,
                    json.dumps(changes),
                    json.dumps(metrics_before) if metrics_before else None,
                    json.dumps(metrics_after) if metrics_after else None,
                ],
            )

            return {"adaptation_id": adaptation_id}

        except Exception as e:
            return {"error": str(e)}

    def record_learning(
        self,
        learning_type: str,
        category: str,
        description: str,
        evidence: list | None = None,
        confidence: float = 0.5,
        application: str | None = None,
    ) -> dict[str, Any]:
        """
        Record a learning insight from the meta-learning system.

        Args:
            learning_type: Type ('pattern', 'insight', 'rule', 'preference')
            category: Category ('agent', 'skill', 'workflow', 'general')
            description: What was learned
            evidence: List of evidence (spec_ids, feedback_ids)
            confidence: Confidence score (0.0 - 1.0)
            application: How this should be applied

        Returns:
            Dict with learning ID
        """
        try:
            learning_id = self._next_id("spec_learning_seq")

            self.con.execute(
                """
                INSERT INTO spec_learning
                    (id, learning_type, category, description,
                     evidence, confidence, application)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    learning_id,
                    learning_type,
                    category,
                    description,
                    json.dumps(evidence) if evidence else None,
                    confidence,
                    application,
                ],
            )

            return {"learning_id": learning_id}

        except Exception as e:
            return {"error": str(e)}

    def get_top_learnings(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get top learning insights by confidence.

        Args:
            limit: Maximum number of learnings to return

        Returns:
            List of learning insights
        """
        try:
            query = """
                SELECT
                    id, learning_type, category,
                    description, confidence,
                    application,
                    created_at
                FROM spec_learning
                WHERE confidence >= 0.5
                ORDER BY confidence DESC, created_at DESC
                LIMIT ?
            """
            result = self.con.execute(query, [limit]).fetchall()

            columns = [
                "id",
                "learning_type",
                "category",
                "description",
                "confidence",
                "application",
                "created_at",
            ]
            specs = []
            for row in result:
                spec = dict(zip(columns, row))
                if spec.get("created_at"):
                    spec["created_at"] = str(spec["created_at"])
                specs.append(spec)
            return specs

        except Exception:
            return []

    # =========================================================================
    # Provenance Methods (Source Tracking)
    # =========================================================================

    def set_upstream_source(
        self,
        spec_id: int,
        source_url: str,
        upstream_version: str,
        source_ref: str | None = None,
    ) -> dict[str, Any]:
        """
        Set upstream source for a spec.

        Args:
            spec_id: Spec ID
            source_url: URL of the upstream source
            upstream_version: Version in upstream
            source_ref: Commit hash or other reference

        Returns:
            Dict with update status
        """
        try:
            self.con.execute(
                """
                UPDATE spec_objects
                SET source_type = 'upstream',
                    source_url = ?,
                    upstream_version = ?,
                    source_ref = ?,
                    sync_status = 'synced',
                    last_sync = current_timestamp,
                    updated_at = current_timestamp
                WHERE id = ?
                """,
                [source_url, upstream_version, source_ref, spec_id],
            )
            return {"updated": True, "sync_status": "synced"}

        except Exception as e:
            return {"error": str(e)}

    def get_specs_needing_sync(self) -> list[dict[str, Any]]:
        """
        Get specs that need to be synced with their upstream source.

        Returns:
            List of specs with outdated or conflicting sync status
        """
        try:
            query = """
                SELECT
                    id, kind, name, version,
                    source_type, source_url, upstream_version,
                    last_sync, sync_status,
                    summary
                FROM spec_objects
                WHERE source_type = 'upstream'
                  AND sync_status IN ('outdated', 'conflict')
                ORDER BY last_sync ASC NULLS FIRST
            """
            result = self.con.execute(query).fetchall()

            columns = [
                "id",
                "kind",
                "name",
                "version",
                "source_type",
                "source_url",
                "upstream_version",
                "last_sync",
                "sync_status",
                "summary",
            ]
            specs = []
            for row in result:
                spec = dict(zip(columns, row))
                if spec.get("last_sync"):
                    spec["last_sync"] = str(spec["last_sync"])
                specs.append(spec)
            return specs

        except Exception:
            return []

    # =========================================================================
    # Intelligence Layer Methods (RAG/Embeddings)
    # =========================================================================

    def store_embedding(
        self,
        content: str,
        embedding: list[float],
        content_type: str,
        spec_id: int | None = None,
        org_id: int | None = None,
        metadata: dict | None = None,
        embedding_model: str = "default",
    ) -> dict[str, Any]:
        """
        Store content with its embedding vector.

        Args:
            content: Text content to store
            embedding: Vector embedding as list of floats
            content_type: Type of content ('code', 'doc', 'decision', 'research', 'design', 'log')
            spec_id: Optional reference to spec_objects
            org_id: Optional reference to org spec
            metadata: Optional JSON metadata
            embedding_model: Model used for embedding

        Returns:
            Dict with embedding ID
        """
        try:
            import hashlib

            content_hash = hashlib.sha256(content.encode()).hexdigest()

            emb_id = self._next_id("spec_embeddings_seq")

            self.con.execute(
                """
                INSERT INTO spec_embeddings
                    (id, spec_id, org_id, content_type, content_hash,
                     content, embedding, embedding_model, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (content_hash, chunk_index) DO UPDATE SET
                    embedding = EXCLUDED.embedding
                """,
                [
                    emb_id,
                    spec_id,
                    org_id,
                    content_type,
                    content_hash,
                    content,
                    embedding,
                    embedding_model,
                    json.dumps(metadata) if metadata else None,
                ],
            )

            return {"embedding_id": emb_id, "content_hash": content_hash}

        except Exception as e:
            return {"error": str(e)}

    def search_similar(
        self,
        query_embedding: list[float],
        k: int = 10,
        content_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar content using vector similarity.

        Args:
            query_embedding: Query vector
            k: Number of results to return
            content_type: Optional filter by content type

        Returns:
            List of similar content with similarity scores
        """
        try:
            if content_type:
                query = """
                    SELECT
                        id, spec_id, org_id, content_type,
                        content, metadata,
                        list_cosine_similarity(embedding, ?::FLOAT[]) AS similarity
                    FROM spec_embeddings
                    WHERE content_type = ?
                      AND embedding IS NOT NULL
                    ORDER BY similarity DESC
                    LIMIT ?
                """
                result = self.con.execute(query, [query_embedding, content_type, k]).fetchall()
            else:
                query = """
                    SELECT
                        id, spec_id, org_id, content_type,
                        content, metadata,
                        list_cosine_similarity(embedding, ?::FLOAT[]) AS similarity
                    FROM spec_embeddings
                    WHERE embedding IS NOT NULL
                    ORDER BY similarity DESC
                    LIMIT ?
                """
                result = self.con.execute(query, [query_embedding, k]).fetchall()

            columns = [
                "id",
                "spec_id",
                "org_id",
                "content_type",
                "content",
                "metadata",
                "similarity",
            ]
            return [dict(zip(columns, row)) for row in result]

        except Exception:
            return []

    def hybrid_search(
        self,
        text_query: str,
        query_embedding: list[float],
        k: int = 10,
        content_type: str | None = None,
        keyword_weight: float = 0.3,
    ) -> list[dict[str, Any]]:
        """
        Hybrid search combining keyword matching with vector similarity.

        Args:
            text_query: Text query for keyword matching
            query_embedding: Query vector for semantic matching
            k: Number of results to return
            content_type: Optional filter by content type
            keyword_weight: Weight for keyword score (0-1), rest goes to vector

        Returns:
            List of results with hybrid scores
        """
        try:
            vector_weight = 1.0 - keyword_weight
            params: list[Any]
            if content_type:
                query = f"""
                    WITH keyword_matches AS (
                        SELECT id, 1.0 AS keyword_score
                        FROM spec_embeddings
                        WHERE content ILIKE '%' || ? || '%'
                          AND content_type = ?
                    ),
                    vector_matches AS (
                        SELECT
                            id,
                            list_cosine_similarity(embedding, ?::FLOAT[]) AS vector_score
                        FROM spec_embeddings
                        WHERE embedding IS NOT NULL
                          AND content_type = ?
                    )
                    SELECT
                        e.id, e.spec_id, e.org_id, e.content_type,
                        e.content, e.metadata,
                        COALESCE(k.keyword_score, 0) AS keyword_score,
                        COALESCE(v.vector_score, 0) AS vector_score,
                        (COALESCE(k.keyword_score, 0) * {keyword_weight} +
                         COALESCE(v.vector_score, 0) * {vector_weight}) AS hybrid_score
                    FROM spec_embeddings e
                    LEFT JOIN keyword_matches k ON k.id = e.id
                    LEFT JOIN vector_matches v ON v.id = e.id
                    WHERE (k.id IS NOT NULL OR v.id IS NOT NULL)
                      AND e.content_type = ?
                    ORDER BY hybrid_score DESC
                    LIMIT ?
                """
                params = [text_query, content_type, query_embedding, content_type, content_type, k]
            else:
                query = f"""
                    WITH keyword_matches AS (
                        SELECT id, 1.0 AS keyword_score
                        FROM spec_embeddings
                        WHERE content ILIKE '%' || ? || '%'
                    ),
                    vector_matches AS (
                        SELECT
                            id,
                            list_cosine_similarity(embedding, ?::FLOAT[]) AS vector_score
                        FROM spec_embeddings
                        WHERE embedding IS NOT NULL
                    )
                    SELECT
                        e.id, e.spec_id, e.org_id, e.content_type,
                        e.content, e.metadata,
                        COALESCE(k.keyword_score, 0) AS keyword_score,
                        COALESCE(v.vector_score, 0) AS vector_score,
                        (COALESCE(k.keyword_score, 0) * {keyword_weight} +
                         COALESCE(v.vector_score, 0) * {vector_weight}) AS hybrid_score
                    FROM spec_embeddings e
                    LEFT JOIN keyword_matches k ON k.id = e.id
                    LEFT JOIN vector_matches v ON v.id = e.id
                    WHERE k.id IS NOT NULL OR v.id IS NOT NULL
                    ORDER BY hybrid_score DESC
                    LIMIT ?
                """
                params = [text_query, query_embedding, k]
            result = self.con.execute(query, params).fetchall()

            columns = [
                "id",
                "spec_id",
                "org_id",
                "content_type",
                "content",
                "metadata",
                "keyword_score",
                "vector_score",
                "hybrid_score",
            ]
            return [dict(zip(columns, row)) for row in result]

        except Exception:
            return []

    def store_conversation_memory(
        self,
        session_id: str,
        role: str,
        content: str,
        embedding: list[float] | None = None,
        agent_spec_id: int | None = None,
        importance: float = 0.5,
        tool_calls: list | None = None,
    ) -> dict[str, Any]:
        """
        Store a conversation message in long-term memory.

        Args:
            session_id: Session identifier
            role: Message role ('user', 'assistant', 'system', 'tool')
            content: Message content
            embedding: Optional vector embedding
            agent_spec_id: Optional reference to agent spec
            importance: Importance score for memory prioritization (0-1)
            tool_calls: Optional list of tool calls

        Returns:
            Dict with memory ID
        """
        try:
            mem_id = self._next_id("memory_conversations_seq")

            self.con.execute(
                """
                INSERT INTO memory_conversations
                    (id, session_id, agent_spec_id, role, content,
                     embedding, importance, tool_calls)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    mem_id,
                    session_id,
                    agent_spec_id,
                    role,
                    content,
                    embedding,
                    importance,
                    json.dumps(tool_calls) if tool_calls else None,
                ],
            )

            return {"memory_id": mem_id}

        except Exception as e:
            return {"error": str(e)}

    def get_conversation_context(
        self,
        session_id: str,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get recent conversation context for a session.

        Args:
            session_id: Session identifier
            k: Number of messages to retrieve

        Returns:
            List of conversation messages
        """
        try:
            query = """
                SELECT role, content, importance, created_at
                FROM memory_conversations
                WHERE session_id = ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
            """
            result = self.con.execute(query, [session_id, k]).fetchall()

            columns = ["role", "content", "importance", "created_at"]
            messages = []
            for row in result:
                msg = dict(zip(columns, row))
                if msg.get("created_at"):
                    msg["created_at"] = str(msg["created_at"])
                messages.append(msg)
            return messages

        except Exception:
            return []

    def store_org_knowledge(
        self,
        org: str,
        content: str,
        embedding: list[float] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Store knowledge in an organization-specific knowledge base.

        Args:
            org: Organization name ('dev', 'research', 'studio', 'ops')
            content: Content to store
            embedding: Optional vector embedding
            **kwargs: Additional org-specific fields

        Returns:
            Dict with knowledge entry ID
        """
        try:
            if org == "dev":
                entry_id = self._next_id("knowledge_dev_seq")
                self.con.execute(
                    """
                    INSERT INTO knowledge_dev
                        (id, repo, file_path, language, ast_type,
                         symbol_name, content, embedding,
                         doc_string, version_ref)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        entry_id,
                        kwargs.get("repo", "unknown"),
                        kwargs.get("file_path", "unknown"),
                        kwargs.get("language"),
                        kwargs.get("ast_type"),
                        kwargs.get("symbol_name"),
                        content,
                        embedding,
                        kwargs.get("doc_string"),
                        kwargs.get("version_ref"),
                    ],
                )
            elif org == "research":
                entry_id = self._next_id("knowledge_research_seq")
                self.con.execute(
                    """
                    INSERT INTO knowledge_research
                        (id, query, source_url, source_title,
                         content, embedding, relevance_score,
                         search_engine)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        entry_id,
                        kwargs.get("query", ""),
                        kwargs.get("source_url"),
                        kwargs.get("source_title"),
                        content,
                        embedding,
                        kwargs.get("relevance_score"),
                        kwargs.get("search_engine", "searxng"),
                    ],
                )
            elif org == "studio":
                entry_id = self._next_id("knowledge_studio_seq")
                self.con.execute(
                    """
                    INSERT INTO knowledge_studio
                        (id, project, decision_type, title,
                         description, content, embedding,
                         rationale, performance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        entry_id,
                        kwargs.get("project", "default"),
                        kwargs.get("decision_type", "general"),
                        kwargs.get("title", "Untitled"),
                        kwargs.get("description"),
                        content,
                        embedding,
                        kwargs.get("rationale"),
                        kwargs.get("performance"),
                    ],
                )
            elif org == "ops":
                entry_id = self._next_id("knowledge_ops_seq")
                self.con.execute(
                    """
                    INSERT INTO knowledge_ops
                        (id, pipeline, run_id, status, log_level,
                         content, embedding, metrics, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        entry_id,
                        kwargs.get("pipeline", "unknown"),
                        kwargs.get("run_id"),
                        kwargs.get("status"),
                        kwargs.get("log_level", "info"),
                        content,
                        embedding,
                        json.dumps(kwargs.get("metrics")) if kwargs.get("metrics") else None,
                        kwargs.get("duration_ms"),
                    ],
                )
            else:
                return {"error": f"Unknown org: {org}"}

            return {"entry_id": entry_id, "org": org}

        except Exception as e:
            return {"error": str(e)}

    def get_knowledge_stats(self) -> dict[str, Any]:
        """
        Get statistics about the knowledge bases.

        Returns:
            Dict with knowledge base statistics
        """
        try:
            stats = {}

            # Embedding stats
            emb_result = self.con.execute("""
                SELECT
                    content_type,
                    COUNT(*) AS total,
                    COUNT(embedding) AS with_embeddings
                FROM spec_embeddings
                GROUP BY content_type
            """).fetchall()
            stats["embeddings"] = {
                row[0]: {"total": row[1], "with_embeddings": row[2]} for row in emb_result
            }

            # Org knowledge stats
            for org, table in [
                ("dev", "knowledge_dev"),
                ("research", "knowledge_research"),
                ("studio", "knowledge_studio"),
                ("ops", "knowledge_ops"),
            ]:
                try:
                    result = self.con.execute(f"""
                        SELECT COUNT(*), COUNT(embedding)
                        FROM {table}
                    """).fetchone()
                    stats[org] = {"total": result[0], "with_embeddings": result[1]}
                except Exception:
                    stats[org] = {"total": 0, "with_embeddings": 0}

            # Memory stats
            try:
                mem_result = self.con.execute("""
                    SELECT COUNT(*), COUNT(DISTINCT session_id)
                    FROM memory_conversations
                """).fetchone()
                stats["memory"] = {"messages": mem_result[0], "sessions": mem_result[1]}
            except Exception:
                stats["memory"] = {"messages": 0, "sessions": 0}

            return stats

        except Exception as e:
            return {"error": str(e)}


# Global spec engine instance
_spec_engine: SpecEngine | None = None
_spec_engine_lock = Lock()


def get_spec_engine(con: duckdb.DuckDBPyConnection | None = None) -> SpecEngine:
    """
    Get or create the global Spec Engine instance.

    Args:
        con: Optional DuckDB connection (only used on first call)

    Returns:
        The global SpecEngine instance
    """
    global _spec_engine
    with _spec_engine_lock:
        if _spec_engine is None:
            if con is None:
                raise ValueError("Connection required for first SpecEngine initialization")
            _spec_engine = SpecEngine(con)
            _spec_engine.initialize()
            return _spec_engine

        if con is not None and _spec_engine.con is not con:
            _spec_engine = SpecEngine(con)
            _spec_engine.initialize()

        return _spec_engine


def register_spec_engine_tools(con: duckdb.DuckDBPyConnection) -> list[str]:
    """
    Register Spec Engine tools as Python UDFs in DuckDB.

    Args:
        con: DuckDB connection

    Returns:
        List of registered tool names
    """
    engine = get_spec_engine(con)
    registered = []

    # Register spec_list as UDF
    def udf_spec_list(kind: str = None, status: str = None, limit: int = 50) -> str:
        result = engine.spec_list(kind, status, limit)
        return json.dumps(result)

    try:
        con.create_function("spec_list_udf", udf_spec_list, return_type="VARCHAR")
        registered.append("spec_list_udf")
    except Exception as e:
        print(f"Failed to register spec_list_udf: {e}", file=sys.stderr)

    # Register spec_search as UDF
    def udf_spec_search(query: str, limit: int = 20) -> str:
        result = engine.spec_search(query, limit)
        return json.dumps(result)

    try:
        con.create_function("spec_search_udf", udf_spec_search, return_type="VARCHAR")
        registered.append("spec_search_udf")
    except Exception as e:
        print(f"Failed to register spec_search_udf: {e}", file=sys.stderr)

    # Register render_from_template as UDF
    def udf_render_template(template_name: str, context_json: str) -> str:
        try:
            context = json.loads(context_json)
        except json.JSONDecodeError:
            context = {}
        result = engine.render_from_template(template_name, context)
        return json.dumps(result)

    try:
        con.create_function("render_template_udf", udf_render_template, return_type="VARCHAR")
        registered.append("render_template_udf")
    except Exception as e:
        print(f"Failed to register render_template_udf: {e}", file=sys.stderr)

    # Register validate_payload as UDF
    def udf_validate_payload(kind: str, name: str, payload_json: str) -> str:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            return json.dumps({"ok": False, "errors": ["Invalid JSON payload"]})
        result = engine.validate_payload_against_spec(kind, name, payload)
        return json.dumps(result)

    try:
        con.create_function("validate_payload_udf", udf_validate_payload, return_type="VARCHAR")
        registered.append("validate_payload_udf")
    except Exception as e:
        print(f"Failed to register validate_payload_udf: {e}", file=sys.stderr)

    return registered
