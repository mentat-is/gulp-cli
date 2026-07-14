"""Raw-ingest worker wait coverage."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from gulp_cli.commands import ingest as ingest_module


def test_ingest_raw_passes_wait_and_timeout_to_sdk(monkeypatch) -> None:
    raw = AsyncMock(return_value=SimpleNamespace(req_id="req-1"))
    client = SimpleNamespace(
        ingest=SimpleNamespace(raw=raw),
        ensure_websocket=AsyncMock(),
    )

    @asynccontextmanager
    async def _client_context():
        yield client

    tracker = SimpleNamespace(
        wait_for_terminal=AsyncMock(return_value={"status": "done"})
    )
    monkeypatch.setattr(ingest_module, "get_client", _client_context)
    monkeypatch.setattr(
        ingest_module,
        "_IngestWsTracker",
        SimpleNamespace(create=AsyncMock(return_value=tracker)),
    )
    monkeypatch.setattr(ingest_module, "_ensure_operation_exists", AsyncMock())
    monkeypatch.setattr(ingest_module, "print_result", lambda _result: None)

    ingest_module.ingest_raw(
        operation_id="op-1",
        data="[]",
        data_file=None,
        plugin="raw",
        plugin_params=None,
        flt=None,
        req_id=None,
        last=True,
        reset_operation=False,
        create_operation_if_missing=False,
        wait=True,
        wait_log=False,
        wait_timeout=321,
    )

    kwargs = raw.await_args.kwargs
    assert kwargs["wait_for_worker"] is True
    assert kwargs["timeout"] == 321
    assert kwargs["wait"] is False
