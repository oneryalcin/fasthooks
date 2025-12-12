"""Main HookApp class."""
from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Callable
from typing import IO, Any

from cchooks._internal.io import read_stdin, write_stdout
from cchooks.events.base import BaseEvent
from cchooks.responses import HookResponse


class HookApp:
    """Main application for registering and running hook handlers."""

    def __init__(self, state_dir: str | None = None, log_level: str = "INFO"):
        """Initialize HookApp.

        Args:
            state_dir: Directory for persistent state files
            log_level: Logging verbosity
        """
        self.state_dir = state_dir
        self.log_level = log_level
        self._pre_tool_handlers: dict[str, list[Callable]] = defaultdict(list)
        self._post_tool_handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lifecycle_handlers: dict[str, list[Callable]] = defaultdict(list)

    def pre_tool(self, *tools: str) -> Callable:
        """Decorator to register a PreToolUse handler.

        Args:
            *tools: Tool names to match (e.g., "Bash", "Write")

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            for tool in tools:
                self._pre_tool_handlers[tool].append(func)
            return func
        return decorator

    def post_tool(self, *tools: str) -> Callable:
        """Decorator to register a PostToolUse handler.

        Args:
            *tools: Tool names to match

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            for tool in tools:
                self._post_tool_handlers[tool].append(func)
            return func
        return decorator

    def run(
        self,
        stdin: IO[str] | None = None,
        stdout: IO[str] | None = None,
    ) -> None:
        """Run the hook app, processing stdin and writing to stdout.

        Args:
            stdin: Input stream (default: sys.stdin)
            stdout: Output stream (default: sys.stdout)
        """
        if stdin is None:
            stdin = sys.stdin
        if stdout is None:
            stdout = sys.stdout

        # Read input
        data = read_stdin(stdin)
        if not data:
            return

        # Parse event
        event = BaseEvent.model_validate(data)
        # Store raw data for tool_input access
        event._raw_data = data  # type: ignore

        # Route to handlers
        response = self._dispatch(event, data)

        # Write output
        if response:
            write_stdout(response, stdout)

    def _dispatch(self, event: BaseEvent, data: dict[str, Any]) -> HookResponse | None:
        """Dispatch event to appropriate handlers.

        Args:
            event: Parsed event
            data: Raw input data

        Returns:
            Response from first blocking handler, or None
        """
        hook_type = event.hook_event_name

        if hook_type == "PreToolUse":
            tool_name = data.get("tool_name", "")
            handlers = self._pre_tool_handlers.get(tool_name, [])
            return self._run_handlers(handlers, event, data)

        elif hook_type == "PostToolUse":
            tool_name = data.get("tool_name", "")
            handlers = self._post_tool_handlers.get(tool_name, [])
            return self._run_handlers(handlers, event, data)

        # No matching handlers
        return None

    def _run_handlers(
        self,
        handlers: list[Callable],
        event: BaseEvent,
        data: dict[str, Any],
    ) -> HookResponse | None:
        """Run handlers in order, stopping on deny/block.

        Args:
            handlers: List of handler functions
            event: Parsed event
            data: Raw input data

        Returns:
            First deny/block response, or None
        """
        # Create a simple event wrapper with tool_input access
        class EventWrapper:
            def __init__(self, base: BaseEvent, raw: dict):
                self._base = base
                self._raw = raw

            @property
            def session_id(self) -> str:
                return self._base.session_id

            @property
            def cwd(self) -> str:
                return self._base.cwd

            @property
            def permission_mode(self) -> str:
                return self._base.permission_mode

            @property
            def hook_event_name(self) -> str:
                return self._base.hook_event_name

            @property
            def tool_name(self) -> str:
                return self._raw.get("tool_name", "")

            @property
            def tool_input(self) -> dict:
                return self._raw.get("tool_input", {})

        wrapper = EventWrapper(event, data)

        for handler in handlers:
            try:
                response = handler(wrapper)
                if response and response.decision in ("deny", "block"):
                    return response
            except Exception as e:
                # Log and continue (fail open)
                print(f"[cchooks] Handler {handler.__name__} failed: {e}", file=sys.stderr)
                continue

        return None
