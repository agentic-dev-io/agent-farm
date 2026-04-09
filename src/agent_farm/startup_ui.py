"""TTY-friendly bootstrap output (Rich). Disabled when stderr is not a TTY or AGENT_FARM_PLAIN_LOG is set."""

from __future__ import annotations

import os
import sys


def use_startup_ui() -> bool:
    """True when we may render progress bars / emoji on stderr (not for MCP stdio or CI)."""
    if os.environ.get("AGENT_FARM_PLAIN_LOG", "").strip():
        return False
    return sys.stderr.isatty()


def suppress_stderr_info() -> object:
    """Raise stderr StreamHandler on agent_farm to WARNING so INFO spam stays off the console (file log unchanged)."""
    import logging

    root = logging.getLogger("agent_farm")
    saved: list[tuple[logging.Handler, int]] = []
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and h.stream in (sys.stderr, sys.__stderr__):
            saved.append((h, h.level))
            h.setLevel(logging.WARNING)

    class _Restore:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: object) -> None:
            for h, lvl in saved:
                h.setLevel(lvl)

    return _Restore()
