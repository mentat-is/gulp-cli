from __future__ import annotations

from types import SimpleNamespace

from gulp_cli.commands import operations


def test_operation_reset_deletes_then_recreates(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    class _Operations:
        async def delete(self, operation_id: str, *, force: bool) -> None:
            calls.append(("delete", (operation_id, force)))

        async def create(self, operation_id: str):
            calls.append(("create", operation_id))
            return SimpleNamespace(model_dump=lambda **_kwargs: {"id": operation_id})

    class _ClientContext:
        async def __aenter__(self):
            return SimpleNamespace(operations=_Operations())

        async def __aexit__(self, *_args) -> bool:
            return False

    monkeypatch.setattr(operations, "get_client", lambda: _ClientContext())
    monkeypatch.setattr(operations, "print_result", lambda _value: None)

    operations.operation_reset("op")

    assert calls == [("delete", ("op", True)), ("create", "op")]
