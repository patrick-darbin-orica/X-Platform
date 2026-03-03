"""XPrime priming module implementation."""
from .module import PrimingModule

# Auto-register module
from modules.registry import register_module
register_module(PrimingModule)

__all__ = ["PrimingModule"]
