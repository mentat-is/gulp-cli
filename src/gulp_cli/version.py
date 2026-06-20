from __future__ import annotations

def print_version() -> None:
    """Print the CLI version."""
    from gulp_cli._version import __commit_id__, __version__

    print(
        f"gulp-cli version: {__version__} ({__commit_id__})"
        if __commit_id__
        else f"gulp-cli version: {__version__}"
    )


def main() -> None:
    """Entry point for the standalone CLI version command."""
    print_version()


if __name__ == "__main__":
    main()
