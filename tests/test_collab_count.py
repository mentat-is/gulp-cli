from __future__ import annotations


def test_collab_count_command_uses_sdk(monkeypatch) -> None:
    import gulp_cli.commands.collab as collab

    seen: dict[str, object] = {}

    class _FakePlugins:
        async def object_count(self, **kwargs) -> dict[str, int]:
            seen.update(kwargs)
            return {"count": 7}

    class _FakeClient:
        plugins = _FakePlugins()

    class _FakeGetClient:
        async def __aenter__(self):
            return _FakeClient()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(collab, "get_client", lambda: _FakeGetClient())
    monkeypatch.setattr(collab, "print_result", lambda data: seen.setdefault("data", data))

    collab.object_count("note", operation_id="op-a", flt='{"tags":["auto"]}')

    assert seen == {
        "obj_type": "note",
        "flt": {"tags": ["auto"]},
        "operation_id": "op-a",
        "data": {"count": 7},
    }
