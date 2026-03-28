from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any, Callable

import typer

from gulp_cli.client import get_client
from gulp_cli.config import CONFIG_DIR
from gulp_cli.output import print_warning

INTERNAL_EXTENSIONS_DIR = Path(__file__).resolve().parent / "extension"
EXTERNAL_EXTENSIONS_DIR = CONFIG_DIR / "extension"


def _is_valid_extension_file(path: Path) -> bool:
    return path.is_file() and path.suffix == ".py" and not path.name.startswith("_")


def discover_extensions() -> dict[str, Path]:
    """
    Discover extension modules from internal and external extension folders.

    External modules have priority when a filename exists in both folders.
    """
    discovered: dict[str, Path] = {}

    if INTERNAL_EXTENSIONS_DIR.exists():
        for path in sorted(INTERNAL_EXTENSIONS_DIR.iterdir()):
            if _is_valid_extension_file(path):
                discovered[path.name] = path

    if EXTERNAL_EXTENSIONS_DIR.exists():
        for path in sorted(EXTERNAL_EXTENSIONS_DIR.iterdir()):
            if _is_valid_extension_file(path):
                discovered[path.name] = path

    return discovered


def _load_extension_module(module_name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load extension module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call_register_extension(
    register_fn: Callable[..., Any],
    *,
    app: typer.Typer,
    command_groups: dict[str, typer.Typer],
) -> None:
    """
    Call register_extension with a flexible, backward-compatible signature.
    """
    supplied_kwargs: dict[str, Any] = {
        "app": app,
        "root_app": app,
        "command_groups": command_groups,
        "get_client": get_client,
    }

    signature = inspect.signature(register_fn)
    accepts_var_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in signature.parameters.values()
    )

    kwargs: dict[str, Any] = {}
    for name in signature.parameters:
        if name in supplied_kwargs:
            kwargs[name] = supplied_kwargs[name]

    if accepts_var_kwargs:
        kwargs = dict(supplied_kwargs)

    if kwargs:
        register_fn(**kwargs)
        return

    if signature.parameters:
        register_fn(app)
        return

    register_fn()


def load_extensions(
    app: typer.Typer,
    *,
    command_groups: dict[str, typer.Typer] | None = None,
) -> list[str]:
    """
    Load and register CLI extensions.

    Returns:
        List of loaded extension filenames.
    """
    loaded: list[str] = []
    groups = command_groups or {}

    for filename, path in sorted(discover_extensions().items()):
        module_name = f"gulp_cli_extension_{path.stem}"
        try:
            module = _load_extension_module(module_name, path)
        except Exception as exc:
            print_warning(f"Failed to load extension {filename}: {exc}")
            continue

        register_fn = getattr(module, "register_extension", None)
        if register_fn is None:
            print_warning(
                f"Skipping extension {filename}: missing register_extension function"
            )
            continue

        if not callable(register_fn):
            print_warning(
                f"Skipping extension {filename}: register_extension is not callable"
            )
            continue

        try:
            _call_register_extension(
                register_fn,
                app=app,
                command_groups=groups,
            )
        except Exception as exc:
            print_warning(f"Failed to register extension {filename}: {exc}")
            continue

        loaded.append(filename)

    return loaded
