from __future__ import annotations

import asyncio
import inspect

import pytest

from gulp_cli.commands.ingest import (
    _IngestWsTracker,
    _print_ingestion_finished_marker,
    ingest_file,
    ingest_file_to_source,
    ingest_raw,
)
from gulp_sdk.websocket import WSMessage, WSMessageType


def test_ingest_file_exposes_wait_log_option() -> None:
    wait_log_default = inspect.signature(ingest_file).parameters["wait_log"].default
    assert wait_log_default.default is False


def test_ingest_file_to_source_exposes_wait_log_option() -> None:
    wait_log_default = inspect.signature(ingest_file_to_source).parameters[
        "wait_log"
    ].default
    assert wait_log_default.default is False


def test_ingest_file_to_source_exposes_plugin_option() -> None:
    plugin_default = inspect.signature(ingest_file_to_source).parameters[
        "plugin"
    ].default
    assert plugin_default.param_decls == ("--plugin",)


def test_ingest_raw_exposes_wait_log_option() -> None:
    wait_log_default = inspect.signature(ingest_raw).parameters["wait_log"].default
    assert wait_log_default.default is False


def test_ingest_ws_tracker_logs_updates_to_stdout(capsys) -> None:
    class _FakeWs:
        def on_message(self, *_args, **_kwargs) -> None:
            pass

        def off_message(self, *_args, **_kwargs) -> None:
            pass

    tracker = _IngestWsTracker(
        _FakeWs(),
        log_updates=True,
        request_label_getter=lambda _req_id: "/tmp/sample.txt",
    )

    tracker._on_message(  # noqa: SLF001
        WSMessage(
            type=WSMessageType.STATS_UPDATE.value,
            req_id="req12345",
            timestamp_msec=0,
            data={
                "obj": {
                    "status": "ongoing",
                    "ingest_percentage": 42,
                    "records_ingested": 12,
                    "records_skipped": 1,
                    "records_failed": 0,
                }
            },
        )
    )

    out = capsys.readouterr().out
    assert "sample.txt" in out
    assert "stats update" in out
    assert "42%" in out
    assert "req12345" in out
    assert "ingested=12" in out
    assert "skipped=1" in out
    assert "GULP_MARKER: [MARKER_ONGOING_STATS_RECEIVED]" in out


def test_ingest_ws_tracker_marks_failures_obviously(capsys) -> None:
    class _FakeWs:
        def on_message(self, *_args, **_kwargs) -> None:
            pass

        def off_message(self, *_args, **_kwargs) -> None:
            pass

    tracker = _IngestWsTracker(
        _FakeWs(),
        log_updates=True,
        request_label_getter=lambda _req_id: "/tmp/sample.txt",
    )

    tracker._on_message(  # noqa: SLF001
        WSMessage(
            type=WSMessageType.ERROR.value,
            req_id="req12345",
            timestamp_msec=0,
            data={"obj": {"status": "failed", "message": "backend rejected file"}},
        )
    )

    out = capsys.readouterr().out
    assert "FAILED!" in out
    assert "req12345" in out
    assert "sample.txt" in out
    assert "backend rejected file" in out
    assert "GULP_MARKER: [MARKER_BACKEND_EXCEPTION_REPORTED]" in out
    assert "GULP_MARKER: [MARKER_FAILED_STATS_RECEIVED]" in out


def test_ingest_ws_tracker_marks_source_done(capsys) -> None:
    class _FakeWs:
        def on_message(self, *_args, **_kwargs) -> None:
            pass

        def off_message(self, *_args, **_kwargs) -> None:
            pass

    tracker = _IngestWsTracker(
        _FakeWs(),
        log_updates=True,
        request_label_getter=lambda _req_id: "/tmp/sample.txt",
    )

    tracker._on_message(  # noqa: SLF001
        WSMessage(
            type=WSMessageType.INGEST_SOURCE_DONE.value,
            req_id="req12345",
            timestamp_msec=0,
            data={"obj": {"status": "done", "records_ingested": 3}},
        )
    )

    out = capsys.readouterr().out
    assert "GULP_MARKER: [MARKER_INGEST_SOURCE_DONE_RECEIVED]" in out
    assert '"ingested": 3' in out


@pytest.mark.parametrize(
    ("status", "marker"),
    [
        ("done", "GULP_MARKER: [MARKER_DONE_STATS_RECEIVED]"),
        ("failed", "GULP_MARKER: [MARKER_FAILED_STATS_RECEIVED]"),
    ],
)
def test_ingest_ws_tracker_marks_terminal_stats(
    status: str, marker: str, capsys
) -> None:
    class _FakeWs:
        def on_message(self, *_args, **_kwargs) -> None:
            pass

        def off_message(self, *_args, **_kwargs) -> None:
            pass

    tracker = _IngestWsTracker(
        _FakeWs(),
        log_updates=True,
        request_label_getter=lambda _req_id: "/tmp/sample.txt",
    )

    tracker._on_message(  # noqa: SLF001
        WSMessage(
            type=WSMessageType.STATS_UPDATE.value,
            req_id="req12345",
            timestamp_msec=0,
            data={"obj": {"status": status}},
        )
    )

    assert marker in capsys.readouterr().out


def test_ingestion_finished_marker(capsys) -> None:
    _print_ingestion_finished_marker(
        [
            {"status": "done", "ingested": 10, "skipped": 2, "failed": 1},
            {"status": "failed", "ingested": 3, "skipped": 0, "failed": 4},
            {"status": "timeout"},
        ]
    )

    out = capsys.readouterr().out
    assert "GULP_MARKER: [MARKER_INGESTION_FINISHED]" in out
    assert '"requests_total": 3' in out
    assert '"requests_done": 1' in out
    assert '"requests_failed": 1' in out
    assert '"requests_timeout": 1' in out
    assert '"ingested": 13' in out
    assert '"skipped": 2' in out
    assert '"failed": 5' in out


@pytest.mark.asyncio
async def test_ingest_ws_tracker_uses_source_done_status_for_wait_results() -> None:
    class _FakeWs:
        def on_message(self, *_args, **_kwargs) -> None:
            pass

        def off_message(self, *_args, **_kwargs) -> None:
            pass

    tracker = _IngestWsTracker(
        _FakeWs(),
        source_done_is_terminal=True,
        request_label_getter=lambda _req_id: "/tmp/sample.txt",
    )

    wait_task = asyncio.create_task(
        tracker.wait_for_terminal("/tmp/sample.txt", "req12345", timeout=1)
    )

    tracker._on_message(  # noqa: SLF001
        WSMessage(
            type=WSMessageType.INGEST_SOURCE_DONE.value,
            req_id="req12345",
            timestamp_msec=0,
            data={
                "obj": {
                    "status": "failed",
                    "records_ingested": 14,
                    "records_skipped": 0,
                    "records_failed": 1,
                }
            },
        )
    )

    result = await wait_task
    tracker.close()

    assert result["status"] == "failed"
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_ingest_ws_tracker_keeps_failed_terminal_status_after_source_done() -> None:
    class _FakeWs:
        def on_message(self, *_args, **_kwargs) -> None:
            pass

        def off_message(self, *_args, **_kwargs) -> None:
            pass

    tracker = _IngestWsTracker(
        _FakeWs(),
        source_done_is_terminal=True,
        request_label_getter=lambda _req_id: "/tmp/sample.txt",
    )

    wait_task = asyncio.create_task(
        tracker.wait_for_terminal("/tmp/sample.txt", "req12345", timeout=1)
    )

    tracker._on_message(  # noqa: SLF001
        WSMessage(
            type=WSMessageType.INGEST_SOURCE_DONE.value,
            req_id="req12345",
            timestamp_msec=0,
            data={
                "obj": {
                    "records_ingested": 14,
                    "records_skipped": 0,
                    "records_failed": 0,
                }
            },
        )
    )
    await asyncio.sleep(0)
    tracker._on_message(  # noqa: SLF001
        WSMessage(
            type=WSMessageType.STATS_UPDATE.value,
            req_id="req12345",
            timestamp_msec=0,
            data={
                "obj": {
                    "status": "failed",
                    "records_ingested": 14,
                    "records_skipped": 0,
                    "records_failed": 1,
                }
            },
        )
    )

    result = await wait_task
    tracker.close()

    assert result["status"] == "failed"
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_ingest_ws_tracker_returns_errors_for_failed_stats() -> None:
    class _FakeWs:
        def on_message(self, *_args, **_kwargs) -> None:
            pass

        def off_message(self, *_args, **_kwargs) -> None:
            pass

    tracker = _IngestWsTracker(
        _FakeWs(),
        request_label_getter=lambda _req_id: "/tmp/sample.txt",
    )

    wait_task = asyncio.create_task(
        tracker.wait_for_terminal("/tmp/sample.txt", "req12345", timeout=1)
    )

    tracker._on_message(  # noqa: SLF001
        WSMessage(
            type=WSMessageType.STATS_UPDATE.value,
            req_id="req12345",
            timestamp_msec=0,
            data={
                "obj": {
                    "status": "failed",
                    "data": {"errors": ["parser failed"]},
                    "records_failed": 1,
                }
            },
        )
    )

    result = await wait_task
    tracker.close()

    assert result["status"] == "failed"
    assert result["errors"] == ["parser failed"]
