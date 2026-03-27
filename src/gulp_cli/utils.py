from __future__ import annotations

import json
from typing import Any

import typer


def parse_json_option(raw: str | None, *, field_name: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON for --{field_name}: {exc}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter(f"--{field_name} must be a JSON object")
    return data


def parse_json_list_option(raw: str | None, *, field_name: str) -> list[dict[str, Any]] | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON for --{field_name}: {exc}") from exc
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data
    raise typer.BadParameter(f"--{field_name} must be a JSON object or a list of JSON objects")


def comma_split(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
