"""Strategy module for fasthooks.

Strategies are reusable, composable hook patterns with built-in observability.
"""

from .base import Strategy, StrategyMeta
from .long_running import LongRunningStrategy

__all__ = [
    "Strategy",
    "StrategyMeta",
    "LongRunningStrategy",
]
