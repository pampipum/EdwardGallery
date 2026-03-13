"""
Execution Layer - Strategy Pattern for Trade Execution

Exports:
- ExecutorFactory: Returns the appropriate executor based on config
- BaseExecutor: Abstract interface for executors
- PaperExecutor: Simulated paper trading
- JupiterExecutor: Live trading via Jupiter API (when implemented)
"""

from .factory import ExecutorFactory
from .base import BaseExecutor, ExecutionResult
from .paper_executor import PaperExecutor

__all__ = ['ExecutorFactory', 'BaseExecutor', 'ExecutionResult', 'PaperExecutor']
