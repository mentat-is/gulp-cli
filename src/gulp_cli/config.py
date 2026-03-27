from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "gulp-cli"
CONFIG_PATH = CONFIG_DIR / "config.json"


class CLIConfigError(Exception):
    """Raised when CLI config is missing or invalid."""


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CLIConfigError(f"Invalid config JSON in {CONFIG_PATH}: {exc}") from exc


def save_config(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def clear_config() -> None:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()


def get_required_url_token() -> tuple[str, str]:
    cfg = load_config()
    url = str(cfg.get("url") or "").strip()
    token = str(cfg.get("token") or "").strip()
    if not url or not token:
        raise CLIConfigError("Not authenticated. Run: gulp-cli login --url <url> --username <u> --password <p>")
    return url, token
