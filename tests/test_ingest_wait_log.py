from __future__ import annotations

import asyncio
import inspect

import pytest

from gulp_cli.commands.ingest import (
    _IngestWsTracker,
    ingest_file,
    ingest_file_to_source,
    ingest_raw,
    ingest_zip,
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


def test_ingest_zip_exposes_wait_log_option() -> None:
    wait_log_default = inspect.signature(ingest_zip).parameters["wait_log"].default
    assert wait_log_default.default is False


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
            data={"obj": {"status": "failed"}},
        )
    )

    out = capsys.readouterr().out
    assert "FAILED!" in out
    assert "req12345" in out
    assert "sample.txt" in out


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
