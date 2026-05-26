# Portable gulp-cli

Portable bundles are the recommended way to run `gulp-cli` from removable media or on machines without internet access.

## What portable means here

- You build one bundle per target OS and architecture.
- The bundle already contains Python, `gulp-cli`, `gulp-sdk`, and runtime dependencies.
- User state lives in a local `data/` folder instead of the user profile.

There is no single executable that runs unchanged on Linux, Windows, and macOS. Build and ship one artifact for each platform:

- Linux `x86_64`
- Windows `x86_64`
- macOS `x86_64`
- macOS `arm64`

## Portable layout

The CI workflow produces a directory like this:

```text
gulp-cli-portable-<platform>/
  gulp-cli[.exe]
  _internal/
  launch-linux.sh | launch-macos.sh | launch-windows.bat
  data/
    extension/
  README.md
```

`gulp-cli` automatically uses `./data` when running from a frozen bundle and that directory exists.

## Runtime overrides

The CLI supports both of these overrides:

```bash
GULP_CLI_HOME=/path/to/portable-data gulp-cli auth whoami
gulp-cli --config-dir /path/to/portable-data auth whoami
```

The overridden directory stores:

- `config.json`
- `extension/`

## Local build

Build a portable bundle locally from the repo root:

```bash
python -m pip install --upgrade pip
python -m pip install '.[portable]'
pyinstaller --noconfirm --clean gulp-cli.spec
```

The output is written under `dist/gulp-cli/`.

## Notes for offline USB use

- Build bundles on CI or on a machine with internet access first.
- Copy the resulting platform-specific bundle folders to the USB stick.
- The target machine does not need Python or internet access.
- The target machine still needs network connectivity to the gULP server unless that server is local.

## GitHub Actions

The repository includes a matrix workflow that builds portable artifacts for:

- Linux `x86_64`
- Windows `x86_64`
- macOS `x86_64`
- macOS `arm64`

Artifacts are uploaded from `.github/workflows/portable-bundles.yml`.
