# gulp-cli Extensions

This document describes how gulp-cli loads dynamic extensions and how to create custom commands without modifying the core CLI code.

---

## Extension Paths

gulp-cli searches Python extension files in two folders:

1. Internal built-in extensions: `src/gulp_cli/extension/`
2. External user extensions: `~/.config/gulp-cli/extension/`

If the same filename exists in both folders, the external one overrides the internal one.

---

## Load Order and Priority

- Internal extensions are discovered first.
- External extensions are discovered after and overwrite by filename.
- Every `.py` file that does not start with `_` is considered an extension module.

If an extension fails to load or register, gulp-cli prints a warning and continues startup.

---

## Extension Contract

Each extension module must expose a callable named `register_extension`.

Recommended signature:

```python
def register_extension(*, command_groups, get_client, app, **kwargs):
    ...
```

Available registration inputs:

- `command_groups`: dict of Typer groups already registered by gulp-cli (`query`, `ingest`, `plugin`, ...)
- `get_client`: async context manager factory used by core commands to access `GulpClient`
- `app`: root Typer application

Extensions can attach commands to existing groups (for example `query`) or to the root app.

---

## Built-in Extension: query sigma-zip

gulp-cli includes an internal extension that registers:

```bash
gulp-cli query sigma-zip OPERATION_ID --zip-file /path/to/rules.zip [OPTIONS]
```

This command calls the plugin extension endpoint `/query_sigma_zip` via `gulp-sdk` (`client.queries.query_sigma_zip`).

Main options:

- `--src-ids`
- `--levels`
- `--tags`
- `--products`
- `--categories`
- `--services`
- `--q-options`
- `--wait`
- `--timeout`

---

## Built-in Extension: collab story

gulp-cli includes an internal extension that registers story commands under the collaboration group:

```bash
gulp-cli collab story [COMMAND]
```

Available commands:

- `create`
- `update`
- `delete`
- `get`
- `list`

These commands call the story plugin endpoints directly:

- `/story_create`
- `/story_update`
- `/story_delete`
- `/story_get_by_id`
- `/story_list`

Example:

```bash
gulp-cli collab story create incident-001 \
    --name "Incident summary" \
    --doc-ids doc-a,doc-b \
    --highlight-ids hl-1 \
    --wait
```

---

## Reusable Helper for Extension Endpoints

The CLI includes `src/gulp_cli/extension_helpers.py` with `call_custom_endpoint(...)`.

Use this helper when an extension endpoint is not yet wrapped in `gulp-sdk`:

- executes direct HTTP requests via `client._request(...)`
- can ensure websocket connection before calling the endpoint
- supports `wait` by resolving pending requests through request stats

This pattern is recommended for future extension APIs until dedicated SDK wrappers are added.

---

## External Extension Example

Create `~/.config/gulp-cli/extension/my_custom_api.py`:

```python
import asyncio
import typer


def register_extension(*, app: typer.Typer, get_client, **kwargs):
    @app.command("my-custom-api")
    def my_custom_api(operation_id: str, payload: str = typer.Option("{}", "--payload")):
        async def _run() -> None:
            import json

            body = json.loads(payload)
            async with get_client() as client:
                result = await client._request(
                    "POST",
                    "/my_custom_api",
                    json=body,
                    params={
                        "operation_id": operation_id,
                        "ws_id": client.ws_id,
                    },
                )
                print(result)

        asyncio.run(_run())
```

Now run:

```bash
gulp-cli my-custom-api incident-001 --payload '{"k":"v"}'
```
