"""XStem stemming module implementation."""
from .module import StemmingModule

# Auto-register module
from modules.registry import register_module
register_module(StemmingModule)

__all__ = ["StemmingModule"]
