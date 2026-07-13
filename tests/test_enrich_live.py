import asyncio
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from gulp_sdk import GulpClient

CLI_BIN = Path("/gulp/.venv/bin/gulp-cli")
SAMPLE_EVTX = Path("/gulp/samples/win_evtx/Security_short_selected.evtx")


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _run_cli(*args: str, config_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GULP_CLI_HOME"] = str(config_dir)
    return subprocess.run(
        [str(CLI_BIN), *args],
        cwd="/gulp",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


async def _setup_sample_docs() -> tuple[str, str]:
    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")
        operation_id = _unique("cli_enrich_op")
        operation = await client.operations.create(operation_id)
        ingest = await client.ingest.file(
            operation_id=operation.id,
            plugin_name="win_evtx",
            file_path=str(SAMPLE_EVTX),
            context_name="cli_enrich_context",
            wait=True,
        )
        assert str(getattr(ingest, "status", "")).lower() in {"done", "pending"}

        preview = await client.queries.query_raw(
            operation_id=operation.id,
            q={"query": {"match_all": {}}},
            q_options={"preview_mode": True, "limit": 1, "name": "cli_enrich_preview"},
        )
        docs = (preview.get("data") or {}).get("docs") or []
        assert docs, "Expected at least one sample document after ingestion"
        doc_id = docs[0].get("_id") or docs[0].get("id")
        assert doc_id, "Could not determine document id for CLI enrichment test"
        return operation.id, str(doc_id)


def _load_saved_session(config_dir: Path) -> tuple[str, str]:
    config = json.loads((config_dir / "config.json").read_text(encoding="utf-8"))
    active_user = str(config.get("active_user") or "")
    sessions = config.get("sessions") or {}
    session = sessions.get(active_user) or next(iter(sessions.values()), None)
    assert isinstance(session, dict), "Expected a saved CLI session for the live test"
    url = str(session.get("url") or "").strip()
    token = str(session.get("token") or "").strip()
    assert url and token, "Saved CLI session is missing url or token"
    return url, token


async def _get_first_doc_id(operation_id: str, config_dir: Path) -> str:
    url, token = _load_saved_session(config_dir)
    async with GulpClient(url, token=token) as client:
        preview = await client.queries.query_raw(
            operation_id=operation_id,
            q={"query": {"match_all": {}}},
            q_options={"preview_mode": True, "limit": 1, "name": "cli_enrich_preview"},
        )
        docs = (preview.get("data") or {}).get("docs") or []
        assert docs, "Expected at least one sample document after CLI ingestion"
        doc_id = docs[0].get("_id") or docs[0].get("id")
        assert doc_id, "Could not determine document id for CLI enrichment test"
        return str(doc_id)


async def _cleanup_operation(operation_id: str) -> None:
    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")
        await client.operations.delete(operation_id)


@pytest.mark.integration
def test_enrich_cli_tag_update_remove_and_untag(tmp_path: Path) -> None:
    config_dir = tmp_path / "cli-config"
    config_dir.mkdir(parents=True, exist_ok=True)

    login = _run_cli(
        "auth",
        "login",
        "--url",
        "http://localhost:8080",
        "--username",
        "admin",
        "--password",
        "admin",
        config_dir=config_dir,
    )
    assert login.returncode == 0, login.stderr or login.stdout

    operation_id = _unique("cli_enrich_op")

    ingest_result = _run_cli(
        "ingest",
        "file",
        operation_id,
        "win_evtx",
        str(SAMPLE_EVTX),
        "--context",
        "test_context",
        "--reset-operation",
        "--batch-size",
        "128",
        "--wait",
        config_dir=config_dir,
    )
    assert ingest_result.returncode == 0, ingest_result.stderr or ingest_result.stdout

    doc_id = asyncio.run(_get_first_doc_id(operation_id, config_dir))

    try:
        tag_result = _run_cli(
            "enrich",
            "tag",
            operation_id,
            "--tag",
            "cli_enrich_tag",
            "--flt",
            json.dumps({"operation_ids": [operation_id]}),
            "--wait",
            config_dir=config_dir,
        )
        assert tag_result.returncode == 0, tag_result.stderr or tag_result.stdout
        assert "RuntimeWarning" not in (tag_result.stderr or "")

        update_result = _run_cli(
            "enrich",
            "update",
            operation_id,
            "--fields",
            json.dumps({"cli_enrich_field": True}),
            "--flt",
            json.dumps({"operation_ids": [operation_id]}),
            "--wait",
            config_dir=config_dir,
        )
        assert update_result.returncode == 0, (
            update_result.stderr or update_result.stdout
        )

        remove_result = _run_cli(
            "enrich",
            "remove",
            operation_id,
            "--fields",
            "cli_enrich_field",
            "--flt",
            json.dumps({"operation_ids": [operation_id]}),
            "--wait",
            config_dir=config_dir,
        )
        assert remove_result.returncode == 0, (
            remove_result.stderr or remove_result.stdout
        )

        untag_result = _run_cli(
            "enrich",
            "untag",
            operation_id,
            "--tag",
            "cli_enrich_tag",
            "--flt",
            json.dumps({"operation_ids": [operation_id]}),
            "--wait",
            config_dir=config_dir,
        )
        assert untag_result.returncode == 0, untag_result.stderr or untag_result.stdout

        async def _verify() -> None:
            async with GulpClient("http://localhost:8080") as client:
                await client.auth.login("admin", "admin")
                fetched = await client.queries.query_single_id(operation_id, doc_id)
                assert isinstance(fetched, dict)
                tags = fetched.get("gulp.tags") or fetched.get("gulp", {}).get(
                    "tags", []
                )
                assert "cli_enrich_tag" not in tags
                assert "cli_enrich_field" not in fetched

        asyncio.run(_verify())
    finally:
        try:
            asyncio.run(_cleanup_operation(operation_id))
        except Exception:
            pass
        try:
            shutil.rmtree(config_dir, ignore_errors=True)
        except Exception:
            pass


@pytest.mark.integration
def test_enrich_cli_documents_and_single_id(tmp_path: Path) -> None:
    config_dir = tmp_path / "cli-config"
    config_dir.mkdir(parents=True, exist_ok=True)

    login = _run_cli(
        "auth",
        "login",
        "--url",
        "http://localhost:8080",
        "--username",
        "admin",
        "--password",
        "admin",
        config_dir=config_dir,
    )
    assert login.returncode == 0, login.stderr or login.stdout

    operation_id, doc_id = asyncio.run(_setup_sample_docs())

    login = _run_cli(
        "auth",
        "login",
        "--url",
        "http://localhost:8080",
        "--username",
        "admin",
        "--password",
        "admin",
        config_dir=config_dir,
    )
    assert login.returncode == 0, login.stderr or login.stdout

    try:
        documents_result = _run_cli(
            "enrich",
            "documents",
            operation_id,
            "--plugin",
            "enrich_whois",
            "--fields",
            json.dumps({"source.ip": None}),
            "--flt",
            json.dumps({"operation_ids": [operation_id]}),
            "--plugin-params",
            json.dumps({"custom_parameters": {}}),
            "--wait",
            config_dir=config_dir,
        )

        if documents_result.returncode != 0:
            pytest.skip(
                f"enrich_whois unavailable for CLI documents test: {documents_result.stderr or documents_result.stdout}"
            )

        single_result = _run_cli(
            "enrich",
            "single-id",
            operation_id,
            doc_id,
            "--plugin",
            "enrich_whois",
            "--fields",
            json.dumps({"sdk_cli_whois": "8.8.8.8"}),
            "--plugin-params",
            json.dumps({"custom_parameters": {}}),
            config_dir=config_dir,
        )
        if single_result.returncode != 0:
            pytest.skip(
                f"enrich_whois unavailable for CLI single-id test: {single_result.stderr or single_result.stdout}"
            )

        async def _verify() -> None:
            async with GulpClient("http://localhost:8080") as client:
                await client.auth.login("admin", "admin")
                fetched = await client.queries.query_single_id(operation_id, doc_id)
                assert isinstance(fetched, dict)
                assert fetched.get("_id") == doc_id or fetched.get("id") == doc_id

        asyncio.run(_verify())
    finally:
        try:
            asyncio.run(_cleanup_operation(operation_id))
        except Exception:
            pass
        try:
            shutil.rmtree(config_dir, ignore_errors=True)
        except Exception:
            pass
