from __future__ import annotations

import json
from contextvars import ContextVar
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "gulp-cli"
CONFIG_PATH = CONFIG_DIR / "config.json"
_AS_USER_OVERRIDE: ContextVar[str | None] = ContextVar("gulp_cli_as_user_override", default=None)


class CLIConfigError(Exception):
    """Raised when CLI config is missing or invalid."""


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    sessions_raw = data.get("sessions")
    sessions: dict[str, dict[str, Any]] = {}

    if isinstance(sessions_raw, dict):
        for username, session in sessions_raw.items():
            if not isinstance(session, dict):
                continue

            name = str(username).strip()
            url = str(session.get("url") or data.get("url") or "").strip()
            token = str(session.get("token") or "").strip()
            user_id = str(session.get("user_id") or name).strip()

            if not name or not url or not token:
                continue

            sessions[name] = {
                "url": url.rstrip("/"),
                "token": token,
                "user_id": user_id,
                "expires_at": session.get("expires_at"),
            }
    else:
        url = str(data.get("url") or "").strip()
        token = str(data.get("token") or "").strip()
        user_id = str(data.get("user_id") or "").strip()
        if url and token:
            username = user_id or "default"
            sessions[username] = {
                "url": url.rstrip("/"),
                "token": token,
                "user_id": user_id or username,
                "expires_at": data.get("expires_at"),
            }

    active_user = str(data.get("active_user") or "").strip()
    if active_user not in sessions:
        active_user = next(iter(sessions), "")

    return {
        "active_user": active_user,
        "sessions": sessions,
    }


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"active_user": "", "sessions": {}}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CLIConfigError(f"Invalid config JSON in {CONFIG_PATH}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CLIConfigError(f"Invalid config JSON in {CONFIG_PATH}: root object must be a JSON object")
    return _normalize_config(raw)


def save_config(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_config(data)
    CONFIG_PATH.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")


def clear_config() -> None:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()


def set_runtime_as_user(user_name: str | None) -> None:
    value = str(user_name or "").strip() or None
    _AS_USER_OVERRIDE.set(value)


def get_runtime_as_user() -> str | None:
    return _AS_USER_OVERRIDE.get()


def get_saved_users() -> list[str]:
    return list(load_config().get("sessions", {}).keys())


def save_session(
    *,
    url: str,
    username: str,
    token: str,
    user_id: str,
    expires_at: Any,
    make_active: bool = True,
) -> dict[str, Any]:
    cfg = load_config()
    sessions = dict(cfg.get("sessions") or {})
    name = username.strip()
    sessions[name] = {
        "url": url.rstrip("/"),
        "token": token,
        "user_id": user_id.strip() or name,
        "expires_at": expires_at,
    }
    cfg["sessions"] = sessions
    if make_active or not cfg.get("active_user"):
        cfg["active_user"] = name
    save_config(cfg)
    return cfg


def get_selected_session(user_name: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    sessions = cfg.get("sessions") or {}
    selected = (user_name or get_runtime_as_user() or cfg.get("active_user") or "").strip()

    if not sessions:
        raise CLIConfigError("Not authenticated. Run: gulp-cli auth login --url <url> --username <u> --password <p>")

    if not selected:
        selected = next(iter(sessions), "")

    session = sessions.get(selected)
    if not isinstance(session, dict):
        available = ", ".join(sorted(sessions))
        raise CLIConfigError(
            f"User '{selected}' is not logged in. Logged-in users: {available}"
        )

    return {"username": selected, **session}


def delete_session(user_name: str | None = None) -> dict[str, Any] | None:
    cfg = load_config()
    sessions = dict(cfg.get("sessions") or {})
    selected = (user_name or get_runtime_as_user() or cfg.get("active_user") or "").strip()
    if not selected:
        return None

    removed = sessions.pop(selected, None)
    if removed is None:
        return None

    if sessions:
        if cfg.get("active_user") == selected:
            cfg["active_user"] = next(iter(sessions))
        cfg["sessions"] = sessions
        save_config(cfg)
    else:
        clear_config()

    return {"username": selected, **removed}


def get_required_url_token() -> tuple[str, str]:
    session = get_selected_session()
    url = str(session.get("url") or "").strip()
    token = str(session.get("token") or "").strip()
    if not url or not token:
        raise CLIConfigError("Not authenticated. Run: gulp-cli auth login --url <url> --username <u> --password <p>")
    return url, token
