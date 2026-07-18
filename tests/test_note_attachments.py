"""CLI dispatch for note attachment commands."""


def test_note_attachment_commands_use_sdk(monkeypatch, tmp_path) -> None:
    import gulp_cli.commands.collab as collab

    calls: list[tuple[str, tuple, dict]] = []
    printed: list[object] = []

    class _FakeCollab:
        async def note_add_attachment(self, *args, **kwargs):
            calls.append(("add", args, kwargs))
            return {"id": "attachment-a"}

        async def note_delete_attachment(self, *args, **kwargs):
            calls.append(("delete", args, kwargs))
            return {"id": "attachment-a"}

        async def note_list_attachments(self, *args, **kwargs):
            calls.append(("list", args, kwargs))
            return [{"id": "attachment-a"}]

        async def note_get_attachment(self, *args, **kwargs):
            calls.append(("get", args, kwargs))
            return args[2]

    class _FakeClient:
        collab = _FakeCollab()

        async def ensure_websocket(self):
            return None

    class _FakeGetClient:
        async def __aenter__(self):
            return _FakeClient()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(collab, "get_client", lambda: _FakeGetClient())
    monkeypatch.setattr(
        collab,
        "print_result",
        lambda data, **_kwargs: printed.append(data),
    )

    upload = tmp_path / "evidence.bin"
    output = tmp_path / "download.bin"
    collab.note_add_attachment(
        "note-a", str(upload), title="Evidence", mime_type="x/test"
    )
    collab.note_delete_attachment("note-a", "attachment-a")
    collab.note_list_attachments("note-a")
    collab.note_get_attachment("note-a", "attachment-a", output=str(output))

    print("CLI attachment SDK calls:", calls)
    assert calls == [
        (
            "add",
            ("note-a", str(upload)),
            {"title": "Evidence", "mime_type": "x/test"},
        ),
        ("delete", ("note-a", "attachment-a"), {}),
        ("list", ("note-a",), {}),
        ("get", ("note-a", "attachment-a", str(output)), {}),
    ]
    assert printed == [
        {"id": "attachment-a"},
        {"id": "attachment-a"},
        [{"id": "attachment-a"}],
        str(output),
    ]
