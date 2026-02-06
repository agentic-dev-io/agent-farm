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
from queue import Queue
from threading import Lock
from datetime import datetime

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


def _get_ollama_response(model: str, messages: list, tools: list | None = None) -> dict:
    """Call Ollama API directly."""
    import urllib.request

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
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Check if using Anthropic
    if "claude" in model.lower():
        client = _get_anthropic_client()
        if client:
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt or "",
                    messages=[{"role": "user", "content": prompt}],
                )
                return json.dumps(
                    {
                        "content": response.content[0].text,
                        "model": model,
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                        },
                    }
                )
            except Exception as e:
                return json.dumps({"error": str(e)})

    # Use Ollama
    response = _get_ollama_response(model, messages)
    if "error" in response:
        return json.dumps(response)

    return json.dumps(
        {
            "content": response.get("message", {}).get("content", ""),
            "model": model,
            "done": response.get("done", False),
        }
    )


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

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Check if using Anthropic
    if "claude" in model.lower():
        client = _get_anthropic_client()
        if client:
            try:
                # Convert tools to Anthropic format
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

                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt or "",
                    messages=[{"role": "user", "content": prompt}],
                    tools=anthropic_tools if anthropic_tools else None,
                )

                # Extract tool use blocks
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
                        text_content = block.text

                return json.dumps(
                    {
                        "content": text_content,
                        "tool_calls": tool_calls if tool_calls else None,
                        "model": model,
                        "stop_reason": response.stop_reason,
                    }
                )
            except Exception as e:
                return json.dumps({"error": str(e)})

    # Use Ollama
    response = _get_ollama_response(model, messages, tools)
    if "error" in response:
        return json.dumps(response)

    message = response.get("message", {})
    return json.dumps(
        {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls"),
            "model": model,
            "done": response.get("done", False),
        }
    )


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
    tools_json = json.dumps(tools)

    trace = []
    final_result = None

    for turn in range(max_turns):
        # Call model
        response_json = udf_agent_tools(
            model_name, prompt if turn == 0 else "", tools_json, system_prompt
        )
        response = json.loads(response_json)

        if "error" in response:
            return json.dumps({"error": response["error"], "trace": trace})

        trace.append({"turn": turn, "response": response})

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            final_result = response.get("content", "")
            break

        # Process tool calls
        for tc in tool_calls:
            func_name = tc.get("function", {}).get("name")
            func_args = tc.get("function", {}).get("arguments", "{}")

            if func_name == "task_complete":
                if isinstance(func_args, str):
                    args = json.loads(func_args)
                else:
                    args = func_args
                final_result = args.get("result", "Task complete")
                result = {
                    "status": "complete",
                    "result": final_result,
                    "turns": turn + 1,
                    "trace": trace,
                }
                return json.dumps(result)

            trace.append({"tool": func_name, "args": func_args})

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
# Radio Pub/Sub System (Windows-compatible replacement for radio extension)
# ============================================================================

# Global in-memory channels (one Queue per channel name)
_radio_channels: dict[str, Queue] = {}
_radio_lock = Lock()


def _get_or_create_channel(channel_name: str) -> Queue:
    """Get or create a queue for the given channel."""
    with _radio_lock:
        if channel_name not in _radio_channels:
            _radio_channels[channel_name] = Queue(maxsize=1000)
        return _radio_channels[channel_name]


def udf_radio_subscribe(channel_name: str) -> str:
    """
    Subscribe to a radio channel.

    Returns JSON: {"channel": name, "subscribed": true, "timestamp": ISO8601}
    """
    if not channel_name:
        return json.dumps({"error": "channel_name required"})

    channel = _get_or_create_channel(channel_name)
    return json.dumps({
        "channel": channel_name,
        "subscribed": True,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "mode": "udf_radio"
    })


def udf_radio_transmit_message(channel_name: str, message_json: str) -> str:
    """
    Publish a message to a radio channel.

    Args:
        channel_name: Channel to publish to
        message_json: JSON string of message

    Returns JSON: {"channel": name, "published": true, "timestamp": ISO8601}
    """
    if not channel_name or not message_json:
        return json.dumps({"error": "channel_name and message_json required"})

    try:
        channel = _get_or_create_channel(channel_name)

        # Wrap message with metadata
        envelope = {
            "channel": channel_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": json.loads(message_json) if isinstance(message_json, str) else message_json
        }

        channel.put_nowait(json.dumps(envelope))

        return json.dumps({
            "channel": channel_name,
            "published": True,
            "timestamp": envelope["timestamp"]
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def udf_radio_listen(channel_name: str, timeout_ms: int = 1000) -> str:
    """
    Listen for messages on a radio channel (non-blocking with timeout).

    Args:
        channel_name: Channel to listen on
        timeout_ms: Timeout in milliseconds

    Returns JSON message or {"no_message": true}
    """
    if not channel_name:
        return json.dumps({"error": "channel_name required"})

    try:
        channel = _get_or_create_channel(channel_name)
        timeout_sec = (timeout_ms or 1000) / 1000.0

        message_json = channel.get(timeout=timeout_sec)
        return message_json
    except:
        # Timeout or empty queue
        return json.dumps({"no_message": True, "channel": channel_name})


def udf_radio_channel_list() -> str:
    """
    List all active radio channels and their queue sizes.

    Returns JSON: {"channels": [{name, queue_size}, ...]}
    """
    with _radio_lock:
        channels = [
            {"name": name, "queue_size": queue.qsize()}
            for name, queue in _radio_channels.items()
        ]

    return json.dumps({
        "channels": channels,
        "total": len(channels)
    })


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
        null_handling="special",
    )
    registered.append("agent_chat")

    # agent_tools(model, prompt, tools_json, system_prompt?) -> JSON
    con.create_function(
        "agent_tools",
        udf_agent_tools,
        [str, str, str, str],
        str,
        null_handling="special",
    )
    registered.append("agent_tools")

    # detect_injection(content) -> VARCHAR or NULL
    con.create_function(
        "detect_injection_udf",
        udf_detect_injection,
        [str],
        str,
        null_handling="special",
    )
    registered.append("detect_injection_udf")

    # getenv(name) -> VARCHAR or NULL (replaces CLI-only getenv)
    con.create_function(
        "getenv",
        udf_getenv,
        [str],
        str,
        null_handling="special",
    )
    registered.append("getenv")

    # Radio Pub/Sub UDFs (Windows-compatible, in-memory channels)
    con.create_function(
        "radio_subscribe",
        udf_radio_subscribe,
        [str],
        str,
    )
    registered.append("radio_subscribe")

    con.create_function(
        "radio_transmit_message",
        udf_radio_transmit_message,
        [str, str],
        str,
    )
    registered.append("radio_transmit_message")

    con.create_function(
        "radio_listen",
        udf_radio_listen,
        [str, int],
        str,
        default_null_handling=True,
    )
    registered.append("radio_listen")

    con.create_function(
        "radio_channel_list",
        udf_radio_channel_list,
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
        null_handling="special",
    )
    registered.append("safe_json_extract")

    return registered
