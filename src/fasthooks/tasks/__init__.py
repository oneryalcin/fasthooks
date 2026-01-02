"""
Background tasks for fasthooks.

Enables hooks to spawn async work that feeds back results in subsequent hook calls.

Usage:
    from fasthooks.tasks import task, Tasks

    @task
    def memory_lookup(query: str) -> str:
        return search_db(query)

    @app.on_prompt()  # Recommended unified dependency
    def check_memory(event, tasks: Tasks):
        if result := tasks.pop(memory_lookup):
            return allow(message=f"Found: {result}")

        # Default key is function name; use explicit key for concurrent calls
        tasks.add(memory_lookup, event.prompt)
        return allow()
"""

from .backend import BaseBackend, InMemoryBackend
from .base import Task, TaskResult, TaskStatus, task
from .depends import BackgroundTasks, PendingResults, Tasks
from .testing import ImmediateBackend, MockBackend

__all__ = [
    # Core
    "task",
    "Task",
    "TaskResult",
    "TaskStatus",
    # Backends
    "BaseBackend",
    "InMemoryBackend",
    # DI Dependencies
    "Tasks",
    "BackgroundTasks",
    "PendingResults",
    # Testing
    "ImmediateBackend",
    "MockBackend",
]
