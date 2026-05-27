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

## practical usage examples

following are some practical usage examples of the portable bundles

### ingesting windows evtx files taken from a windows machine and ingesting them on a linux machine

#### step 1: take windows evtx files from a windows machine  

1. Unzip the portable bundle on a USB stick and plug it into the windows machine
2. Open a command prompt and navigate to the gulp-cli portable bundle on the USB stick
3. Run the following command to generate the zip with evtx files
   ~~~bash
   D:\> cd \path\to\gulp-cli-portable-windows-x64
   
   D:\path\to\gulp-cli-portable-windows-x64> .\launch-windows.bat ingest zip-create ./evtx.zip C:\Windows\System32\winevt\Logs\
   ~~~

#### step 2: ingest the evtx files on a linux machine

> we assume the linux machine have gulp-cli installed and configured to connect to the gULP server, and the user have permissions to ingest data to the gULP server.

1. Go on the linux machine (which can connect to the gULP server) and plug in the USB stick with the portable bundle from above
2. Open a terminal and navigate to the gulp-cli portable bundle on the USB stick
3. Unzip the evtx.zip file to a local directory
    ~~~bash
    $ cd /path/to/gulp-cli-portable-windows-x64
    $ unzip evtx.zip
    # you obtain a `Logs` directory with the evtx files
    ~~~
4. Run the following commands to ingest the evtx files to the gULP server
    ~~~bash
    # authenticate to the gULP server (if not already authenticated)
    gulp-cli auth login --url http://localhost:8080 --username admin --password admin
    # ingest the evtx files to the gULP server, we assume a `test_operation` exists on the gULP server, and we want to ingest the evtx files to that operation
    gulp-cli ingest file test_operation win_evtx ./Logs/*.evtx
    ~~~