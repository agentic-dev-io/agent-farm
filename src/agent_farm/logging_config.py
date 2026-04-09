"""Centralized logging setup for Agent Farm."""

import logging
import os
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_file: str | None = None,
    level: int = logging.INFO,
    stdio_safe: bool = False,
) -> None:
    """Configure agent_farm logging. Use stdio_safe=True when stdout/stderr are used for protocol (e.g. MCP stdio)."""
    root = logging.getLogger("agent_farm")
    if root.handlers:
        return
    root.setLevel(level)
    if not stdio_safe:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATEFMT))
        root.addHandler(stderr_handler)
    path = log_file or os.environ.get("AGENT_FARM_LOG")
    if stdio_safe and not path:
        path = str(Path.home() / ".agent_farm" / "agent_farm.log")
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATEFMT))
        root.addHandler(file_handler)
