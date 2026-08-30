"""Provider registry: name -> factory.

Providers register themselves with the `@register("name")` decorator. Callers
resolve them by name via `get_provider`, and `available()` lists everything
registered (used by the CLI to build `--provider` choices).
"""

from __future__ import annotations

from collections.abc import Callable

from vgeval.providers.base import ImageToVideoProvider

_REGISTRY: dict[str, type[ImageToVideoProvider]] = {}


def register(name: str) -> Callable[[type[ImageToVideoProvider]], type[ImageToVideoProvider]]:
    """Class decorator that registers a provider under `name`."""

    def _wrap(cls: type[ImageToVideoProvider]) -> type[ImageToVideoProvider]:
        if name in _REGISTRY:
            raise ValueError(f"Provider {name!r} is already registered")
        cls.name = name
        _REGISTRY[name] = cls
        return cls

    return _wrap


def get_provider(name: str, **config: object) -> ImageToVideoProvider:
    """Instantiate the provider registered under `name`."""
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown provider {name!r}. Available: {', '.join(available()) or '(none)'}"
        ) from None
    return cls(**config)


def available() -> list[str]:
    """Sorted list of registered provider names."""
    return sorted(_REGISTRY)
