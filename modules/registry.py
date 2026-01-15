"""Module registry for discovering and loading modules."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Type

from .base_module import BaseModule, NullModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Registry for discovering and loading modules.

    The registry maintains a mapping of module names to module classes.
    Modules can be registered manually or discovered automatically.

    Example Usage:
        ```python
        registry = ModuleRegistry()

        # Manual registration
        registry.register(MyModule)

        # Get module class and instantiate
        ModuleClass = registry.get("my_module")
        module = ModuleClass()
        ```
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._modules: Dict[str, Type[BaseModule]] = {}

        # Register built-in null module
        self.register(NullModule)

        logger.info("Module registry initialized")

    def register(self, module_class: Type[BaseModule]) -> None:
        """Register a module class.

        Args:
            module_class: Module class that implements BaseModule

        Raises:
            ValueError: If module_name is already registered
            TypeError: If module_class doesn't implement BaseModule
        """
        if not issubclass(module_class, BaseModule):
            raise TypeError(
                f"{module_class.__name__} must inherit from BaseModule"
            )

        # Get module name from class property
        # We need to instantiate briefly to get the name
        # (property can't be accessed on class)
        try:
            temp_instance = module_class.__new__(module_class)
            module_name = temp_instance.module_name
        except Exception as e:
            raise ValueError(
                f"Could not get module_name from {module_class.__name__}: {e}"
            )

        if module_name in self._modules:
            logger.warning(
                f"Module '{module_name}' already registered, overwriting"
            )

        self._modules[module_name] = module_class
        logger.info(f"Registered module: {module_name} ({module_class.__name__})")

    def get(self, module_name: str) -> Type[BaseModule]:
        """Get module class by name.

        Args:
            module_name: Name of module to retrieve

        Returns:
            Module class

        Raises:
            KeyError: If module_name not found in registry
        """
        if module_name not in self._modules:
            available = ", ".join(self._modules.keys())
            raise KeyError(
                f"Module '{module_name}' not found in registry. "
                f"Available modules: {available}"
            )

        return self._modules[module_name]

    def list_modules(self) -> list[str]:
        """Get list of registered module names.

        Returns:
            List of module names
        """
        return list(self._modules.keys())

    def discover_modules(self, modules_dir: Path) -> None:
        """Auto-discover modules in directory.

        Looks for module.py files in subdirectories of modules_dir
        and attempts to import and register them.

        Directory structure expected:
            modules_dir/
                module1/
                    module.py  (contains Module class)
                module2/
                    module.py  (contains Module class)

        Args:
            modules_dir: Directory to search for modules

        Note:
            This is a simple discovery mechanism. Modules must:
            1. Have a module.py file
            2. Define a class that inherits from BaseModule
            3. The class name should end with "Module" (convention)
        """
        if not modules_dir.exists():
            logger.warning(f"Modules directory does not exist: {modules_dir}")
            return

        discovered_count = 0

        for module_path in modules_dir.iterdir():
            if not module_path.is_dir():
                continue

            if module_path.name.startswith("_"):
                continue  # Skip private directories

            module_file = module_path / "module.py"
            if not module_file.exists():
                continue

            # Try to import the module
            module_name = module_path.name
            try:
                # Dynamic import
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"modules.{module_name}.module",
                    module_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find BaseModule subclass in module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseModule)
                            and attr is not BaseModule
                        ):
                            self.register(attr)
                            discovered_count += 1
                            break

            except Exception as e:
                logger.error(
                    f"Failed to discover module in {module_path}: {e}",
                    exc_info=True
                )

        logger.info(f"Discovered {discovered_count} module(s)")


# Global registry instance
_global_registry = ModuleRegistry()


def get_global_registry() -> ModuleRegistry:
    """Get the global module registry instance.

    Returns:
        Global ModuleRegistry instance
    """
    return _global_registry


def register_module(module_class: Type[BaseModule]) -> None:
    """Register a module in the global registry.

    Convenience function for registering modules.

    Args:
        module_class: Module class to register
    """
    _global_registry.register(module_class)


def get_module(module_name: str) -> Type[BaseModule]:
    """Get module class from global registry.

    Convenience function for getting modules.

    Args:
        module_name: Name of module to get

    Returns:
        Module class
    """
    return _global_registry.get(module_name)
