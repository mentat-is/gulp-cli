from __future__ import annotations

import asyncio
import bz2
import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from glob import glob, has_magic
from pathlib import Path
from typing import Any, Awaitable, Callable

from gulp_cli.config import get_runtime_config_dir, get_runtime_verbose
import typer
from gulp_sdk.exceptions import NotFoundError
from gulp_sdk.websocket import WSMessage, WSMessageType
from rich.markup import escape
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)

from gulp_cli.client import get_client
from gulp_cli.output import (
    console,
    print_error,
    print_json,
    print_result,
    print_warning,
)
from gulp_cli.utils import parse_json_option

app = typer.Typer(help="Ingestion commands")

# How long to keep the websocket alive waiting for STATS_CREATE confirmation
# when --wait is NOT used.  Should be well above the worker task-scheduling lag.
_WS_CONFIRM_TIMEOUT_SEC = 30.0
_TERMINAL_STATUSES = {"done", "failed", "canceled"}
_MAX_ZIP_PART_SIZE_BYTES = 4 * 1024**3 - 1


def _print_marker(marker: str, **payload: Any) -> None:
    console.print(
        f"GULP_MARKER: {marker} | {json.dumps(payload, sort_keys=True, default=str)}",
        markup=False,
        highlight=False,
        soft_wrap=True,
    )


def _print_ingestion_finished_marker(results: list[dict[str, Any]]) -> None:
    _print_marker(
        "[MARKER_INGESTION_FINISHED]",
        requests_total=len(results),
        requests_done=sum(1 for item in results if item.get("status") == "done"),
        requests_failed=sum(1 for item in results if item.get("status") == "failed"),
        requests_canceled=sum(
            1 for item in results if item.get("status") == "canceled"
        ),
        requests_timeout=sum(1 for item in results if item.get("status") == "timeout"),
        ingested=sum(int(item.get("ingested") or 0) for item in results),
        skipped=sum(int(item.get("skipped") or 0) for item in results),
        failed=sum(int(item.get("failed") or 0) for item in results),
    )


def _plugin_params_request_compression(plugin_params: dict[str, Any] | None) -> bool:
    """Return True when plugin parameters request core decompression."""
    return bool(plugin_params and plugin_params.get("compressed"))


def _bz2_compress_file_for_ingestion_sync(file_path: str) -> str:
    """Compress a file into a temporary bzip2 file for upload."""
    source_path = Path(file_path)
    fd, temp_path = tempfile.mkstemp(
        prefix=f"{source_path.name}.",
        suffix=".bz2",
    )
    os.close(fd)

    try:
        with open(source_path, "rb") as src, bz2.open(temp_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
    except Exception:
        try:
            Path(temp_path).unlink()
        except FileNotFoundError:
            pass
        raise

    return temp_path


async def _maybe_bz2_compress_file_for_ingestion(
    file_path: str, plugin_params: dict[str, Any] | None
) -> tuple[str, str | None]:
    """Return an upload path and optional temporary path to delete after upload."""
    if not _plugin_params_request_compression(plugin_params):
        return file_path, None
    temp_path = await asyncio.to_thread(_bz2_compress_file_for_ingestion_sync, file_path)
    return temp_path, temp_path


def _default_ingest_batch_size() -> int:
    return max(1, (os.cpu_count() or 1) * 2)


def _format_per_file_progress_line(item: dict[str, Any]) -> str:
    req_id = str(item.get("req_id") or "")
    req_tag = req_id[:8] if req_id else "no-reqid"
    file_name = Path(str(item.get("file") or "")).name or "<unknown>"
    status = str(item.get("status") or "unknown")
    if status in {"failed", "canceled"}:
        status = f"{status.upper()}!"
    ingested = int(item.get("ingested") or 0)
    skipped = int(item.get("skipped") or 0)
    failed = int(item.get("failed") or 0)
    return (
        f"[{req_tag}] {file_name}: {status} "
        f"(ingested={ingested}, skipped={skipped}, failed={failed})"
    )


def _format_per_file_log_line(item: dict[str, Any]) -> str:
    req_id = str(item.get("req_id") or "")
    req_tag = req_id if req_id else "no-reqid"
    file_name = Path(str(item.get("file") or "")).name or "<unknown>"
    event = str(item.get("event") or "update").replace("_", " ")
    status = str(item.get("status") or "unknown")
    if status in {"failed", "canceled"}:
        status = f"{status.upper()}!"
    ingested = int(item.get("ingested") or 0)
    skipped = int(item.get("skipped") or 0)
    failed = int(item.get("failed") or 0)
    pct = item.get("pct")
    prefix = (
        f"req_id={req_tag} {file_name} {event}: {status}"
        if pct is None
        else f"req_id={req_tag} {file_name} {event}: {status} ({int(pct)}%)"
    )
    line = (
        f"{prefix} "
        f"(ingested={ingested}, skipped={skipped}, failed={failed})"
    )
    errors = item.get("errors")
    if errors and item.get("status") == "failed":
        return f"{line} errors={errors}"
    return line


def _extract_errors(payload: dict[str, Any]) -> list[str]:
    nested = payload.get("data")
    candidates = [payload, nested if isinstance(nested, dict) else {}]
    errors: list[str] = []
    for data in candidates:
        raw_errors = data.get("errors")
        if isinstance(raw_errors, list):
            errors.extend(str(item) for item in raw_errors if item)
        elif raw_errors:
            errors.append(str(raw_errors))
        for key in ("error", "message", "detail", "reason"):
            value = data.get(key)
            if value:
                errors.append(str(value))
    return list(dict.fromkeys(errors))


def _with_failed_errors(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("status") != "failed":
        return item
    result = item.get("result")
    errors = _extract_errors(result if isinstance(result, dict) else {})
    if not errors:
        return item
    return {**item, "errors": errors}


async def _ensure_operation_exists(
    client: Any,
    operation_id: str,
    *,
    create_if_missing: bool,
) -> None:
    """Ensure operation exists, optionally creating it when missing."""
    try:
        await client.operations.get(operation_id)
    except NotFoundError:
        if not create_if_missing:
            raise
        await client.operations.create(name=operation_id)
        if not get_runtime_verbose():
            print_warning(f"Operation {operation_id} was missing and has been created.")


def _read_path_list(
    positional_paths: list[str],
    paths_file: str | None,
    *,
    noun: str,
) -> list[str]:
    if not positional_paths and paths_file is None:
        raise typer.BadParameter(f"Provide at least one {noun} argument or --paths-file")

    if paths_file is None:
        return list(positional_paths)

    file_path = _resolve_path(paths_file)
    if not file_path.is_file():
        raise typer.BadParameter(f"Paths file not found: {file_path}")

    console.print(f"[cyan]Reading path list[/] {file_path}")
    if positional_paths:
        console.print(
            f"[yellow]Ignoring positional {noun} patterns[/] because --paths-file is set"
        )
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise typer.BadParameter(
            f"Paths file must be UTF-8 text, not binary data: {file_path}. "
            "For shell globs, omit --paths-file and pass the pattern as a positional argument."
        ) from exc

    raw_entries = [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    console.print(
        f"[cyan]Loaded[/] {len(raw_entries)} {noun} expression(s) from {file_path}"
    )
    return raw_entries


def _resolve_path(raw_path: str) -> Path:
    expanded = _expand_path_expression(raw_path)
    return Path(expanded).resolve()


def _expand_path_expression(raw_path: str) -> str:
    """Expand shell-style path expressions (env vars and '~')."""
    return os.path.expandvars(os.path.expanduser(raw_path.strip()))


def _parse_zip_split_size(size_spec: str | int | None) -> int | None:
    if size_spec is None:
        return None
    if isinstance(size_spec, int):
        return max(0, size_spec)

    text = str(size_spec).strip()
    if not text:
        return None

    match = re.fullmatch(r"(?i)(\d+)(b|kb|mb|gb)?", text)
    if match is None:
        raise typer.BadParameter(
            "Invalid split size. Use a plain number of bytes or a suffix like mb/gb."
        )

    value = int(match.group(1))
    suffix = (match.group(2) or "b").lower()
    multipliers = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}
    return max(0, value * multipliers[suffix])


def _format_zip_split_size_spec(size_bytes: int) -> str:
    if size_bytes >= 1024**3 and size_bytes % (1024**3) == 0:
        return f"{size_bytes // (1024**3)}g"
    if size_bytes >= 1024**2 and size_bytes % (1024**2) == 0:
        return f"{size_bytes // (1024**2)}m"
    if size_bytes >= 1024 and size_bytes % 1024 == 0:
        return f"{size_bytes // 1024}k"
    return str(size_bytes)


def _expand_source_patterns(
    path_patterns: list[str],
    paths_file: str | None,
) -> list[tuple[Path, Path]]:
    raw_entries = _read_path_list(path_patterns, paths_file, noun="path")

    expanded_paths: list[tuple[Path, Path]] = []
    seen: set[tuple[Path, Path]] = set()
    for raw_entry in raw_entries:
        expanded_entry = _expand_path_expression(raw_entry)
        if not expanded_entry:
            continue

        if has_magic(expanded_entry):
            pattern_path = Path(expanded_entry)
            base_dir = _resolve_glob_base(pattern_path)
            matches = [
                Path(match).resolve()
                for match in sorted(glob(expanded_entry, recursive=True))
            ]
            if not matches:
                raise typer.BadParameter(
                    f"Path mask did not match any files: {expanded_entry}"
                )

            for match in matches:
                item = (match, base_dir)
                if item not in seen:
                    seen.add(item)
                    expanded_paths.append(item)
            continue

        resolved_path = _resolve_path(expanded_entry)
        if not resolved_path.exists():
            raise typer.BadParameter(f"Path not found: {resolved_path}")

        base_dir = resolved_path.parent
        item = (resolved_path, base_dir)
        if item not in seen:
            seen.add(item)
            expanded_paths.append(item)

    return expanded_paths


def _resolve_glob_base(pattern_path: Path) -> Path:
    parts = pattern_path.parts
    if pattern_path.is_absolute():
        base_dir = Path(pattern_path.anchor)
        part_index = 1
    else:
        base_dir = Path.cwd()
        part_index = 0

    for part in parts[part_index:]:
        if has_magic(part):
            break
        base_dir /= part

    return base_dir.resolve()


def _safe_archive_name(path: str) -> str:
    """Return a ZIP entry path without roots or dot-directory components."""
    return "/".join(
        _zip_path_part(part)
        for part in path.replace("\\", "/").split("/")
        if part not in ("", ".", "..")
    )


def _zip_path_part(part: str) -> str:
    if re.fullmatch(r"[A-Za-z]:", part):
        return part[0]
    return part


def _preserved_archive_name(source_path: Path) -> str:
    try:
        absolute_path = source_path.resolve()
    except OSError:
        absolute_path = Path(os.path.abspath(source_path))
    return _safe_archive_name(str(absolute_path))


def _build_zip_from_sources(
    output_zip: Path,
    sources: list[tuple[Path, Path]],
    *,
    preserve_path: bool = False,
    split_size_bytes: int | None = None,
) -> tuple[int, list[str], list[Path]]:
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    archived_entries: list[str] = []
    archived_count = 0
    seen_archive_entries: set[str] = set()
    seen_source_files: set[Path] = set()
    created_archives: list[Path] = []
    total_entries = 0
    entries_added = 0

    def _archive_name_for_path(source_path: Path, base_dir: Path) -> str:
        if preserve_path:
            return _preserved_archive_name(source_path)
        try:
            rel_path = source_path.relative_to(base_dir)
        except ValueError:
            rel_path = source_path.name
        return _safe_archive_name(rel_path.as_posix())

    planned_entries: list[tuple[Path, Path, str]] = []
    for source_path, base_dir in sources:
        try:
            console.print(f"[cyan]Scanning[/] {source_path}")
            if not source_path.exists():
                raise FileNotFoundError(source_path)

            if source_path.is_file():
                planned_entries.append(
                    (
                        source_path,
                        base_dir,
                        _archive_name_for_path(source_path, base_dir),
                    )
                )
                continue

            child_paths = sorted(source_path.rglob("*"))
            if not child_paths:
                planned_entries.append(
                    (
                        source_path,
                        base_dir,
                        _archive_name_for_path(source_path, base_dir),
                    )
                )
                continue

            for current_path in child_paths:
                try:
                    planned_entries.append(
                        (
                            current_path,
                            base_dir,
                            _archive_name_for_path(current_path, base_dir),
                        )
                    )
                except Exception as exc:
                    _print_marker(
                        "[MARKER_ZIP_CREATE_ERROR]",
                        path=str(current_path),
                        zip=str(output_zip),
                        error=str(exc),
                    )
                    print_error(
                        f"Skipping {current_path} while creating ZIP {output_zip}: {exc}"
                    )
        except Exception as exc:
            _print_marker(
                "[MARKER_ZIP_CREATE_ERROR]",
                path=str(source_path),
                zip=str(output_zip),
                error=str(exc),
            )
            print_error(
                f"Skipping {source_path} while creating ZIP {output_zip}: {exc}"
            )

    entries_to_archive: list[tuple[Path, str]] = []
    planned_archive_entries: set[str] = set()
    planned_source_files: set[Path] = set()
    for source_path, _base_dir, archive_name_str in planned_entries:
        if archive_name_str in planned_archive_entries:
            continue
        if source_path.is_file() and source_path in planned_source_files:
            continue
        planned_archive_entries.add(archive_name_str)
        if source_path.is_file():
            planned_source_files.add(source_path)
        entries_to_archive.append((source_path, archive_name_str))
    total_entries = len(entries_to_archive)

    if split_size_bytes is not None and split_size_bytes > _MAX_ZIP_PART_SIZE_BYTES:
        raise typer.BadParameter(
            "Split size must be at most 4gb so temporary ZIP files stay FAT32-safe"
        )

    def _write_archive(
        archive_path: Path,
        entries_to_store: list[tuple[Path, str]],
        *,
        log_entries: bool = False,
    ) -> None:
        nonlocal entries_added
        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for source_path, archive_name_str in entries_to_store:
                try:
                    if source_path.is_dir():
                        archive.writestr(f"{archive_name_str}/", "")
                        info = archive.getinfo(f"{archive_name_str}/")
                    else:
                        archive.write(source_path, arcname=archive_name_str)
                        info = archive.getinfo(archive_name_str)
                    if log_entries and total_entries:
                        entries_added += 1
                        percent = int((entries_added / total_entries) * 100)
                        console.print(
                            "[cyan]Added ZIP entry[/] "
                            f"{info.filename} "
                            f"({info.file_size} bytes -> {info.compress_size} bytes, "
                            f"{entries_added}/{total_entries}, {percent}%)"
                        )
                        _print_marker(
                            "[MARKER_FILE_ADDED_TO_ZIP]",
                            zip=str(output_zip),
                            entry=info.filename,
                            source=str(source_path),
                            file_size=info.file_size,
                            compress_size=info.compress_size,
                            current=entries_added,
                            total=total_entries,
                            percent=percent,
                        )
                except Exception as exc:
                    _print_marker(
                        "[MARKER_ZIP_CREATE_ERROR]",
                        path=str(source_path),
                        zip=str(output_zip),
                        error=str(exc),
                    )
                    print_error(
                        f"Skipping {source_path} while creating ZIP {output_zip}: {exc}"
                    )

    def _record_entry(source_path: Path, archive_name_str: str) -> None:
        nonlocal archived_count
        entry_name = (
            f"{archive_name_str}/" if source_path.is_dir() else archive_name_str
        )
        if entry_name in seen_archive_entries or source_path in seen_source_files:
            return
        seen_archive_entries.add(entry_name)
        archived_entries.append(entry_name)
        if source_path.is_dir():
            return
        seen_source_files.add(source_path)
        archived_count += 1

    def _publish_archive(temp_path: Path, final_path: Path) -> None:
        if final_path.exists():
            final_path.unlink()
        shutil.move(str(temp_path), str(final_path))
        console.print(
            f"[green]Wrote[/] {final_path} ({final_path.stat().st_size} bytes)"
        )

    class _SplitZipWriter:
        def __init__(
            self,
            volume_base: Path,
            split_size: int,
            on_volume_open: Callable[[Path, int, int], None],
        ) -> None:
            self._volume_base = volume_base
            self._split_size = split_size
            self._on_volume_open = on_volume_open
            self._volume_index = 0
            self._volume_size = 0
            self._position = 0
            self._handle: Any = None
            self.volumes: list[Path] = []

        def writable(self) -> bool:
            return True

        def seekable(self) -> bool:
            return False

        def tell(self) -> int:
            return self._position

        def seek(self, _offset: int, _whence: int = 0) -> int:
            raise OSError("split ZIP writer is not seekable")

        def write(self, data: bytes) -> int:
            data_view = memoryview(data)
            written = 0
            while written < len(data_view):
                if self._handle is None or self._volume_size >= self._split_size:
                    self._open_next_volume()
                remaining = self._split_size - self._volume_size
                chunk = data_view[written : written + remaining]
                self._handle.write(chunk)
                chunk_size = len(chunk)
                self._volume_size += chunk_size
                self._position += chunk_size
                written += chunk_size
            return written

        def flush(self) -> None:
            if self._handle is not None:
                self._handle.flush()

        def close(self) -> None:
            if self._handle is not None:
                self._handle.close()
                self._handle = None

        def _open_next_volume(self) -> None:
            self.close()
            self._volume_index += 1
            self._volume_size = 0
            volume_path = self._volume_base.with_name(
                f"{self._volume_base.name}.{self._volume_index:03d}"
            )
            self._handle = volume_path.open("wb")
            self.volumes.append(volume_path)
            self._on_volume_open(volume_path, self._volume_index, self._position)

    def _write_multipart_archive(temp_dir: Path) -> list[Path]:
        temp_archive_base = temp_dir / output_zip.name
        console.print(
            "[yellow]Creating multipart ZIP volumes; extract with 7z or another "
            "split-ZIP compatible tool.[/]"
        )

        def _print_volume_start(
            volume_path: Path,
            volume_index: int,
            byte_offset: int,
        ) -> None:
            console.print(
                "[cyan]Starting split volume[/] "
                f"{volume_path.name} ({volume_index}, offset={byte_offset} bytes)"
            )

        writer = _SplitZipWriter(
            temp_archive_base,
            split_size_bytes or 1,
            _print_volume_start,
        )
        try:
            _write_archive(
                writer,
                [
                    (source_path, archive_name_str)
                    for source_path, archive_name_str in entries_to_archive
                ],
                log_entries=True,
            )
        finally:
            writer.close()

        if not writer.volumes:
            raise RuntimeError("multipart ZIP writer did not create any volumes")

        for source_path, archive_name_str in entries_to_archive:
            _record_entry(source_path, archive_name_str)

        published_volumes: list[Path] = []
        for temp_volume in writer.volumes:
            final_path = output_zip.with_name(temp_volume.name)
            _publish_archive(temp_volume, final_path)
            published_volumes.append(final_path)
        return published_volumes

    console.print(f"[cyan]Building ZIP archive[/] {output_zip}")
    temp_root = get_runtime_config_dir() or output_zip.parent
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output_zip.name}.",
        dir=str(temp_root),
    ) as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        if split_size_bytes and split_size_bytes > 0:
            split_spec = _format_zip_split_size_spec(split_size_bytes)
            console.print(f"[cyan]Creating multipart ZIP volumes up to {split_spec}[/]")

            created_archives = _write_multipart_archive(temp_dir)
            console.print(
                f"[green]Created[/] {len(created_archives)} multipart ZIP volume(s)"
            )
            _print_marker(
                "[MARKER_ZIP_CREATED_SUCCESSFULLY]",
                zip_files=[str(path) for path in created_archives],
                files_archived=archived_count,
                entries_archived=len(archived_entries),
            )
            return archived_count, archived_entries, created_archives
        else:
            temp_archive_path = temp_dir / output_zip.name
            console.print(f"[cyan]Writing[/] temporary archive for {output_zip} in {temp_archive_path}")
            _write_archive(
                temp_archive_path,
                [
                    (source_path, archive_name_str)
                    for source_path, archive_name_str in entries_to_archive
                ],
                log_entries=True,
            )
            for source_path, archive_name_str in entries_to_archive:
                _record_entry(source_path, archive_name_str)
            _publish_archive(temp_archive_path, output_zip)
            created_archives = [output_zip]

        console.print(f"[green]Created[/] {len(created_archives)} archive part(s)")
        _print_marker(
            "[MARKER_ZIP_CREATED_SUCCESSFULLY]",
            zip_files=[str(path) for path in created_archives],
            files_archived=archived_count,
            entries_archived=len(archived_entries),
        )
        return archived_count, archived_entries, created_archives


async def _wait_for_stats_create(
    client: Any,
    req_ids: list[str],
    timeout: float = _WS_CONFIRM_TIMEOUT_SEC,
) -> list[str]:
    """Keep the websocket alive until a STATS_CREATE (or STATS_UPDATE) event is
    received for every *req_id* in the list.

    This is the websocket-native replacement for HTTP polling: the backend
    publishes STATS_CREATE the moment it creates the GulpRequestStats object,
    which is the very first thing a worker does.  Receiving that event proves
    the websocket was alive when the backend needed it.

    Returns the list of req_ids that did NOT receive confirmation within *timeout*.
    """
    req_ids = [r for r in req_ids if r]
    if not req_ids:
        return []

    ws = await client.ensure_websocket()

    # One asyncio.Event per req_id; we set it on any STATS_CREATE/STATS_UPDATE
    # message that carries the matching req_id.
    events: dict[str, asyncio.Event] = {req_id: asyncio.Event() for req_id in req_ids}

    async def _on_stats(msg: WSMessage) -> None:
        ev = events.get(msg.req_id)
        if ev is not None:
            ev.set()

    ws.on_message(WSMessageType.STATS_CREATE, _on_stats)
    ws.on_message(WSMessageType.STATS_UPDATE, _on_stats)

    try:
        await asyncio.wait_for(
            asyncio.gather(*[ev.wait() for ev in events.values()]),
            timeout=timeout,
        )
        return []
    except asyncio.TimeoutError:
        return [rid for rid, ev in events.items() if not ev.is_set()]
    finally:
        ws.off_message(WSMessageType.STATS_CREATE, _on_stats)
        ws.off_message(WSMessageType.STATS_UPDATE, _on_stats)


async def _wait_for_completion(
    client: Any,
    file_req_map: dict[str, str],
    timeout: int,
) -> list[dict[str, Any]]:
    """Wait for every ingest request to reach a terminal status via websocket only.

    This function intentionally avoids HTTP polling and relies exclusively on
    websocket packets (STATS_CREATE/STATS_UPDATE/INGEST_SOURCE_DONE/ERROR).

    Returns a list of result dicts (one per file) with final status.
    """

    ws = await client.ensure_websocket()
    req_to_file: dict[str, str] = {
        rid: file_path for file_path, rid in file_req_map.items()
    }

    def _extract_payload_obj(msg: WSMessage) -> dict[str, Any]:
        if not isinstance(msg.data, dict):
            return {}
        obj = msg.data.get("obj")
        if isinstance(obj, dict):
            return obj
        return msg.data

    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _extract_ingest_counters(payload: dict[str, Any]) -> tuple[int, int, int, bool]:
        """Extract ingestion counters from either top-level or nested stats data."""
        nested = payload.get("data")
        nested_data = nested if isinstance(nested, dict) else {}
        has_top = any(
            key in payload
            for key in ("records_ingested", "records_skipped", "records_failed")
        )
        has_nested = any(
            key in nested_data
            for key in ("records_ingested", "records_skipped", "records_failed")
        )
        ingested = _to_int(payload.get("records_ingested"))
        skipped = _to_int(payload.get("records_skipped"))
        failed = _to_int(payload.get("records_failed"))

        # GulpRequestStats packets usually keep ingestion counters in obj.data.
        ingested = max(ingested, _to_int(nested_data.get("records_ingested")))
        skipped = max(skipped, _to_int(nested_data.get("records_skipped")))
        failed = max(failed, _to_int(nested_data.get("records_failed")))
        return ingested, skipped, failed, (has_top or has_nested)

    def _status_label(status: str, ingested: int, skipped: int, failed: int) -> str:
        return f"{status}: ingested={ingested}, skipped={skipped}, failed={failed}"

    states: dict[str, dict[str, Any]] = {
        req_id: {
            "status": "ongoing",
            "ingested": 0,
            "skipped": 0,
            "failed": 0,
            "stats": {},
            "event": asyncio.Event(),
        }
        for req_id in file_req_map.values()
        if req_id
    }

    results: list[dict[str, Any]] = []
    # Rich progress bar: one task per file
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_ids: dict[str, Any] = {}
        for file_path, req_id in file_req_map.items():
            sid_tag = escape(f"[{req_id[:8]}]")
            task_ids[req_id] = progress.add_task(
                f"{sid_tag} {Path(file_path).name}", total=None
            )

        def _on_message(msg: WSMessage) -> None:
            req_id = msg.req_id
            state = states.get(req_id)
            if state is None:
                return

            tid = task_ids.get(req_id)
            if tid is None:
                return

            file_name = Path(req_to_file.get(req_id, req_id)).name
            sid_tag = escape(f"[{req_id[:8]}]")
            obj = _extract_payload_obj(msg)

            if msg.type == WSMessageType.INGEST_SOURCE_DONE.value:
                done_ingested, done_skipped, done_failed, _ = _extract_ingest_counters(
                    obj
                )
                state["ingested"] += done_ingested
                state["skipped"] += done_skipped
                state["failed"] += done_failed
                state.setdefault("sources_done", 0)
                state["sources_done"] += 1
                progress.update(
                    tid,
                    description=(
                        f"{sid_tag} {file_name} (running: ingested={state['ingested']}, "
                        f"skipped={state['skipped']}, failed={state['failed']})"
                    ),
                )
                return

            if msg.type in (
                WSMessageType.STATS_CREATE.value,
                WSMessageType.STATS_UPDATE.value,
            ):
                state["stats"] = obj
                status = str(obj.get("status", state["status"]))
                pct = obj.get("ingest_percentage")
                if pct is not None:
                    progress.update(tid, completed=pct, total=100)

                # Request stats counters are authoritative snapshots.
                stats_ingested, stats_skipped, stats_failed, has_stats_counters = (
                    _extract_ingest_counters(obj)
                )
                if has_stats_counters:
                    state["ingested"] = stats_ingested
                    state["skipped"] = stats_skipped
                    state["failed"] = stats_failed

                state["status"] = status
                if status in _TERMINAL_STATUSES:
                    progress.update(
                        tid,
                        completed=100,
                        total=100,
                        description=f"{sid_tag} {file_name} ({_status_label(status, state['ingested'], state['skipped'], state['failed'])})",
                    )
                    state["event"].set()
                return

            if msg.type == WSMessageType.ERROR.value:
                state["status"] = "failed"
                state["stats"] = obj
                progress.update(
                    tid,
                    completed=100,
                    total=100,
                    description=f"{sid_tag} {file_name} ({_status_label('failed', state['ingested'], state['skipped'], state['failed'])})",
                )
                state["event"].set()

        ws.on_message(WSMessageType.INGEST_SOURCE_DONE, _on_message)
        ws.on_message(WSMessageType.STATS_CREATE, _on_message)
        ws.on_message(WSMessageType.STATS_UPDATE, _on_message)
        ws.on_message(WSMessageType.ERROR, _on_message)

        deadline = None if timeout == 0 else asyncio.get_running_loop().time() + timeout
        try:
            for req_id, state in states.items():
                if deadline is None:
                    await state["event"].wait()
                else:
                    remaining = max(0.0, deadline - asyncio.get_running_loop().time())
                    if remaining == 0.0 and not state["event"].is_set():
                        continue
                    try:
                        await asyncio.wait_for(state["event"].wait(), timeout=remaining)
                    except asyncio.TimeoutError:
                        pass
        finally:
            ws.off_message(WSMessageType.INGEST_SOURCE_DONE, _on_message)
            ws.off_message(WSMessageType.STATS_CREATE, _on_message)
            ws.off_message(WSMessageType.STATS_UPDATE, _on_message)
            ws.off_message(WSMessageType.ERROR, _on_message)

        for file_path, req_id in file_req_map.items():
            tid = task_ids.get(req_id)
            state = states.get(req_id)
            sid_tag = escape(f"[{req_id[:8]}]")

            if tid is not None:
                try:
                    if state and state.get("status") in _TERMINAL_STATUSES:
                        status = str(state.get("status"))
                        progress.update(
                            tid,
                            completed=100,
                            total=100,
                            description=(
                                f"{sid_tag} {Path(file_path).name} ("
                                f"{_status_label(status, state.get('ingested', 0), state.get('skipped', 0), state.get('failed', 0))}"
                                ")"
                            ),
                        )
                    elif state and not state.get("event").is_set():
                        progress.update(
                            tid,
                            description=(
                                f"{sid_tag} {Path(file_path).name} (timeout: ingested={state.get('ingested', 0)}, "
                                f"skipped={state.get('skipped', 0)}, failed={state.get('failed', 0)})"
                            ),
                        )
                except Exception:
                    pass

            if state is None:
                results.append(
                    {"file": file_path, "req_id": req_id, "status": "unknown"}
                )
            elif get_runtime_verbose():
                results.append(
                    {
                        "file": file_path,
                        "req_id": req_id,
                        "status": state.get("status", "unknown"),
                        "ingested": state.get("ingested", 0),
                        "skipped": state.get("skipped", 0),
                        "failed": state.get("failed", 0),
                        "result": state.get("stats", {}),
                        "ws_only": True,
                    }
                )
            else:
                results.append(
                    {
                        "file": file_path,
                        "req_id": req_id,
                        "status": state.get("status", "unknown"),
                        "ingested": state.get("ingested", 0),
                        "skipped": state.get("skipped", 0),
                        "failed": state.get("failed", 0),
                    }
                )

    return results


class _IngestWsTracker:
    """Track ingest websocket events with persistent listeners for the whole run."""

    def __init__(
        self,
        ws: Any,
        *,
        source_done_is_terminal: bool = False,
        log_updates: bool = False,
        request_label_getter: Callable[[str], str] | None = None,
        request_status_fetcher: (
            Callable[[str], Awaitable[dict[str, Any] | None]] | None
        ) = None,
    ) -> None:
        self._ws = ws
        self._source_done_is_terminal = source_done_is_terminal
        self._log_updates = log_updates
        self._request_label_getter = request_label_getter or (lambda req_id: req_id)
        self._request_status_fetcher = request_status_fetcher
        self._states: dict[str, dict[str, Any]] = {}
        self._confirm_events: dict[str, asyncio.Event] = {}
        self._terminal_events: dict[str, asyncio.Event] = {}

        self._ws.on_message(WSMessageType.INGEST_SOURCE_DONE, self._on_message)
        self._ws.on_message(WSMessageType.STATS_CREATE, self._on_message)
        self._ws.on_message(WSMessageType.STATS_UPDATE, self._on_message)
        self._ws.on_message(WSMessageType.ERROR, self._on_message)

    @classmethod
    async def create(
        cls,
        client: Any,
        *,
        source_done_is_terminal: bool = False,
        log_updates: bool = False,
        request_label_getter: Callable[[str], str] | None = None,
        request_status_fetcher: (
            Callable[[str], Awaitable[dict[str, Any] | None]] | None
        ) = None,
    ) -> "_IngestWsTracker":
        ws = await client.ensure_websocket()
        return cls(
            ws,
            source_done_is_terminal=source_done_is_terminal,
            log_updates=log_updates,
            request_label_getter=request_label_getter,
            request_status_fetcher=request_status_fetcher,
        )

    def close(self) -> None:
        self._ws.off_message(WSMessageType.INGEST_SOURCE_DONE, self._on_message)
        self._ws.off_message(WSMessageType.STATS_CREATE, self._on_message)
        self._ws.off_message(WSMessageType.STATS_UPDATE, self._on_message)
        self._ws.off_message(WSMessageType.ERROR, self._on_message)

    def _state(self, req_id: str) -> dict[str, Any]:
        if req_id not in self._states:
            self._states[req_id] = {
                "status": "ongoing",
                "ingested": 0,
                "skipped": 0,
                "failed": 0,
                "stats": {},
                "seen_confirm": False,
            }
        return self._states[req_id]

    def _request_label(self, req_id: str) -> str:
        label = self._request_label_getter(req_id)
        return Path(label).name or label or req_id

    @staticmethod
    def _extract_payload_obj(msg: WSMessage) -> dict[str, Any]:
        if not isinstance(msg.data, dict):
            return {}
        obj = msg.data.get("obj")
        if isinstance(obj, dict):
            return obj
        return msg.data

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _extract_ingest_counters(
        cls, payload: dict[str, Any]
    ) -> tuple[int, int, int, bool]:
        nested = payload.get("data")
        nested_data = nested if isinstance(nested, dict) else {}
        has_top = any(
            key in payload
            for key in ("records_ingested", "records_skipped", "records_failed")
        )
        has_nested = any(
            key in nested_data
            for key in ("records_ingested", "records_skipped", "records_failed")
        )
        ingested = cls._to_int(payload.get("records_ingested"))
        skipped = cls._to_int(payload.get("records_skipped"))
        failed = cls._to_int(payload.get("records_failed"))
        ingested = max(ingested, cls._to_int(nested_data.get("records_ingested")))
        skipped = max(skipped, cls._to_int(nested_data.get("records_skipped")))
        failed = max(failed, cls._to_int(nested_data.get("records_failed")))
        return ingested, skipped, failed, (has_top or has_nested)

    def _on_message(self, msg: WSMessage) -> None:
        req_id = msg.req_id
        if not req_id:
            return

        state = self._state(req_id)
        obj = self._extract_payload_obj(msg)

        if msg.type == WSMessageType.INGEST_SOURCE_DONE.value:
            done_ingested, done_skipped, done_failed, _ = self._extract_ingest_counters(
                obj
            )
            state["ingested"] += done_ingested
            state["skipped"] += done_skipped
            state["failed"] += done_failed
            source_status = str(obj.get("status", state["status"]))
            state["status"] = source_status
            if (
                self._source_done_is_terminal
                and source_status not in _TERMINAL_STATUSES
            ):
                state["seen_confirm"] = True

                confirm_ev = self._confirm_events.get(req_id)
                if confirm_ev is not None:
                    confirm_ev.set()

                terminal_ev = self._terminal_events.get(req_id)
                if terminal_ev is not None:
                    terminal_ev.set()
            if self._log_updates:
                _print_marker(
                    "[MARKER_INGEST_SOURCE_DONE_RECEIVED]",
                    req_id=req_id,
                    file=self._request_label(req_id),
                    status=source_status,
                    ingested=state.get("ingested", 0),
                    skipped=state.get("skipped", 0),
                    failed=state.get("failed", 0),
                    errors=_extract_errors(obj),
                )
                console.print(
                    _format_per_file_log_line(
                        {
                            "event": msg.type,
                            "req_id": req_id,
                            "file": self._request_label(req_id),
                            "status": source_status,
                            "ingested": state.get("ingested", 0),
                            "skipped": state.get("skipped", 0),
                            "failed": state.get("failed", 0),
                            "errors": _extract_errors(obj),
                        }
                    )
                )
            return

        if msg.type in (
            WSMessageType.STATS_CREATE.value,
            WSMessageType.STATS_UPDATE.value,
        ):
            state["seen_confirm"] = True
            state["stats"] = obj
            status = str(obj.get("status", state["status"]))
            stats_ingested, stats_skipped, stats_failed, has_stats_counters = (
                self._extract_ingest_counters(obj)
            )
            if has_stats_counters:
                state["ingested"] = stats_ingested
                state["skipped"] = stats_skipped
                state["failed"] = stats_failed
            state["status"] = status

            confirm_ev = self._confirm_events.get(req_id)
            if confirm_ev is not None:
                confirm_ev.set()

            if status in _TERMINAL_STATUSES:
                terminal_ev = self._terminal_events.get(req_id)
                if terminal_ev is not None:
                    terminal_ev.set()
            if self._log_updates:
                if status == "done":
                    marker = "[MARKER_DONE_STATS_RECEIVED]"
                elif status in {"failed", "canceled"}:
                    marker = "[MARKER_FAILED_STATS_RECEIVED]"
                else:
                    marker = "[MARKER_ONGOING_STATS_RECEIVED]"
                _print_marker(
                    marker,
                    req_id=req_id,
                    file=self._request_label(req_id),
                    event=msg.type,
                    status=state["status"],
                    ingested=state["ingested"],
                    skipped=state["skipped"],
                    failed=state["failed"],
                    pct=obj.get("ingest_percentage"),
                    errors=_extract_errors(obj),
                )
                console.print(
                    _format_per_file_log_line(
                        {
                            "event": msg.type,
                            "req_id": req_id,
                            "file": self._request_label(req_id),
                            "status": state["status"],
                            "ingested": state["ingested"],
                            "skipped": state["skipped"],
                            "failed": state["failed"],
                            "pct": obj.get("ingest_percentage"),
                            "errors": _extract_errors(obj),
                        }
                    )
                )
            return

        if msg.type == WSMessageType.ERROR.value:
            state["status"] = "failed"
            state["stats"] = obj
            terminal_ev = self._terminal_events.get(req_id)
            if terminal_ev is not None:
                terminal_ev.set()
            if self._log_updates:
                _print_marker(
                    "[MARKER_BACKEND_EXCEPTION_REPORTED]",
                    req_id=req_id,
                    file=self._request_label(req_id),
                    event=msg.type,
                    status=state["status"],
                    errors=_extract_errors(obj),
                )
                _print_marker(
                    "[MARKER_FAILED_STATS_RECEIVED]",
                    req_id=req_id,
                    file=self._request_label(req_id),
                    event=msg.type,
                    status=state["status"],
                    ingested=state["ingested"],
                    skipped=state["skipped"],
                    failed=state["failed"],
                    errors=_extract_errors(obj),
                )
                console.print(
                    _format_per_file_log_line(
                        {
                            "event": msg.type,
                            "req_id": req_id,
                            "file": self._request_label(req_id),
                            "status": state["status"],
                            "ingested": state["ingested"],
                            "skipped": state["skipped"],
                            "failed": state["failed"],
                            "errors": _extract_errors(obj),
                        }
                    )
                )

    async def wait_for_confirm(self, req_id: str, timeout: float) -> bool:
        """Return True if timed out waiting for STATS_CREATE/UPDATE for req_id."""
        if not req_id:
            return False

        state = self._state(req_id)
        if state.get("seen_confirm"):
            return False

        ev = self._confirm_events.get(req_id)
        if ev is None:
            ev = asyncio.Event()
            self._confirm_events[req_id] = ev

        if timeout == 0:
            await ev.wait()
            return False

        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
            return False
        except asyncio.TimeoutError:
            return True

    async def wait_for_terminal(
        self,
        file_path: str,
        req_id: str,
        timeout: int,
    ) -> dict[str, Any]:
        if not req_id:
            return {
                "file": file_path,
                "req_id": req_id,
                "status": "unknown",
                "ingested": 0,
                "skipped": 0,
                "failed": 0,
                "result": {},
                "timed_out": False,
            }

        state = self._state(req_id)
        timed_out = False

        if state.get("status") not in _TERMINAL_STATUSES:
            ev = self._terminal_events.get(req_id)
            if ev is None:
                ev = asyncio.Event()
                self._terminal_events[req_id] = ev

            deadline = (
                None if timeout == 0 else asyncio.get_running_loop().time() + timeout
            )
            while state.get("status") not in _TERMINAL_STATUSES:
                remaining = (
                    None
                    if deadline is None
                    else max(0.0, deadline - asyncio.get_running_loop().time())
                )
                if remaining is not None and remaining == 0.0:
                    timed_out = True
                    state["status"] = "timeout"
                    break

                wait_slice = 10.0 if remaining is None else min(10.0, remaining)
                try:
                    await asyncio.wait_for(ev.wait(), timeout=wait_slice)
                    if state.get("status") in _TERMINAL_STATUSES:
                        break
                    ev.clear()
                    continue
                except asyncio.TimeoutError:
                    # Fallback: poll current request status in case websocket terminal
                    # notifications are delayed or missed under high load.
                    if self._request_status_fetcher is not None:
                        try:
                            data = await self._request_status_fetcher(req_id)
                        except Exception:
                            data = None

                        if isinstance(data, dict):
                            polled_status = str(data.get("status", state["status"]))
                            state["stats"] = data
                            state["status"] = polled_status

                            ing = data.get("records_ingested")
                            skp = data.get("records_skipped")
                            fld = data.get("records_failed")
                            if ing is not None:
                                state["ingested"] = self._to_int(ing)
                            if skp is not None:
                                state["skipped"] = self._to_int(skp)
                            if fld is not None:
                                state["failed"] = self._to_int(fld)

                            if polled_status in _TERMINAL_STATUSES:
                                state["seen_confirm"] = True
                                confirm_ev = self._confirm_events.get(req_id)
                                if confirm_ev is not None:
                                    confirm_ev.set()
                                ev.set()
                                break

        return _with_failed_errors({
            "file": file_path,
            "req_id": req_id,
            "status": state.get("status", "unknown"),
            "ingested": state.get("ingested", 0),
            "skipped": state.get("skipped", 0),
            "failed": state.get("failed", 0),
            "result": state.get("stats", {}),
            "timed_out": timed_out,
        })


@app.command("file")
def ingest_file(
    operation_id: str,
    plugin: str,
    file_patterns: list[str] | None = typer.Argument(
        None,
        help="One or more files or glob patterns; optional when --paths-file is set",
    ),
    paths_file: str | None = typer.Option(
        None,
        "--paths-file",
        help="Text file with one file or glob pattern per line; positional patterns become optional",
    ),
    context_name: str = typer.Option(
        "sdk_context",
        "--context",
        help="Context for ingestion, specify a name to create a new context if it doesn't exist, or an existing `context_id`.",
    ),
    plugin_params: str | None = typer.Option(
        None, "--plugin-params", help="JSON object for plugin_params"
    ),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpIngestionFilter"
    ),
    reset_operation: bool = typer.Option(
        False,
        "--reset-operation",
        help="Delete and recreate the operation before ingest starts",
    ),
    create_operation_if_missing: bool = typer.Option(
        False,
        "--create-operation",
        help="Create operation automatically when it does not exist",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Run ingestion preview (no persistence) and return preview payload",
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        help=(
            "Wait for all ingestions to complete (WS-driven progress bar). "
            "Without this flag the CLI returns as soon as the backend confirms "
            "reception of each request via STATS_CREATE websocket event."
        ),
    ),
    wait_log: bool = typer.Option(
        False,
        "--wait-log",
        help=(
            "Wait for all ingestions to complete and print websocket updates "
            "to stdout as they arrive."
        ),
    ),
    wait_timeout: int = typer.Option(
        300,
        "--timeout",
        help="Seconds to wait for completion (only used with --wait/--wait-log)",
    ),
    show_per_file_progress: bool = typer.Option(
        True,
        "--show-per-file-progress/--no-show-per-file-progress",
        help="In --wait mode, print one line for each completed file request.",
    ),
    batch_size: int = typer.Option(
        _default_ingest_batch_size(),
        "--batch-size",
        min=1,
        help="Number of file ingestion requests to submit concurrently per batch (default: cores*2).",
    ),
) -> None:
    """Ingest one or more files (supports glob patterns).

    By default the command returns once the backend has confirmed every request
    via a STATS_CREATE websocket notification — no HTTP polling.  Pass --wait
    to block until ingestion fully completes, with a live progress bar, or
    --wait-log to stream websocket updates as they arrive.
    """

    unique_files = [
        str(path)
        for path, _base_dir in _expand_source_patterns(file_patterns or [], paths_file)
    ]

    if not unique_files:
        print_error("No files found matching the provided patterns.")
        raise typer.Exit(1)

    # ------------------------------------------------------------------ #
    # Async runner                                                         #
    # ------------------------------------------------------------------ #
    async def _run() -> None:
        if preview and wait:
            raise typer.BadParameter("--preview and --wait are mutually exclusive")
        if preview and wait_log:
            raise typer.BadParameter("--preview and --wait-log are mutually exclusive")
        if preview and reset_operation:
            raise typer.BadParameter(
                "--preview and --reset-operation are mutually exclusive"
            )
        if wait and wait_log:
            raise typer.BadParameter("--wait and --wait-log are mutually exclusive")
        if reset_operation and create_operation_if_missing:
            raise typer.BadParameter(
                "--reset-operation and --create-operation are mutually exclusive"
            )
        wait_mode = wait or wait_log

        async with get_client() as client:
            # Establish WS BEFORE any ingest call so ws_id is live when the
            # worker tries to publish its first STATS_CREATE event.
            await client.ensure_websocket()

            async def _fetch_request_status(req_id: str) -> dict[str, Any] | None:
                try:
                    resp = await client._request(
                        "GET", "/request_get_by_id", params={"obj_id": req_id}
                    )
                except Exception:
                    return None
                data = resp.get("data")
                return data if isinstance(data, dict) else None

            req_to_file: dict[str, str] = {}
            tracker = await _IngestWsTracker.create(
                client,
                source_done_is_terminal=True,
                log_updates=wait_log,
                request_label_getter=lambda req_id: req_to_file.get(req_id, req_id),
                request_status_fetcher=_fetch_request_status,
            )

            params = {
                "plugin_params": parse_json_option(
                    plugin_params, field_name="plugin-params"
                )
                or {},
                "flt": parse_json_option(flt, field_name="flt") or {},
            }

            if preview:
                previews: list[dict[str, Any]] = []
                for file_path in unique_files:
                    upload_path, temp_path = await _maybe_bz2_compress_file_for_ingestion(
                        file_path, params["plugin_params"]
                    )
                    try:
                        data = await client.ingest.preview(
                            operation_id=operation_id,
                            plugin_name=plugin,
                            file_path=upload_path,
                            params={
                                "context_name": context_name,
                                "plugin_params": params["plugin_params"],
                                "flt": params["flt"],
                                "original_file_path": str(Path(file_path).resolve()),
                            },
                        )
                    finally:
                        if temp_path:
                            Path(temp_path).unlink(missing_ok=True)
                    previews.append({"file": file_path, "preview": data})
                print_result(previews)
                return

            if reset_operation:
                try:
                    await client.operations.delete(operation_id, force=True)
                except NotFoundError:
                    pass
                op = await client.operations.create(name=operation_id)
                if not get_runtime_verbose():
                    print_warning(
                        f"Operation {operation_id} reset (deleted and recreated)."
                    )
            else:
                await _ensure_operation_exists(
                    client,
                    operation_id,
                    create_if_missing=create_operation_if_missing,
                )

            async def _fire_one(file_path: str) -> tuple[str, str, dict[str, Any]]:
                """Submit ingestion for one file; returns (file_path, req_id, submission)."""
                req_id = str(uuid.uuid4())
                req_to_file[req_id] = file_path
                upload_path, temp_path = await _maybe_bz2_compress_file_for_ingestion(
                    file_path, params["plugin_params"]
                )
                try:
                    result = await client.ingest.file(
                        operation_id=operation_id,
                        plugin_name=plugin,
                        file_path=upload_path,
                        context_name=context_name,
                        params={
                            **params,
                            "original_file_path": str(Path(file_path).resolve()),
                            "req_id": req_id,
                        },
                        wait=False,  # we handle waiting ourselves below
                    )
                finally:
                    if temp_path:
                        Path(temp_path).unlink(missing_ok=True)
                if hasattr(result, "model_dump"):
                    submission = result.model_dump(exclude_none=True)
                else:
                    submission = {"req_id": getattr(result, "req_id", None)}
                req_id = str(submission.get("req_id") or req_id)
                if req_id:
                    req_to_file[req_id] = file_path
                return file_path, req_id, submission

            # Sliding window dispatcher: keep up to batch_size requests in flight.
            file_req_map: dict[str, str] = {}
            fired_meta: dict[str, dict[str, Any]] = {}
            timed_out_req_ids: set[str] = set()
            completed_by_file: dict[str, dict[str, Any]] = {}
            file_iter = iter(unique_files)
            in_flight: set[
                asyncio.Task[
                    tuple[str, str, dict[str, Any], dict[str, Any] | None, bool]
                ]
            ] = set()

            async def _submit_and_gate(
                file_path: str,
            ) -> tuple[str, str, dict[str, Any], dict[str, Any] | None, bool]:
                fpath, req_id, submission = await _fire_one(file_path)
                if wait_mode:
                    waited = await tracker.wait_for_terminal(
                        fpath, req_id, wait_timeout
                    )
                    return fpath, req_id, submission, waited, False

                timed_out = await tracker.wait_for_confirm(
                    req_id, _WS_CONFIRM_TIMEOUT_SEC
                )
                return fpath, req_id, submission, None, timed_out

            def _schedule_next() -> bool:
                try:
                    next_file = next(file_iter)
                except StopIteration:
                    return False

                in_flight.add(asyncio.create_task(_submit_and_gate(next_file)))
                return True

            try:
                progress = None
                progress_task_id = None
                completed_count = 0
                if wait:
                    progress = Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        TimeElapsedColumn(),
                        console=console,
                        transient=True,
                    )
                    progress.__enter__()
                    progress_task_id = progress.add_task(
                        "ingesting files", total=len(unique_files)
                    )

                for _ in range(min(batch_size, len(unique_files))):
                    _schedule_next()

                while in_flight:
                    done, pending = await asyncio.wait(
                        in_flight, return_when=asyncio.FIRST_COMPLETED
                    )
                    in_flight = pending

                    for done_task in done:
                        file_path, req_id, submission, waited, timed_out = (
                            await done_task
                        )
                        file_req_map[file_path] = req_id
                        if req_id:
                            fired_meta[req_id] = submission
                        if timed_out and req_id:
                            timed_out_req_ids.add(req_id)
                        if waited is not None:
                            completed_by_file[file_path] = waited
                            completed_count += 1
                            if show_per_file_progress:
                                console.print(_format_per_file_progress_line(waited))
                            if progress is not None and progress_task_id is not None:
                                progress.update(
                                    progress_task_id,
                                    advance=1,
                                    description=(
                                        f"ingesting files (done={completed_count}/{len(unique_files)}, "
                                        f"running={len(in_flight)})"
                                    ),
                                )

                        _schedule_next()
            finally:
                if wait and progress is not None:
                    progress.__exit__(None, None, None)
                tracker.close()

            if wait_mode:
                results = [
                    completed_by_file.get(
                        fp,
                        {
                            "file": fp,
                            "req_id": file_req_map.get(fp, ""),
                            "status": "unknown",
                            "ingested": 0,
                            "skipped": 0,
                            "failed": 0,
                            "result": {},
                            "timed_out": False,
                        },
                    )
                    for fp in unique_files
                ]
                if not get_runtime_verbose():
                    results = [
                        {
                            "file": item.get("file"),
                            "req_id": item.get("req_id"),
                            "status": item.get("status", "unknown"),
                            "ingested": item.get("ingested", 0),
                            "skipped": item.get("skipped", 0),
                            "failed": item.get("failed", 0),
                            **({"errors": item["errors"]} if item.get("errors") else {}),
                        }
                        for item in results
                    ]
                else:
                    results = [
                        {
                            "file": item.get("file"),
                            "req_id": item.get("req_id"),
                            "status": item.get("status", "unknown"),
                            "ingested": item.get("ingested", 0),
                            "skipped": item.get("skipped", 0),
                            "failed": item.get("failed", 0),
                            "result": item.get("result", {}),
                            "ws_only": True,
                        }
                        for item in results
                    ]
            else:
                timed_out_set = set(timed_out_req_ids)
                if timed_out_set and not get_runtime_verbose():
                    print_warning(
                        f"{len(timed_out_set)} request(s) did not receive STATS_CREATE "
                        f"within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s — backend may still be processing: "
                        + ", ".join(sorted(timed_out_set))
                    )
                if get_runtime_verbose():
                    results = [
                        {
                            "file": fp,
                            "req_id": rid,
                            "submitted": fired_meta.get(rid, {"req_id": rid}),
                            "ws_confirmed": rid not in timed_out_set,
                        }
                        for fp, rid in file_req_map.items()
                    ]
                else:
                    results = [
                        {"file": fp, "req_id": rid, "status": "pending"}
                        for fp, rid in file_req_map.items()
                    ]

            if wait_log:
                _print_ingestion_finished_marker(results)
            print_result(results)

    asyncio.run(_run())


@app.command("file-to-source")
def ingest_file_to_source(
    source_id: str,
    file_patterns: list[str] | None = typer.Argument(
        None,
        help="One or more files or glob patterns; optional when --paths-file is set",
    ),
    paths_file: str | None = typer.Option(
        None,
        "--paths-file",
        help="Text file with one file or glob pattern per line; positional patterns become optional",
    ),
    plugin: str | None = typer.Option(
        None,
        "--plugin",
        help="Override the plugin associated with the source (requires --plugin-params).",
    ),
    plugin_params: str | None = typer.Option(
        None,
        "--plugin-params",
        help="JSON object for plugin_params (overrides source defaults; required with --plugin, {} is allowed)",
    ),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpIngestionFilter"
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        help=(
            "Wait for all ingestions to complete (WS-driven progress bar). "
            "Without this flag the CLI returns as soon as the backend confirms "
            "reception of each request via STATS_CREATE websocket event."
        ),
    ),
    wait_log: bool = typer.Option(
        False,
        "--wait-log",
        help=(
            "Wait for all ingestions to complete and print websocket updates "
            "to stdout as they arrive."
        ),
    ),
    wait_timeout: int = typer.Option(
        300,
        "--timeout",
        help="Seconds to wait for completion (only used with --wait/--wait-log)",
    ),
    show_per_file_progress: bool = typer.Option(
        True,
        "--show-per-file-progress/--no-show-per-file-progress",
        help="In --wait mode, print one line for each completed file request.",
    ),
    batch_size: int = typer.Option(
        _default_ingest_batch_size(),
        "--batch-size",
        min=1,
        help="Number of file ingestion requests to submit concurrently per batch (default: cores*2).",
    ),
) -> None:
    """Ingest one or more files into an existing source."""

    unique_files = [
        str(path)
        for path, _base_dir in _expand_source_patterns(file_patterns or [], paths_file)
    ]
    if not unique_files:
        print_error("No files found matching the provided patterns.")
        raise typer.Exit(1)

    async def _run() -> None:
        if wait and wait_log:
            raise typer.BadParameter("--wait and --wait-log are mutually exclusive")
        if plugin and plugin_params is None:
            raise typer.BadParameter("--plugin requires --plugin-params")

        async with get_client() as client:
            await client.ensure_websocket()

            async def _fetch_request_status(req_id: str) -> dict[str, Any] | None:
                try:
                    resp = await client._request(
                        "GET", "/request_get_by_id", params={"obj_id": req_id}
                    )
                except Exception:
                    return None
                data = resp.get("data")
                return data if isinstance(data, dict) else None

            tracker = await _IngestWsTracker.create(
                client,
                source_done_is_terminal=True,
                log_updates=wait_log,
                request_label_getter=lambda req_id: req_to_file.get(req_id, req_id),
                request_status_fetcher=_fetch_request_status,
            )

            params = {
                "plugin_params": parse_json_option(
                    plugin_params, field_name="plugin-params"
                )
                or {},
                "flt": parse_json_option(flt, field_name="flt") or {},
            }

            req_to_file: dict[str, str] = {}

            async def _fire_one(file_path: str) -> tuple[str, str, dict[str, Any]]:
                req_id = str(uuid.uuid4())
                req_to_file[req_id] = file_path
                upload_path, temp_path = await _maybe_bz2_compress_file_for_ingestion(
                    file_path, params["plugin_params"]
                )
                try:
                    result = await client.ingest.file_to_source(
                        source_id=source_id,
                        file_path=upload_path,
                        plugin=plugin,
                        plugin_params=(
                            params["plugin_params"]
                            if plugin is not None
                            else params["plugin_params"] or None
                        ),
                        flt=params["flt"] or None,
                        req_id=req_id,
                        original_file_path=str(Path(file_path).resolve()),
                        wait=False,
                    )
                finally:
                    if temp_path:
                        Path(temp_path).unlink(missing_ok=True)
                if hasattr(result, "model_dump"):
                    submission = result.model_dump(exclude_none=True)
                else:
                    submission = {"req_id": getattr(result, "req_id", None)}
                req_id = str(submission.get("req_id") or req_id)
                if req_id:
                    req_to_file[req_id] = file_path
                return file_path, req_id, submission

            file_req_map: dict[str, str] = {}
            fired_meta: dict[str, dict[str, Any]] = {}
            timed_out_req_ids: set[str] = set()
            completed_by_file: dict[str, dict[str, Any]] = {}
            file_iter = iter(unique_files)
            in_flight: set[
                asyncio.Task[
                    tuple[str, str, dict[str, Any], dict[str, Any] | None, bool]
                ]
            ] = set()
            wait_mode = wait or wait_log

            async def _submit_and_gate(
                file_path: str,
            ) -> tuple[str, str, dict[str, Any], dict[str, Any] | None, bool]:
                fpath, req_id, submission = await _fire_one(file_path)
                if wait_mode:
                    waited = await tracker.wait_for_terminal(
                        fpath, req_id, wait_timeout
                    )
                    return fpath, req_id, submission, waited, False

                timed_out = await tracker.wait_for_confirm(
                    req_id, _WS_CONFIRM_TIMEOUT_SEC
                )
                return fpath, req_id, submission, None, timed_out

            def _schedule_next() -> bool:
                try:
                    next_file = next(file_iter)
                except StopIteration:
                    return False

                in_flight.add(asyncio.create_task(_submit_and_gate(next_file)))
                return True

            try:
                progress = None
                progress_task_id = None
                completed_count = 0
                if wait:
                    progress = Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        TimeElapsedColumn(),
                        console=console,
                        transient=True,
                    )
                    progress.__enter__()
                    progress_task_id = progress.add_task(
                        "ingesting files", total=len(unique_files)
                    )

                for _ in range(min(batch_size, len(unique_files))):
                    _schedule_next()

                while in_flight:
                    done, pending = await asyncio.wait(
                        in_flight, return_when=asyncio.FIRST_COMPLETED
                    )
                    in_flight = pending

                    for done_task in done:
                        file_path, req_id, submission, waited, timed_out = (
                            await done_task
                        )
                        file_req_map[file_path] = req_id
                        if req_id:
                            fired_meta[req_id] = submission
                        if timed_out and req_id:
                            timed_out_req_ids.add(req_id)
                        if waited is not None:
                            completed_by_file[file_path] = waited
                            completed_count += 1
                            if show_per_file_progress:
                                console.print(_format_per_file_progress_line(waited))
                            if progress is not None and progress_task_id is not None:
                                progress.update(
                                    progress_task_id,
                                    advance=1,
                                    description=(
                                        f"ingesting files (done={completed_count}/{len(unique_files)}, "
                                        f"running={len(in_flight)})"
                                    ),
                                )

                        _schedule_next()
            finally:
                if wait and progress is not None:
                    progress.__exit__(None, None, None)
                tracker.close()

            if wait_mode:
                results = [
                    completed_by_file.get(
                        fp,
                        {
                            "file": fp,
                            "req_id": file_req_map.get(fp, ""),
                            "status": "unknown",
                            "ingested": 0,
                            "skipped": 0,
                            "failed": 0,
                            "result": {},
                            "timed_out": False,
                        },
                    )
                    for fp in unique_files
                ]
                if not get_runtime_verbose():
                    results = [
                        {
                            "file": item.get("file"),
                            "req_id": item.get("req_id"),
                            "status": item.get("status", "unknown"),
                            "ingested": item.get("ingested", 0),
                            "skipped": item.get("skipped", 0),
                            "failed": item.get("failed", 0),
                            **({"errors": item["errors"]} if item.get("errors") else {}),
                        }
                        for item in results
                    ]
                else:
                    results = [
                        {
                            "file": item.get("file"),
                            "req_id": item.get("req_id"),
                            "status": item.get("status", "unknown"),
                            "ingested": item.get("ingested", 0),
                            "skipped": item.get("skipped", 0),
                            "failed": item.get("failed", 0),
                            "result": item.get("result", {}),
                            "ws_only": True,
                        }
                        for item in results
                    ]
            else:
                timed_out_set = set(timed_out_req_ids)
                if timed_out_set and not get_runtime_verbose():
                    print_warning(
                        f"{len(timed_out_set)} request(s) did not receive STATS_CREATE "
                        f"within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s - backend may still be processing: "
                        + ", ".join(sorted(timed_out_set))
                    )
                if get_runtime_verbose():
                    results = [
                        {
                            "file": fp,
                            "req_id": rid,
                            "submitted": fired_meta.get(rid, {"req_id": rid}),
                            "ws_confirmed": rid not in timed_out_set,
                        }
                        for fp, rid in file_req_map.items()
                    ]
                else:
                    results = [
                        {"file": fp, "req_id": rid, "status": "pending"}
                        for fp, rid in file_req_map.items()
                    ]

            if wait_log:
                _print_ingestion_finished_marker(results)
            print_result(results)

    asyncio.run(_run())


@app.command("zip-create")
def ingest_zip_create(
    output_zip: str = typer.Argument(
        ...,
        help="Path to the ZIP file to create (supports $VARS and ~)",
    ),
    path_patterns: list[str] = typer.Argument(
        None,
        help="One or more files, directories, or glob patterns to archive (supports $VARS and ~)",
    ),
    paths_file: str | None = typer.Option(
        None,
        "--paths-file",
        help="Text file with one file, directory, or glob pattern per line (supports $VARS and ~ per line)",
    ),
    no_overwrite: bool = typer.Option(
        False,
        "--no-overwrite",
        help="Do not overwrite the ZIP file if it already exists",
    ),
    no_preserve_path: bool = typer.Option(
        False,
        "--no-preserve-path",
        help="Do not preserve the source path hierarchy inside the archive entries",
    ),
    split_size: str | None = typer.Option(
        None,
        "--split-size",
        help="Create multipart ZIP volumes at this size (bytes, kb, mb, gb; default: disabled)",
    ),
) -> None:
    """Create a ZIP archive from files, directories, or glob patterns."""

    try:
        overwrite = not no_overwrite
        preserve_path = not no_preserve_path
        output_path = _resolve_path(output_zip)
        source_paths = _expand_source_patterns(path_patterns or [], paths_file)
        split_size_bytes = _parse_zip_split_size(split_size)
        if split_size_bytes is not None and split_size_bytes < 0:
            raise typer.BadParameter("Split size must be zero or greater")

        if output_path.exists() and not overwrite:
            raise typer.BadParameter(
                f"Output ZIP already exists: {output_path}. Omit --no-overwrite to replace it"
            )
        if split_size_bytes and split_size_bytes > 0 and not overwrite:
            for archive_path in output_path.parent.glob(f"{output_path.name}.*"):
                if not archive_path.name.removeprefix(f"{output_path.name}.").isdigit():
                    continue
                raise typer.BadParameter(
                    f"Output ZIP already exists: {archive_path}. Omit --no-overwrite to replace it"
                )

        archived_count, archived_entries, created_archives = _build_zip_from_sources(
            output_path,
            source_paths,
            preserve_path=preserve_path,
            split_size_bytes=split_size_bytes,
        )
        print_result(
            {
                "zip_files": [str(path) for path in created_archives],
                "sources": [str(path) for path, _ in source_paths],
                "files_archived": archived_count,
                "entries_archived": len(archived_entries),
                "entries": archived_entries,
                "preserve_path": preserve_path,
                "split_size": split_size_bytes,
            },
            formatter=lambda data: console.print(
                f"Created ZIP archive(s) {', '.join(data['zip_files'])} from {len(data['sources'])} source"
                f"{'s' if len(data['sources']) != 1 else ''} with {data['files_archived']} file(s), "
                f"{data['entries_archived']} ZIP entr{'y' if data['entries_archived'] == 1 else 'ies'}."
            ),
        )
    except Exception as exc:
        _print_marker("[MARKER_ZIP_CREATE_ERROR]", zip=output_zip, error=str(exc))
        _print_marker("[MARKER_OTHER_ERROR]", command="zip-create", error=str(exc))
        raise


@app.command("raw")
def ingest_raw(
    operation_id: str,
    data: str | None = typer.Option(
        None, "--data", help="Raw payload text (JSON recommended)"
    ),
    data_file: str | None = typer.Option(
        None, "--data-file", help="Path to file containing raw payload"
    ),
    plugin: str = typer.Option(
        "raw", "--plugin", help="Plugin used to process the raw payload"
    ),
    plugin_params: str | None = typer.Option(
        None, "--plugin-params", help="JSON object for plugin_params"
    ),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpIngestionFilter"
    ),
    req_id: str | None = typer.Option(
        None, "--req-id", help="Optional request ID for chunked ingestion"
    ),
    last: bool = typer.Option(
        False, "--last", help="Mark this payload as the last raw chunk"
    ),
    reset_operation: bool = typer.Option(
        False,
        "--reset-operation",
        help="Delete and recreate the operation before ingest starts",
    ),
    create_operation_if_missing: bool = typer.Option(
        False,
        "--create-operation",
        help="Create operation automatically when it does not exist",
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for ingestion completion"),
    wait_log: bool = typer.Option(
        False,
        "--wait-log",
        help="Wait for ingestion completion and print websocket updates as they arrive.",
    ),
    wait_timeout: int = typer.Option(
        300,
        "--timeout",
        help="Seconds to wait for completion (only used with --wait/--wait-log)",
    ),
) -> None:
    """Ingest raw payload into an operation."""

    if (data is None and data_file is None) or (
        data is not None and data_file is not None
    ):
        raise typer.BadParameter("Provide exactly one of --data or --data-file")

    async def _run() -> None:
        if reset_operation and create_operation_if_missing:
            raise typer.BadParameter(
                "--reset-operation and --create-operation are mutually exclusive"
            )
        if wait and wait_log:
            raise typer.BadParameter("--wait and --wait-log are mutually exclusive")
        wait_mode = wait or wait_log

        async with get_client() as client:
            await client.ensure_websocket()

            async def _fetch_request_status(req_id: str) -> dict[str, Any] | None:
                try:
                    resp = await client._request(
                        "GET", "/request_get_by_id", params={"obj_id": req_id}
                    )
                except Exception:
                    return None
                data = resp.get("data")
                return data if isinstance(data, dict) else None

            if reset_operation:
                await client.operations.delete(operation_id, force=True)
                await client.operations.create(name=operation_id)
                if not get_runtime_verbose():
                    print_warning(
                        f"Operation {operation_id} reset (deleted and recreated)."
                    )
            else:
                await _ensure_operation_exists(
                    client,
                    operation_id,
                    create_if_missing=create_operation_if_missing,
                )

            if data_file is not None:
                payload_data: dict[str, Any] | str | bytes = Path(
                    data_file
                ).read_bytes()
            else:
                assert data is not None
                try:
                    payload_data = json.loads(data)
                except json.JSONDecodeError:
                    payload_data = data

            request_label = data_file if data_file is not None else "raw-input"
            req_to_label: dict[str, str] = {}
            tracker = await _IngestWsTracker.create(
                client,
                source_done_is_terminal=True,
                log_updates=wait_log,
                request_label_getter=lambda req_id: req_to_label.get(req_id, request_label),
                request_status_fetcher=_fetch_request_status,
            )
            params: dict[str, Any] = {
                "plugin_params": parse_json_option(
                    plugin_params, field_name="plugin-params"
                )
                or {},
                "flt": parse_json_option(flt, field_name="flt") or {},
                "last": last,
            }
            if req_id:
                params["req_id"] = req_id

            result = await client.ingest.raw(
                operation_id=operation_id,
                plugin_name=plugin,
                data=payload_data,
                params=params,
                wait=False,
            )

            if hasattr(result, "model_dump"):
                submission = result.model_dump(exclude_none=True)
            else:
                submission = {"req_id": getattr(result, "req_id", None)}

            resolved_req_id = str(submission.get("req_id") or "")
            if not resolved_req_id:
                print_result(submission)
                return

            req_to_label[resolved_req_id] = request_label
            file_req_map: dict[str, str] = {request_label: resolved_req_id}

            if wait_mode:
                waited = await tracker.wait_for_terminal(
                    request_label, resolved_req_id, wait_timeout
                )
                if wait_log:
                    _print_ingestion_finished_marker([waited])
                print_result(waited)
            else:
                timed_out = await _wait_for_stats_create(client, [resolved_req_id])
                if timed_out and not get_runtime_verbose():
                    print_warning(
                        f"Request did not receive STATS_CREATE within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s - backend may still be processing: {resolved_req_id}"
                    )

                if get_runtime_verbose():
                    print_result(
                        {
                            "file": request_label,
                            "req_id": resolved_req_id,
                            "submitted": submission,
                            "ws_confirmed": resolved_req_id not in timed_out,
                        }
                    )
                else:
                    print_result(
                        {
                            "file": request_label,
                            "req_id": resolved_req_id,
                            "status": "pending",
                        }
                    )

    asyncio.run(_run())
