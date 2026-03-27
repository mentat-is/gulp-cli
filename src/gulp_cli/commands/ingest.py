from __future__ import annotations

import asyncio
from glob import glob
from pathlib import Path

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_error, print_json
from gulp_cli.utils import parse_json_option

app = typer.Typer(help="Ingestion commands")


@app.command("file")
def ingest_file(
    operation_id: str,
    plugin: str,
    file_patterns: list[str] = typer.Argument(..., help="One or more files or glob patterns to ingest (e.g. '*.evtx', '/path/to/dir/*')"),
    context_name: str = typer.Option("sdk_context", "--context-name"),
    plugin_params: str | None = typer.Option(None, "--plugin-params", help="JSON object for plugin_params"),
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpIngestionFilter"),
    wait: bool = typer.Option(False, "--wait"),
) -> None:
    """Ingest one or more files using glob patterns for wildcard matching."""
    
    # Expand glob patterns to actual files
    expanded_files: list[str] = []
    for pattern in file_patterns:
        matches = glob(pattern, recursive=True)
        if not matches:
            # If no matches, treat as literal file path (may not exist, server will error)
            expanded_files.append(pattern)
        else:
            expanded_files.extend(sorted(matches))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in expanded_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)
    
    if not unique_files:
        print_error("No files found matching the provided patterns.")
        raise typer.Exit(1)
    
    async def _ingest_one(file_path: str) -> dict:
        params = {
            "plugin_params": parse_json_option(plugin_params, field_name="plugin-params") or {},
            "flt": parse_json_option(flt, field_name="flt") or {},
            "original_file_path": str(Path(file_path).resolve()),
        }
        async with get_client() as client:
            result = await client.ingest.file(
                operation_id=operation_id,
                plugin_name=plugin,
                file_path=file_path,
                context_name=context_name,
                params=params,
                wait=wait,
            )
            return {
                "file": file_path,
                "req_id": result.req_id,
                "status": result.status,
            }

    async def _run() -> None:
        results = await asyncio.gather(*[_ingest_one(path) for path in unique_files])
        print_json(results)

    asyncio.run(_run())
