"""UI orchestration shared by the collector, the flow engine and the demo scripts.

The public surface is re-exported here so callers write `uiauto.launch(...)`.
"""
from .uiauto import (  # noqa: F401
    DEFAULT_POLL_MS,
    LAUNCHER_HINT,
    ensure_foreground,
    launch,
    launch_action,
    launch_component,
    start_command,
    wait_foreground,
    wait_left_launcher,
)

__all__ = [
    "DEFAULT_POLL_MS",
    "LAUNCHER_HINT",
    "ensure_foreground",
    "launch",
    "launch_action",
    "launch_component",
    "start_command",
    "wait_foreground",
    "wait_left_launcher",
]