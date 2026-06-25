# Stdout Markers Cheat Sheet

Marker lines are emitted as one unwrapped stdout line:

```text
GULP_MARKER: [MARKER_NAME] | {"json": "payload"}
```

Parser rule: match lines starting with `GULP_MARKER: `, split once on ` | `, then JSON-decode the right side.

## Ingest `--wait-log`

These markers are emitted by `ingest file --wait-log`, `ingest file-to-source --wait-log`, and `ingest raw --wait-log`.

### `[MARKER_INGEST_SOURCE_DONE_RECEIVED]`

Emitted when the backend sends `INGEST_SOURCE_DONE`.

Payload:
- `req_id`: backend request id.
- `file`: display label for the file/request.
- `status`: status from the source-done packet or current state.
- `ingested`: accumulated ingested record count.
- `skipped`: accumulated skipped record count.
- `failed`: accumulated failed record count.
- `errors`: extracted backend errors, usually an array of strings.

### `[MARKER_ONGOING_STATS_RECEIVED]`

Emitted for `STATS_CREATE` or `STATS_UPDATE` while status is not `done`, `failed`, or `canceled`.

Payload:
- `req_id`: backend request id.
- `file`: display label for the file/request.
- `event`: websocket event name, usually `STATS_CREATE` or `STATS_UPDATE`.
- `status`: current stats status.
- `ingested`: current authoritative ingested count.
- `skipped`: current authoritative skipped count.
- `failed`: current authoritative failed count.
- `pct`: ingest percentage when provided by the backend, otherwise `null`.
- `errors`: extracted backend errors, usually an array of strings.

### `[MARKER_DONE_STATS_RECEIVED]`

Emitted for `STATS_CREATE` or `STATS_UPDATE` when status is `done`.

Payload: same fields as `[MARKER_ONGOING_STATS_RECEIVED]`.

### `[MARKER_FAILED_STATS_RECEIVED]`

Emitted for `STATS_CREATE` or `STATS_UPDATE` when status is `failed` or `canceled`.

Also emitted after a backend websocket `ERROR` packet.

Payload:
- From stats packets: same fields as `[MARKER_ONGOING_STATS_RECEIVED]`.
- From `ERROR` packets: `req_id`, `file`, `event`, `status`, `ingested`, `skipped`, `failed`, `errors`.

### `[MARKER_BACKEND_EXCEPTION_REPORTED]`

Emitted when the backend sends websocket `ERROR`.

Payload:
- `req_id`: backend request id.
- `file`: display label for the file/request.
- `event`: websocket event name, `ERROR`.
- `status`: always set to `failed` by the CLI for this request.
- `errors`: extracted backend errors, usually an array of strings.

### `[MARKER_INGESTION_FINISHED]`

Emitted once after wait-log completion, before the final CLI result JSON/table output.

Payload:
- `requests_total`: number of request results.
- `requests_done`: count with status `done`.
- `requests_failed`: count with status `failed`.
- `requests_canceled`: count with status `canceled`.
- `requests_timeout`: count with status `timeout`.
- `ingested`: accumulated ingested record count.
- `skipped`: accumulated skipped record count.
- `failed`: accumulated failed record count.

## `ingest zip-create`

These markers are emitted by local ZIP creation.

### `[MARKER_FILE_ADDED_TO_ZIP]`

Emitted after each ZIP entry is written.

Payload:
- `zip`: requested output ZIP path.
- `entry`: ZIP entry name.
- `source`: source filesystem path for the entry.
- `file_size`: uncompressed entry size in bytes.
- `compress_size`: compressed entry size in bytes.
- `current`: 1-based count of entries added so far.
- `total`: total entries planned for the ZIP.
- `percent`: integer progress percentage.

### `[MARKER_ZIP_CREATED_SUCCESSFULLY]`

Emitted once after the ZIP or multipart ZIP volumes are published.

Payload:
- `zip_files`: array of created archive paths.
- `files_archived`: number of source files archived. Directory entries are not counted here.
- `entries_archived`: number of ZIP entries archived, including directory entries.

### `[MARKER_ZIP_CREATE_ERROR]`

Emitted when ZIP creation hits a validation, scan, write, or publish error.

Payload variants:
- Scan/write skip errors: `path`, `zip`, `error`.
- Top-level `zip-create` command errors: `zip`, `error`.

### `[MARKER_OTHER_ERROR]`

Emitted with top-level `zip-create` command exceptions after `[MARKER_ZIP_CREATE_ERROR]`.

Payload:
- `command`: currently `zip-create`.
- `error`: exception text.
