from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import typer
from rich.console import Group
from rich.live import Live
from rich.progress_bar import ProgressBar
from rich.table import Table

from gulp_cli.client import get_client
from gulp_cli.output import console, print_error

app = typer.Typer(help="Request stats commands")

_ONGOING_STATUSES = {"ongoing", "running", "pending", "processing"}


def _human_time(value: Any) -> str:
    if value is None:
        return "-"

    dt: datetime | None = None

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts = ts / 1000.0
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, ValueError, OSError):
            return str(value)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "-"
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    elif isinstance(value, datetime):
        dt = value
    else:
        return str(value)

    if dt is None:
        return str(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(tz=timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 0:
        seconds = 0

    if seconds < 10:
        rel = "just now"
    elif seconds < 60:
        rel = f"{seconds}s ago"
    elif seconds < 3600:
        rel = f"{seconds // 60}m ago"
    elif seconds < 86400:
        rel = f"{seconds // 3600}h ago"
    else:
        rel = f"{seconds // 86400}d ago"

    return f"{dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')} ({rel})"


def _extract_progress_pct(stat: dict[str, Any]) -> float:
    data = stat.get("data")
    if not isinstance(data, dict):
        return 0.0

    pct = data.get("ingest_percentage")
    if pct is None:
        pct = stat.get("ingest_percentage")

    if pct is None:
        status = str(stat.get("status", "")).lower()
        if status in {"done", "completed", "complete", "success", "ok"}:
            return 100.0
        return 0.0

    try:
        value = float(pct)
    except (TypeError, ValueError):
        return 0.0

    if value < 0:
        return 0.0
    if value > 100:
        return 100.0
    return value


def _extract_errors(stat: dict[str, Any]) -> list[str]:
    errors = stat.get("errors")
    if errors is None:
        data = stat.get("data")
        if isinstance(data, dict):
            errors = data.get("errors")
    if errors is None:
        return []
    if isinstance(errors, list):
        return [str(e) for e in errors if str(e).strip()]
    if isinstance(errors, str):
        return [errors] if errors.strip() else []
    return [str(errors)]


def _errors_preview(stat: dict[str, Any], max_len: int = 80) -> str:
    errs = _extract_errors(stat)
    if not errs:
        return "-"
    text = "; ".join(errs)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _status_text(stat: dict[str, Any]) -> str:
    return str(stat.get("status") or "").strip().lower()


def _is_ongoing(stat: dict[str, Any]) -> bool:
    return _status_text(stat) in _ONGOING_STATUSES


def _to_epoch_msec(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = int(float(value))
        if abs(v) < 10_000_000_000:
            return v * 1000
        return v
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            iv = int(raw)
            if abs(iv) < 10_000_000_000:
                return iv * 1000
            return iv
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    return None


def _build_data_cell(stat: dict[str, Any]) -> Group:
    pct = _extract_progress_pct(stat)
    ongoing = _is_ongoing(stat)

    if ongoing and pct <= 0:
        bar: ProgressBar = ProgressBar(total=None, pulse=True, width=18)
        label = f"ongoing {_data_preview(stat.get('data'))}"
    else:
        bar = ProgressBar(total=100, completed=pct, width=18)
        label = f"{pct:.0f}% {_data_preview(stat.get('data'))}"

    return Group(bar, label)


def _build_stats_table(operation_id: str, stats: list[dict[str, Any]]) -> Table:
    table = Table(title=f"GulpRequestStats ({operation_id})")
    table.add_column("user_id", overflow="fold")
    table.add_column("ws_id", overflow="fold")
    table.add_column("req_id", overflow="fold")
    table.add_column("status", overflow="fold")
    table.add_column("req_type", overflow="fold")
    table.add_column("time_updated", overflow="fold")
    table.add_column("data", overflow="fold")
    table.add_column("errors", overflow="fold")

    for stat in stats:
        table.add_row(
            str(stat.get("user_id") or stat.get("owner_id") or "-"),
            str(stat.get("ws_id") or "-"),
            str(stat.get("req_id") or stat.get("id") or "-"),
            str(stat.get("status") or "-"),
            str(stat.get("req_type") or stat.get("task_type") or "-"),
            _human_time(stat.get("time_updated") or stat.get("updated_at")),
            _build_data_cell(stat),
            _errors_preview(stat),
        )

    return table


def _data_preview(data: Any, max_len: int = 100) -> str:
    if data is None:
        return "-"
    if isinstance(data, str):
        text = data
    else:
        try:
            text = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
        except TypeError:
            text = str(data)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


@app.command("list")
def list_stats(
    operation_id: str = typer.Argument(..., help="Operation ID"),
    ongoing_only: bool = typer.Option(
        True,
        "--ongoing-only/--all",
        help="Show only ongoing requests by default.",
    ),
    user_id: str | None = typer.Option(None, "--user-id", help="Filter by user_id."),
    req_type: str | None = typer.Option(None, "--req-type", help="Filter by request type (e.g. ingest, query, enrich)."),
    server_id: str | None = typer.Option(None, "--server-id", help="Filter by server_id."),
    time_created_from: str | None = typer.Option(
        None,
        "--time-created-from",
        help="Filter requests created at or after this timestamp (epoch sec/ms or ISO8601).",
    ),
    time_created_to: str | None = typer.Option(
        None,
        "--time-created-to",
        help="Filter requests created at or before this timestamp (epoch sec/ms or ISO8601).",
    ),
    errors: str = typer.Option(
        "any",
        "--errors",
        help="Filter by errors: any|present|absent.",
    ),
    live: bool = typer.Option(
        True,
        "--live/--no-live",
        help="Auto-refresh table and animate ongoing rows until no filtered ongoing stats remain.",
    ),
    refresh_seconds: float = typer.Option(
        1.0,
        "--refresh-seconds",
        min=0.2,
        help="Refresh interval for --live mode.",
    ),
    limit: int = typer.Option(100, "--limit", min=1, help="Max rows to render."),
) -> None:
    """List GulpRequestStats as a table with per-request progress bars.

    Default columns: user_id, ws_id, req_id, status, req_type,
    time_updated (human readable), data, errors.
    """

    errors_mode = errors.strip().lower()
    if errors_mode not in {"any", "present", "absent"}:
        raise typer.BadParameter("--errors must be one of: any, present, absent")

    created_from_ms = _to_epoch_msec(time_created_from)
    if time_created_from is not None and created_from_ms is None:
        raise typer.BadParameter("Invalid --time-created-from value")

    created_to_ms = _to_epoch_msec(time_created_to)
    if time_created_to is not None and created_to_ms is None:
        raise typer.BadParameter("Invalid --time-created-to value")

    def _match_filters(stat: dict[str, Any]) -> bool:
        stat_user = str(stat.get("user_id") or stat.get("owner_id") or "")
        stat_req_type = str(stat.get("req_type") or stat.get("task_type") or "")
        stat_server = str(stat.get("server_id") or "")

        if user_id and stat_user != user_id:
            return False
        if req_type and stat_req_type != req_type:
            return False
        if server_id and stat_server != server_id:
            return False

        created_ms = _to_epoch_msec(stat.get("time_created") or stat.get("created_at"))
        if created_from_ms is not None and (created_ms is None or created_ms < created_from_ms):
            return False
        if created_to_ms is not None and (created_ms is None or created_ms > created_to_ms):
            return False

        has_errors = len(_extract_errors(stat)) > 0
        if errors_mode == "present" and not has_errors:
            return False
        if errors_mode == "absent" and has_errors:
            return False

        return True

    async def _fetch_filtered(client: Any) -> list[dict[str, Any]]:
        stats = await client.plugins.request_list(
            operation_id=operation_id,
            running_only=ongoing_only,
        )
        filtered = [s for s in stats if _match_filters(s)]
        return filtered[:limit]

    async def _run() -> None:
        async with get_client() as client:
            initial = await _fetch_filtered(client)
            if not initial:
                print_error("No request stats found for the selected filters.")
                return

            if not live:
                console.print(_build_stats_table(operation_id, initial))
                return

            with Live(console=console, refresh_per_second=max(4, int(1 / refresh_seconds) + 1)) as live_view:
                current = initial
                while True:
                    live_view.update(_build_stats_table(operation_id, current), refresh=True)
                    if not any(_is_ongoing(s) for s in current):
                        break
                    await asyncio.sleep(refresh_seconds)
                    current = await _fetch_filtered(client)
                    if not current:
                        break

    asyncio.run(_run())