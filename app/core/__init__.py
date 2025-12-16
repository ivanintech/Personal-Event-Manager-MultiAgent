"""
Core Module - Core functionality and dependency injection.
"""

from .container import ServiceContainer, get_container, reset_container

__all__ = [
    "ServiceContainer",
    "get_container",
    "reset_container",
]






