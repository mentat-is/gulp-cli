from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Group
from rich.progress_bar import ProgressBar
from rich.live import Live
from rich.text import Text
from rich.table import Table

from gulp_cli.client import get_client
from gulp_cli.output import console, print_error, print_json, print_result
from gulp_cli.utils import parse_json_option

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


def _extract_source_ids(stat: dict[str, Any]) -> list[str]:
    data = stat.get("data")
    if not isinstance(data, dict):
        return []

    sources = data.get("sources")
    if not isinstance(sources, list):
        return []

    source_ids: list[str] = []
    for item in sources:
        source_id = ""
        if isinstance(item, dict):
            source_id = str(item.get("source_id") or item.get("id") or "").strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            source_id = str(item[1] or "").strip()
        if source_id:
            source_ids.append(source_id)
    return source_ids


def _remember_source_ids(
    stats: list[dict[str, Any]], request_source_ids: dict[str, list[str]]
) -> None:
    for stat in stats:
        req_id = str(stat.get("req_id") or stat.get("id") or "").strip()
        if not req_id:
            continue
        source_ids = _extract_source_ids(stat)
        if source_ids:
            request_source_ids[req_id] = source_ids


async def _fetch_source_name_lookup(
    client: Any, source_ids: list[str]
) -> dict[str, str]:
    lookup: dict[str, str] = {}
    unique_source_ids = sorted({source_id for source_id in source_ids if source_id})
    if not unique_source_ids:
        return lookup

    async def _fetch_one(source_id: str) -> tuple[str, str]:
        try:
            source = await client.operations.source_get(source_id)
            if hasattr(source, "model_dump"):
                source = source.model_dump(exclude_none=True)
            if isinstance(source, dict):
                source_name = str(source.get("name") or source.get("id") or "").strip()
                return source_id, source_name
        except Exception:
            pass
        return source_id, ""

    results = await asyncio.gather(
        *[_fetch_one(source_id) for source_id in unique_source_ids]
    )
    for source_id, source_name in results:
        if source_name:
            lookup[source_id] = source_name
    return lookup


def _multiline_label(label: str, threshold: int = 40) -> str:
    text = str(label or "").strip()
    if len(text) <= threshold:
        return text
    if "/" in text:
        is_absolute = text.startswith("/")
        parts = [part for part in text.split("/") if part]
        if not parts:
            return text
        body = "/\n".join(parts)
        return f"/{body}" if is_absolute else body
    if "\\" in text:
        parts = [part for part in text.split("\\") if part]
        if not parts:
            return text
        return "\\\n".join(parts)
    return text


def _resolve_display_label(
    stat: dict[str, Any],
    source_name_lookup: dict[str, str] | None = None,
    request_source_ids: dict[str, list[str]] | None = None,
) -> str:
    req_type = _req_type(stat)
    if req_type != "ingest":
        return _significant_data(stat)

    req_id = str(stat.get("req_id") or stat.get("id") or "").strip()
    source_ids = (
        request_source_ids.get(req_id, []) if request_source_ids and req_id else []
    )
    if not source_ids:
        source_ids = _extract_source_ids(stat)
        if source_ids and request_source_ids is not None and req_id:
            request_source_ids[req_id] = source_ids

    if source_name_lookup and source_ids:
        labels = [
            source_name_lookup.get(source_id, "").strip() for source_id in source_ids
        ]
        labels = [label for label in labels if label]
        if labels:
            return "\n".join(_multiline_label(label) for label in labels)

    data = stat.get("data")
    if isinstance(data, dict):
        source_processed = data.get("source_processed")
        source_total = data.get("source_total")
        if source_processed is not None or source_total is not None:
            processed_text = str(
                source_processed if source_processed is not None else 0
            )
            total_text = str(source_total if source_total is not None else "-")
            failed_text = data.get("source_failed")
            if failed_text is not None:
                return f"sources={processed_text}/{total_text} failed={failed_text}"
            return f"sources={processed_text}/{total_text}"

    return "ingest"


def _build_data_cell(
    stat: dict[str, Any],
    source_name_lookup: dict[str, str] | None = None,
    request_source_ids: dict[str, list[str]] | None = None,
) -> Group:
    pct = _extract_progress_pct(stat)
    ongoing = _is_ongoing(stat)
    sig = _resolve_display_label(stat, source_name_lookup, request_source_ids)
    if ongoing and pct <= 0:
        bar: ProgressBar = ProgressBar(total=None, pulse=True, width=18)
    else:
        bar = ProgressBar(total=100, completed=pct, width=18)
    return Group(bar, Text(sig, overflow="fold", no_wrap=False))


def _build_stats_table(
    operation_id: str,
    stats: list[dict[str, Any]],
    source_name_lookup: dict[str, str] | None = None,
    request_source_ids: dict[str, list[str]] | None = None,
) -> Table:
    table = Table(title=f"GulpRequestStats ({operation_id})")
    table.add_column("user_id", overflow="fold")
    table.add_column("ws_id", overflow="fold")
    table.add_column("req_id", overflow="fold")
    table.add_column("status", overflow="fold")
    table.add_column("req_type", overflow="fold")
    table.add_column("time_updated", overflow="fold")
    table.add_column("data", overflow="fold", no_wrap=False, ratio=2)
    table.add_column("errors", overflow="fold")

    for stat in stats:
        table.add_row(
            str(stat.get("user_id") or stat.get("owner_id") or "-"),
            str(stat.get("ws_id") or "-"),
            str(stat.get("req_id") or stat.get("id") or "-"),
            str(stat.get("status") or "-"),
            str(stat.get("req_type") or stat.get("task_type") or "-"),
            _human_time(stat.get("time_updated") or stat.get("updated_at")),
            _build_data_cell(stat, source_name_lookup, request_source_ids),
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


def _req_type(stat: dict[str, Any]) -> str:
    req_type = str(stat.get("req_type") or stat.get("task_type") or "").strip().lower()
    if req_type == "external_query":
        return "ext_query"
    if req_type == "ingest_raw":
        return "raw_ingest"
    return req_type


def _basename(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return Path(text).name or text


def _first_non_empty(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            val = value.strip()
            if val:
                return val
        elif isinstance(value, (int, float)):
            return str(value)
    return ""


def _significant_data(
    stat: dict[str, Any], source_lookup: dict[str, str] | None = None
) -> str:
    req_type = _req_type(stat)
    data = stat.get("data")
    if not isinstance(data, dict):
        return _data_preview(data)

    if req_type == "ingest":
        source_processed = data.get("source_processed")
        source_total = data.get("source_total")
        if source_processed is not None or source_total is not None:
            processed_text = str(
                source_processed if source_processed is not None else 0
            )
            total_text = str(source_total if source_total is not None else "-")
            failed_text = data.get("source_failed")
            if failed_text is not None:
                return f"sources={processed_text}/{total_text} failed={failed_text}"
            return f"sources={processed_text}/{total_text}"

        return _data_preview(data)

    # raw_ingest: counters remain the most useful compact signal
    if req_type == "raw_ingest":
        ingested = data.get("records_ingested")
        skipped = data.get("records_skipped")
        failed = data.get("records_failed")
        return f"ing={ingested or 0} skip={skipped or 0} fail={failed or 0}"

    # query / ext_query: focus on query group and progress
    if req_type in {"query", "ext_query"}:
        group = _first_non_empty(data, ["q_group", "group", "name"])
        num_q = data.get("num_queries")
        done_q = data.get("completed_queries")
        failed_q = data.get("failed_queries")
        hits = data.get("total_hits")
        prefix = f"group={group}" if group else "query"
        if num_q is not None and done_q is not None:
            return (
                f"{prefix} ({done_q}/{num_q}, failed={failed_q or 0}) "
                f"hits={hits if hits is not None else '-'}"
            )
        if hits is not None:
            return f"{prefix} hits={hits}"
        return prefix

    # rebase / enrich: focus on updated docs counts
    if req_type in {"rebase", "enrich"}:
        updated = data.get("updated")
        total_hits = data.get("total_hits")
        plugin = _first_non_empty(data, ["plugin"])
        if updated is not None or total_hits is not None:
            core = f"updated={updated or 0}/{total_hits if total_hits is not None else '-'}"
            return f"{core} plugin={plugin}" if plugin else core
        return f"plugin={plugin}" if plugin else _data_preview(data)

    return _data_preview(data)


@app.command("list")
def list_stats(
    operation_id: str = typer.Argument(..., help="Operation ID"),
    ongoing_only: bool = typer.Option(
        True,
        "--ongoing-only/--all",
        help="Show only ongoing requests by default.",
    ),
    user_id: str | None = typer.Option(None, "--user-id", help="Filter by user_id."),
    req_type: str | None = typer.Option(
        None, "--req-type", help="Filter by request type (e.g. ingest, query, enrich)."
    ),
    server_id: str | None = typer.Option(
        None, "--server-id", help="Filter by server_id."
    ),
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
        if created_from_ms is not None and (
            created_ms is None or created_ms < created_from_ms
        ):
            return False
        if created_to_ms is not None and (
            created_ms is None or created_ms > created_to_ms
        ):
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
            request_source_ids: dict[str, list[str]] = {}
            source_name_lookup: dict[str, str] = {}
            initial = await _fetch_filtered(client)
            if not initial:
                print_error("No request stats found for the selected filters.")
                return

            _remember_source_ids(initial, request_source_ids)
            source_name_lookup.update(
                await _fetch_source_name_lookup(
                    client,
                    [
                        source_id
                        for source_ids in request_source_ids.values()
                        for source_id in source_ids
                    ],
                )
            )

            if not live:
                console.print(
                    _build_stats_table(
                        operation_id, initial, source_name_lookup, request_source_ids
                    )
                )
                return

            with Live(
                console=console, refresh_per_second=max(4, int(1 / refresh_seconds) + 1)
            ) as live_view:
                current = initial
                while True:
                    _remember_source_ids(current, request_source_ids)
                    source_name_lookup.update(
                        await _fetch_source_name_lookup(
                            client,
                            [
                                source_id
                                for source_ids in request_source_ids.values()
                                for source_id in source_ids
                                if source_id not in source_name_lookup
                            ],
                        )
                    )
                    live_view.update(
                        _build_stats_table(
                            operation_id,
                            current,
                            source_name_lookup,
                            request_source_ids,
                        ),
                        refresh=True,
                    )
                    if not any(_is_ongoing(s) for s in current):
                        break
                    await asyncio.sleep(refresh_seconds)
                    current = await _fetch_filtered(client)
                    if not current:
                        break

    asyncio.run(_run())


@app.command("get")
def get_stats(
    req_id: str = typer.Argument(..., help="Request stats ID / req_id"),
) -> None:
    """Get one GulpRequestStats object by request ID."""

    async def _run() -> None:
        async with get_client() as client:
            stats = await client.plugins.request_get(req_id)
            print_result(stats)

    asyncio.run(_run())


@app.command("delete-bulk")
def delete_bulk(
    operation_id: str,
    flt: str | None = typer.Option(None, "--flt", help="GulpCollabFilter JSON object"),
    delete_all: bool = typer.Option(
        False, "--all", help="Delete all request stats in the operation (dangerous)"
    ),
) -> None:
    """Delete request stats using the server-side object_delete_bulk API."""

    async def _run() -> None:
        if not delete_all and not flt:
            raise typer.BadParameter(
                "Provide --flt or pass --all to delete all request stats in the operation"
            )
        flt_obj = parse_json_option(flt, field_name="flt") or {}
        async with get_client() as client:
            deleted = await client.plugins.object_delete_bulk(
                operation_id=operation_id,
                obj_type="request_stats",
                flt=flt_obj,
            )
            print_result(deleted)

    asyncio.run(_run())


@app.command("cancel")
def cancel_request(
    req_id: str,
    expire_now: bool = typer.Option(
        False,
        "--expire-now",
        help="Immediately expire and delete request stats entry after cancellation",
    ),
) -> None:
    """Cancel a running request using the server-side request_cancel API."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.plugins.request_cancel(
                req_id_to_cancel=req_id,
                expire_now=expire_now,
            )
            print_result(result)

    asyncio.run(_run())
