from __future__ import annotations

import sys

from gulp_cli.config import set_runtime_config_dir


def _bootstrap_runtime_config_dir(argv: list[str]) -> None:
    for index, arg in enumerate(argv):
        if arg == "--config-dir" and index + 1 < len(argv):
            set_runtime_config_dir(argv[index + 1])
            return
        if arg.startswith("--config-dir="):
            set_runtime_config_dir(arg.split("=", 1)[1])
            return


_bootstrap_runtime_config_dir(sys.argv[1:])

from gulp_cli.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
