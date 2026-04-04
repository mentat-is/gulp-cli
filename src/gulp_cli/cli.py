from __future__ import annotations

import typer

from gulp_cli.commands.acl import app as acl_app
from gulp_cli.commands.auth import app as auth_app
from gulp_cli.commands.collab import app as collab_app
from gulp_cli.commands.context import app as context_app
from gulp_cli.commands.db import app as db_app
from gulp_cli.commands.enhance_map import app as enhance_map_app
from gulp_cli.commands.glyph import app as glyph_app
from gulp_cli.commands.ingest import app as ingest_app
from gulp_cli.commands.mapping import app as mapping_app
from gulp_cli.commands.operations import app as operation_app
from gulp_cli.commands.plugin import app as plugin_app
from gulp_cli.commands.query import app as query_app
from gulp_cli.commands.source import app as source_app
from gulp_cli.commands.stats import app as stats_app
from gulp_cli.commands.storage import app as storage_app
from gulp_cli.commands.user_group import app as user_group_app
from gulp_cli.commands.users import app as user_app
from gulp_sdk.client import GulpClient

from gulp_cli.config import set_runtime_as_user, set_runtime_verbose
from gulp_cli.extensions import load_extensions

app = typer.Typer(
    no_args_is_help=True,
    help="Modern CLI for gULP, powered by gulp-sdk",
)


def _show_versions(value: bool) -> None:
    if not value:
        return

    from gulp_cli._version import __version__, __commit_id__

    sdk_version = GulpClient("http://localhost:8080").version()
    print(f"gulp-cli version: {__version__} ({__commit_id__})" if __commit_id__ else __version__)
    print(f"gulp-sdk version: {sdk_version}")
    raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    as_user: str | None = typer.Option(
        None,
        "--as-user",
        help="Use the saved session of a different already-logged-in user for this command only.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Print complete result JSON instead of summary (global override).",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_show_versions,
        is_eager=True,
        help="Show CLI and SDK versions and exit.",
    ),
) -> None:
    set_runtime_as_user(as_user)
    set_runtime_verbose(verbose)

app.add_typer(auth_app, name="auth")
app.add_typer(user_app, name="user")
app.add_typer(user_group_app, name="user-group")
app.add_typer(operation_app, name="operation")
app.add_typer(context_app, name="context")
app.add_typer(source_app, name="source")
app.add_typer(ingest_app, name="ingest")
app.add_typer(query_app, name="query")
app.add_typer(stats_app, name="stats")
app.add_typer(storage_app, name="storage")
app.add_typer(collab_app, name="collab")
app.add_typer(db_app, name="db")
app.add_typer(acl_app, name="acl")
app.add_typer(plugin_app, name="plugin")
app.add_typer(mapping_app, name="mapping")
app.add_typer(enhance_map_app, name="enhance-map")
app.add_typer(glyph_app, name="glyph")

load_extensions(
    app,
    command_groups={
        "auth": auth_app,
        "user": user_app,
        "user-group": user_group_app,
        "operation": operation_app,
        "context": context_app,
        "source": source_app,
        "ingest": ingest_app,
        "query": query_app,
        "stats": stats_app,
        "storage": storage_app,
        "collab": collab_app,
        "db": db_app,
        "acl": acl_app,
        "plugin": plugin_app,
        "mapping": mapping_app,
        "enhance-map": enhance_map_app,
        "glyph": glyph_app,
    },
)
