"""Provider registry package.

Importing this package registers all built-in providers so they are discoverable
via the registry.
"""

from vgeval.providers import mock  # noqa: F401  (import for registration side effect)
from vgeval.providers.local import discover_models, register_local_providers
from vgeval.providers.registry import available, get_provider, register

__all__ = [
    "available",
    "get_provider",
    "register",
    "register_local_providers",
    "discover_models",
]
