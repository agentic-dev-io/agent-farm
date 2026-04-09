"""
Agent SDK UDFs for DuckDB.

Provides Python UDFs that can be registered in DuckDB to interact with
the Anthropic Agent SDK for complex agent operations.

Usage:
    from agent_farm.udfs import register_udfs
    register_udfs(con)  # Register UDFs in DuckDB connection
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb


def _get_anthropic_client():
    """Get Anthropic client if available."""
    try:
        import anthropic

        return anthropic.Anthropic()
    except ImportError:
        return None
    except Exception:
        return None


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prepare_messages(messages: list[dict], system_prompt: str | None = None) -> list[dict]:
    """Normalize chat messages for model backends (preserves tool_calls / tool names for Ollama)."""
    prepared: list[dict] = []
    if system_prompt:
        prepared.append({"role": "system", "content": system_prompt})

    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            continue
        if role == "assistant" and message.get("tool_calls"):
            prepared.append(
                {
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": message["tool_calls"],
                }
            )
            continue
        if role == "tool":
            entry: dict = {"role": "tool", "content": content or ""}
            if message.get("name"):
                entry["name"] = message["name"]
            prepared.append(entry)
            continue
        if content is None:
            continue
        prepared.append({"role": role, "content": content})

    return prepared


def _get_ollama_response(model: str, messages: list, tools: list | None = None) -> dict:
    """Call Ollama API directly."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{base_url}/api/chat"

    payload = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def chat_with_model(
    model: str,
    messages: list[dict],
    system_prompt: str | None = None,
    tools: list | None = None,
) -> dict:
    """Send a message history to the configured backend."""
    prepared_messages = _prepare_messages(messages, system_prompt)

    if "claude" in model.lower():
        client = _get_anthropic_client()
        if client:
            try:
                anthropic_messages = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in prepared_messages
                    if msg["role"] != "system"
                ]

                request_kwargs = {
                    "model": model,
                    "max_tokens": 4096,
                    "system": system_prompt or "",
                    "messages": anthropic_messages,
                }

                if tools:
                    anthropic_tools = []
                    for tool in tools:
                        if tool.get("type") == "function":
                            func = tool.get("function", {})
                            anthropic_tools.append(
                                {
                                    "name": func.get("name"),
                                    "description": func.get("description", ""),
                                    "input_schema": func.get("parameters", {}),
                                }
                            )
                    if anthropic_tools:
                        request_kwargs["tools"] = anthropic_tools

                response = client.messages.create(**request_kwargs)

                tool_calls = []
                text_content = ""
                for block in response.content:
                    if block.type == "tool_use":
                        tool_calls.append(
                            {
                                "id": block.id,
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input),
                                },
                            }
                        )
                    elif block.type == "text":
                        text_content += block.text

                payload = {
                    "content": text_content,
                    "model": model,
                }
                if tools:
                    payload["tool_calls"] = tool_calls if tool_calls else None
                    payload["stop_reason"] = response.stop_reason
                else:
                    payload["usage"] = {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    }
                return payload
            except Exception as e:
                return {"error": str(e)}

    response = _get_ollama_response(model, prepared_messages, tools)
    if "error" in response:
        return response

    message = response.get("message", {})
    payload = {
        "content": message.get("content", ""),
        "model": model,
        "done": response.get("done", False),
    }
    if tools:
        payload["tool_calls"] = message.get("tool_calls")
    return payload


def stream_model_response(
    model: str,
    messages: list[dict],
    system_prompt: str | None = None,
):
    """Yield response chunks for interactive clients."""
    prepared_messages = _prepare_messages(messages, system_prompt)

    if "claude" in model.lower():
        response = chat_with_model(model, messages, system_prompt=system_prompt)
        if response.get("content"):
            yield response["content"]
        return

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{base_url}/api/chat"
    payload = {"model": model, "messages": prepared_messages, "stream": True}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
    except Exception:
        response = chat_with_model(model, messages, system_prompt=system_prompt)
        if response.get("content"):
            yield response["content"]


# =============================================================================
# UDF Functions
# =============================================================================


def udf_agent_chat(model: str, prompt: str, system_prompt: str | None = None) -> str:
    """
    Simple agent chat - send a prompt, get a response.

    Args:
        model: Model name (e.g., 'llama3.2', 'claude-sonnet-4-20250514')
        prompt: User prompt
        system_prompt: Optional system prompt

    Returns:
        JSON string with response
    """
    response = chat_with_model(
        model,
        [{"role": "user", "content": prompt}],
        system_prompt=system_prompt,
    )
    return json.dumps(response)


def udf_agent_tools(
    model: str, prompt: str, tools_json: str, system_prompt: str | None = None
) -> str:
    """
    Agent chat with tools - send a prompt with tool definitions.

    Args:
        model: Model name
        prompt: User prompt
        tools_json: JSON array of tool definitions
        system_prompt: Optional system prompt

    Returns:
        JSON string with response and tool calls
    """
    try:
        tools = json.loads(tools_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid tools_json"})

    response = chat_with_model(
        model,
        [{"role": "user", "content": prompt}],
        system_prompt=system_prompt,
        tools=tools,
    )
    return json.dumps(response)


def _path_is_allowed(path: str, workspaces: list[tuple[str, str]]) -> bool:
    """Return True when a path is inside one of the allowed workspaces."""
    try:
        candidate = Path(path).resolve()
    except Exception:
        return False

    for workspace_path, _mode in workspaces:
        try:
            root = Path(workspace_path).resolve()
        except Exception:
            continue
        if candidate == root or root in candidate.parents:
            return True
    return False


def _execute_agent_tool(
    tool_name: str,
    tool_args: dict,
    workspaces: list[tuple[str, str]],
) -> dict:
    """Execute a minimal local tool set for udf_agent_run."""
    if tool_name == "fs_read":
        path = tool_args.get("path", "")
        if not path:
            return {"error": "path required"}
        if not _path_is_allowed(path, workspaces):
            return {"error": "Path not in allowed workspace", "path": path}
        return {"path": path, "content": Path(path).read_text(encoding="utf-8")}

    if tool_name == "fs_list":
        path = tool_args.get("path", "")
        if not path:
            return {"error": "path required"}
        if not _path_is_allowed(path, workspaces):
            return {"error": "Path not in allowed workspace", "path": path}
        entries = sorted(p.name for p in Path(path).iterdir())
        return {"path": path, "entries": entries}

    if tool_name == "task_complete":
        return {"result": tool_args.get("result", "Task complete")}

    return {"error": f"Unknown tool: {tool_name}"}


def udf_agent_run(
    agent_id: str,
    prompt: str,
    max_turns: int = 10,
    con: duckdb.DuckDBPyConnection | None = None,
) -> str:
    """
    Run a full agent loop with tool execution.

    Args:
        agent_id: Agent ID from agent_config table
        prompt: User prompt
        max_turns: Maximum number of tool-use turns
        con: DuckDB connection (for accessing config)

    Returns:
        JSON string with final result and execution trace
    """
    if con is None:
        return json.dumps({"error": "No database connection"})

    # Get agent config
    try:
        config = con.execute("SELECT * FROM agent_config WHERE id = ?", [agent_id]).fetchone()
        if not config:
            return json.dumps({"error": f"Agent {agent_id} not found"})

        # Extract config fields
        model_name = config[5]  # model_name column

        # Get workspaces
        workspaces = con.execute(
            "SELECT path, mode FROM workspaces WHERE agent_id = ?", [agent_id]
        ).fetchall()

        # Build system prompt
        workspace_paths = ", ".join(w[0] for w in workspaces)
        system_prompt = f"""You are a secure agent assistant.
Allowed workspaces: {workspace_paths}
Only access files within these paths. Use task_complete when done."""

    except Exception as e:
        return json.dumps({"error": f"Config error: {e}"})

    # Get tools schema
    tools = [
        {
            "type": "function",
            "function": {
                "name": "fs_read",
                "description": "Read file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fs_list",
                "description": "List directory",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "task_complete",
                "description": "Mark task complete",
                "parameters": {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                },
            },
        },
    ]
    trace = []
    final_result = None
    messages = [{"role": "user", "content": prompt}]

    for turn in range(max_turns):
        response = chat_with_model(
            model_name,
            messages,
            system_prompt=system_prompt,
            tools=tools,
        )

        if "error" in response:
            return json.dumps({"error": response["error"], "trace": trace})

        trace.append({"turn": turn, "response": response})
        if response.get("content"):
            messages.append({"role": "assistant", "content": response["content"]})

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            final_result = response.get("content", "")
            break

        tool_results = []
        for tc in tool_calls:
            func_name = tc.get("function", {}).get("name")
            func_args = tc.get("function", {}).get("arguments", "{}")
            args = json.loads(func_args) if isinstance(func_args, str) else func_args

            if func_name == "task_complete":
                final_result = args.get("result", "Task complete")
                result = {
                    "status": "complete",
                    "result": final_result,
                    "turns": turn + 1,
                    "trace": trace,
                }
                return json.dumps(result)

            tool_result = _execute_agent_tool(func_name, args, workspaces)
            tool_results.append(
                {
                    "tool": func_name,
                    "args": args,
                    "result": tool_result,
                }
            )
            trace.append(tool_results[-1])

        messages.append(
            {
                "role": "user",
                "content": "Tool results:\n" + json.dumps(tool_results, ensure_ascii=True),
            }
        )

    return json.dumps(
        {
            "status": "max_turns_reached",
            "result": final_result,
            "turns": max_turns,
            "trace": trace,
        }
    )


def udf_detect_injection(content: str) -> str | None:
    """
    Detect potential prompt injection in content.

    Args:
        content: Text content to scan

    Returns:
        Injection type if detected, None otherwise
    """
    if not content:
        return None

    content_lower = content.lower()

    patterns = [
        ("ignore" in content_lower and "instruction" in content_lower, "instruction_override"),
        ("disregard" in content_lower and "above" in content_lower, "instruction_override"),
        ("forget" in content_lower and "everything" in content_lower, "instruction_override"),
        ("you are now" in content_lower, "role_hijack"),
        ("new instructions:" in content_lower, "instruction_injection"),
        ("[system]" in content_lower, "system_injection"),
        ("</system>" in content_lower, "xml_injection"),
        ("<instruction>" in content_lower, "xml_injection"),
        ("admin mode" in content_lower, "privilege_escalation"),
        ("developer mode" in content_lower, "privilege_escalation"),
        ("jailbreak" in content_lower, "jailbreak"),
    ]

    for condition, injection_type in patterns:
        if condition:
            return injection_type

    return None


# ============================================================================
# Approval workflow helpers
# ============================================================================


def udf_create_approval_request(
    session_id: str,
    tool_name: str,
    tool_params: str | None,
    reason: str | None,
    con: duckdb.DuckDBPyConnection | None = None,
) -> str:
    """Create a persistent approval request."""
    if con is None:
        return json.dumps({"error": "No database connection"})
    if not session_id or not tool_name:
        return json.dumps({"error": "session_id and tool_name required"})

    try:
        approval_id = con.execute("SELECT nextval('approval_seq')").fetchone()[0]
        params_json = tool_params or "{}"
        con.execute(
            """
            INSERT INTO pending_approvals (
                id, session_id, tool_name, tool_params, reason, status
            ) VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            [approval_id, session_id, tool_name, params_json, reason],
        )
        return json.dumps(
            {
                "approval_id": approval_id,
                "session_id": session_id,
                "tool_name": tool_name,
                "status": "pending",
                "reason": reason,
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def udf_resolve_approval_request(
    approval_id: int,
    decision: str,
    resolved_by: str,
    con: duckdb.DuckDBPyConnection | None = None,
) -> str:
    """Resolve an approval request."""
    if con is None:
        return json.dumps({"error": "No database connection"})

    normalized_decision = (decision or "").strip().lower()
    if normalized_decision not in {"approved", "denied"}:
        return json.dumps({"error": "decision must be approved or denied"})

    try:
        row = con.execute(
            "SELECT status FROM pending_approvals WHERE id = ?",
            [approval_id],
        ).fetchone()
        if not row:
            return json.dumps({"error": f"Approval {approval_id} not found"})
        if row[0] != "pending":
            return json.dumps({"error": f"Approval {approval_id} already resolved"})

        con.execute(
            """
            UPDATE pending_approvals
            SET status = ?, decision = ?, resolved_at = current_timestamp, resolved_by = ?
            WHERE id = ?
            """,
            [normalized_decision, normalized_decision, resolved_by or "system", approval_id],
        )
        return json.dumps(
            {
                "approval_id": approval_id,
                "status": normalized_decision,
                "decision": normalized_decision,
                "resolved_by": resolved_by or "system",
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Radio Pub/Sub System (persistent DuckDB-backed implementation)
# ============================================================================


def udf_radio_subscribe(
    channel_name: str,
    con: duckdb.DuckDBPyConnection | None = None,
) -> str:
    """
    Subscribe to a radio channel.

    Returns JSON: {"channel": name, "subscribed": true, "timestamp": ISO8601}
    """
    if not channel_name:
        return json.dumps({"error": "channel_name required"})
    if con is None:
        return json.dumps({"error": "No database connection"})

    try:
        sub_id = f"sub-{uuid4()}"
        con.execute(
            """
            INSERT INTO radio_subscriptions (sub_id, org_id, channel_name, active)
            VALUES (?, NULL, ?, TRUE)
            """,
            [sub_id, channel_name],
        )
        return json.dumps(
            {
                "channel": channel_name,
                "subscribed": True,
                "subscription_id": sub_id,
                "timestamp": _utc_now_iso(),
                "mode": "duckdb_persistent",
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def udf_radio_transmit_message(
    channel_name: str,
    message_json: str,
    con: duckdb.DuckDBPyConnection | None = None,
) -> str:
    """
    Publish a message to a radio channel.

    Args:
        channel_name: Channel to publish to
        message_json: JSON string of message

    Returns JSON: {"channel": name, "published": true, "timestamp": ISO8601}
    """
    if not channel_name or not message_json:
        return json.dumps({"error": "channel_name and message_json required"})
    if con is None:
        return json.dumps({"error": "No database connection"})

    try:

        # Wrap message with metadata
        envelope = {
            "channel": channel_name,
            "timestamp": _utc_now_iso(),
            "payload": json.loads(message_json) if isinstance(message_json, str) else message_json,
        }

        message_id = con.execute("SELECT nextval('radio_message_seq')").fetchone()[0]
        con.execute(
            """
            INSERT INTO radio_messages (id, channel_name, payload)
            VALUES (?, ?, ?)
            """,
            [message_id, channel_name, json.dumps(envelope)],
        )

        return json.dumps(
            {
                "channel": channel_name,
                "published": True,
                "message_id": message_id,
                "timestamp": envelope["timestamp"],
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def udf_radio_listen(
    channel_name: str,
    timeout_ms: int = 1000,
    con: duckdb.DuckDBPyConnection | None = None,
) -> str:
    """
    Listen for messages on a radio channel (non-blocking with timeout).

    Args:
        channel_name: Channel to listen on
        timeout_ms: Timeout in milliseconds

    Returns JSON message or {"no_message": true}
    """
    if not channel_name:
        return json.dumps({"error": "channel_name required"})
    if con is None:
        return json.dumps({"error": "No database connection"})

    try:
        timeout_sec = (timeout_ms or 1000) / 1000.0
        deadline = time.monotonic() + timeout_sec

        while time.monotonic() <= deadline:
            row = con.execute(
                """
                SELECT id, payload
                FROM radio_messages
                WHERE channel_name = ?
                ORDER BY id
                LIMIT 1
                """,
                [channel_name],
            ).fetchone()
            if row:
                con.execute("DELETE FROM radio_messages WHERE id = ?", [row[0]])
                return row[1]
            time.sleep(0.05)

        return json.dumps({"no_message": True, "channel": channel_name})
    except Exception as e:
        return json.dumps({"error": str(e)})


def udf_radio_channel_list(con: duckdb.DuckDBPyConnection | None = None) -> str:
    """
    List all active radio channels and their queue sizes.

    Returns JSON: {"channels": [{name, queue_size}, ...]}
    """
    if con is None:
        return json.dumps({"error": "No database connection"})

    try:
        rows = con.execute(
            """
            SELECT
                channel_name,
                COUNT(*) AS message_count
            FROM radio_messages
            GROUP BY channel_name
            ORDER BY channel_name
            """
        ).fetchall()
        channels = [{"name": row[0], "queue_size": row[1]} for row in rows]
        return json.dumps({"channels": channels, "total": len(channels)})
    except Exception as e:
        return json.dumps({"error": str(e)})


def udf_getenv(name: str) -> str | None:
    """
    Get environment variable value.

    Replacement for DuckDB's getenv() which is not available in embedded/Python mode.
    """
    if not name:
        return None
    return os.getenv(name)


def udf_safe_json_extract(json_str: str, path: str) -> str | None:
    """
    Safely extract value from JSON string.

    Args:
        json_str: JSON string
        path: JSON path (e.g., '$.key' or 'key')

    Returns:
        Extracted value as string, or None
    """
    try:
        data = json.loads(json_str)
        # Simple path handling
        path = path.lstrip("$.")
        keys = path.split(".")
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            elif isinstance(data, list) and key.isdigit():
                data = data[int(key)]
            else:
                return None
        return json.dumps(data) if isinstance(data, (dict, list)) else str(data)
    except Exception:
        return None


# =============================================================================
# Registration
# =============================================================================


def register_udfs(con: duckdb.DuckDBPyConnection) -> list[str]:
    """
    Register all agent UDFs in the DuckDB connection.

    Args:
        con: DuckDB connection

    Returns:
        List of registered UDF names
    """
    registered = []

    # agent_chat(model, prompt, system_prompt?) -> JSON
    con.create_function(
        "agent_chat",
        udf_agent_chat,
        [str, str, str],
        str,
        null_handling="default",
    )
    registered.append("agent_chat")

    # agent_tools(model, prompt, tools_json, system_prompt?) -> JSON
    con.create_function(
        "agent_tools",
        udf_agent_tools,
        [str, str, str, str],
        str,
        null_handling="default",
    )
    registered.append("agent_tools")

    con.create_function(
        "agent_run",
        lambda agent_id, prompt, max_turns: udf_agent_run(
            agent_id,
            prompt,
            max_turns,
            con.cursor(),
        ),
        [str, str, int],
        str,
        null_handling="default",
    )
    registered.append("agent_run")

    # detect_injection(content) -> VARCHAR or NULL
    con.create_function(
        "detect_injection_udf",
        udf_detect_injection,
        [str],
        str,
        null_handling="default",
    )
    registered.append("detect_injection_udf")

    # getenv(name) -> VARCHAR or NULL (replaces CLI-only getenv)
    con.create_function(
        "getenv",
        udf_getenv,
        [str],
        str,
        null_handling="default",
    )
    registered.append("getenv")

    con.create_function(
        "approval_request_create",
        lambda session_id, tool_name, tool_params, reason: udf_create_approval_request(
            session_id,
            tool_name,
            tool_params,
            reason,
            con.cursor(),
        ),
        [str, str, str, str],
        str,
        null_handling="default",
    )
    registered.append("approval_request_create")

    con.create_function(
        "approval_request_resolve",
        lambda approval_id, decision, resolved_by: udf_resolve_approval_request(
            approval_id,
            decision,
            resolved_by,
            con.cursor(),
        ),
        [int, str, str],
        str,
        null_handling="default",
    )
    registered.append("approval_request_resolve")

    # Radio Pub/Sub UDFs (DuckDB-backed persistent channels)
    con.create_function(
        "radio_subscribe",
        lambda channel_name: udf_radio_subscribe(channel_name, con.cursor()),
        [str],
        str,
    )
    registered.append("radio_subscribe")

    con.create_function(
        "radio_transmit_message",
        lambda channel_name, message_json: udf_radio_transmit_message(
            channel_name,
            message_json,
            con.cursor(),
        ),
        [str, str],
        str,
    )
    registered.append("radio_transmit_message")

    con.create_function(
        "radio_listen",
        lambda channel_name, timeout_ms: udf_radio_listen(channel_name, timeout_ms, con.cursor()),
        [str, int],
        str,
        null_handling="default",
    )
    registered.append("radio_listen")

    con.create_function(
        "radio_channel_list",
        lambda: udf_radio_channel_list(con.cursor()),
        [],
        str,
    )
    registered.append("radio_channel_list")

    # safe_json_extract(json_str, path) -> VARCHAR or NULL
    con.create_function(
        "safe_json_extract",
        udf_safe_json_extract,
        [str, str],
        str,
        null_handling="default",
    )
    registered.append("safe_json_extract")

    return registered
