# gulp-cli Command Reference

Complete documentation of all available gulp-cli commands and options.

---

## Guide

Commands are organized hierarchically (e.g., `gulp-cli auth login`). This reference uses the format:

```
gulp-cli <group> <command> [OPTIONS] [ARGUMENTS]
```

Global options available on every command:

```bash
gulp-cli --verbose --as-user USER_NAME <group> <command> ...
```

- `--as-user` uses a different already-saved login session (**user must be already logged-in with `auth`**)for the current command only.
- `--verbose` prints full JSON output instead of the standard summary/table output.

---

## Core Commands

### Authentication (`auth`)

#### `login`

Authenticate with gULP server and store authentication token.

```bash
gulp-cli auth login [OPTIONS]
```

**Options:**
- `--url TEXT` — Server URL (default: from config or `http://localhost:8080`)
- `--username TEXT` — Username (required)
- `--password TEXT` — Password (required, or prompt if not provided)

**Examples:**
```bash
gulp-cli auth login --url http://localhost:8080 --username admin --password admin
gulp-cli auth login --url http://localhost:8080 --username guest --password guest
gulp-cli auth login  # Prompts for missing values
```

Each login is saved under that username, so you can switch later with the global `--as-user` flag.

---

#### `logout`

Logout the current saved session.

```bash
gulp-cli auth logout [OPTIONS]
```

**Examples:**
```bash
gulp-cli auth logout
gulp-cli --as-user guest auth logout
```

---

#### `whoami`

Display current authenticated user info.

```bash
gulp-cli auth whoami [OPTIONS]
```

**Examples:**
```bash
gulp-cli auth whoami
gulp-cli --as-user guest auth whoami
```

**Output:**
```
├─ User: admin
├─ Permissions: admin
└─ URL: http://localhost:8080
```

---

## User Management (`user`) — Admin Only

#### `list`

List all users in the system.

```bash
gulp-cli user list [OPTIONS]
```

**Options:**
- `--limit INTEGER` — Max results (default: 50)
- `--offset INTEGER` — Offset (default: 0)

**Examples:**
```bash
gulp-cli user list
gulp-cli user list --limit 100
```

---

#### `get`

Get details for a specific user.

```bash
gulp-cli user get USERNAME [OPTIONS]
```

**Arguments:**
- `USERNAME` — Username to retrieve

**Examples:**
```bash
gulp-cli user get alice
```

---

#### `create`

Create a new user.

```bash
gulp-cli user create USERNAME [OPTIONS]
```

**Arguments:**
- `USERNAME` — New username

**Options:**
- `--password TEXT` — Password (prompted if not provided)
- `--admin` — Grant admin privileges
- `--permissions TEXT` — Comma-separated permissions (e.g., `read,write,execute`)

**Examples:**
```bash
gulp-cli user create alice --password secret123
gulp-cli user create bob --password secret456 --admin
gulp-cli user create analyst --password secret789 --permissions read,write
```

---

#### `update`

Update an existing user.

```bash
gulp-cli user update USERNAME [OPTIONS]
```

**Arguments:**
- `USERNAME` — Username to update

**Options:**
- `--password TEXT` — New password
- `--admin` — Set admin status (use `--no-admin` to revoke)
- `--permissions TEXT` — Update permissions

**Examples:**
```bash
gulp-cli user update alice --password newpass123
gulp-cli user update bob --admin
gulp-cli user update alice --permissions read
```

---

#### `delete`

Delete a user.

```bash
gulp-cli user delete USERNAME [OPTIONS]
```

**Arguments:**
- `USERNAME` — Username to delete

**Options:**
- `--confirm` — Skip confirmation prompt

**Examples:**
```bash
gulp-cli user delete alice
gulp-cli user delete alice --confirm
```

---

#### `session-list`

List `GulpUserSession` objects using the dedicated session API.

- Non-admin users can list only their own session.
- Admin users can list all sessions or filter by `--user-id`.

```bash
gulp-cli user session-list [OPTIONS]
```

**Options:**
- `--user-id TEXT` — Optional user filter; admin required for other users

**Examples:**
```bash
gulp-cli user session-list
gulp-cli user session-list --user-id alice
gulp-cli --as-user guest user session-list
```

---

#### `session-delete`

Delete a specific user session using the dedicated session API.

- Non-admin users can delete only their own session.
- Admin users can delete any session.

```bash
gulp-cli user session-delete SESSION_ID [OPTIONS]
```

**Arguments:**
- `SESSION_ID` — Session ID to delete

**Examples:**
```bash
gulp-cli user session-delete abc123def456
gulp-cli --as-user admin user session-delete abc123def456
```

---

## Operation Management (`operation`)

#### `list`

List all operations.

```bash
gulp-cli operation list [OPTIONS]
```

**Options:**
- `--limit INTEGER` — Max results (default: 50)
- `--offset INTEGER` — Offset (default: 0)

**Examples:**
```bash
gulp-cli operation list
gulp-cli operation list --limit 100
```

---

#### `get`

Get operation details.

```bash
gulp-cli operation get OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Operation ID

**Examples:**
```bash
gulp-cli operation get my_investigation
```

---

#### `create`

Create a new operation.

```bash
gulp-cli operation create OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Operation ID (must be unique)

**Options:**
- `--description TEXT` — Operation description
- `--display-name TEXT` — Display name (default: same as operation ID)

**Examples:**
```bash
gulp-cli operation create incident-2026-001 --description "Malware investigation"
gulp-cli operation create my_investigation --display-name "My Investigation"
```

---

#### `update`

Update operation details.

```bash
gulp-cli operation update OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Operation ID

**Options:**
- `--description TEXT` — New description
- `--display-name TEXT` — New display name

**Examples:**
```bash
gulp-cli operation update my_investigation --description "Updated description"
```

---

#### `delete`

Delete an operation.

```bash
gulp-cli operation delete OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Operation ID

**Options:**
- `--confirm` — Skip confirmation

**Examples:**
```bash
gulp-cli operation delete my_investigation --confirm
```

---

#### `grant-user`

Grant user access to an operation.

```bash
gulp-cli operation grant-user OPERATION_ID USERNAME [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Operation ID
- `USERNAME` — Username to grant access

**Examples:**
```bash
gulp-cli operation grant-user my_investigation alice
```

---

#### `revoke-user`

Revoke user access from an operation.

```bash
gulp-cli operation revoke-user OPERATION_ID USERNAME [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Operation ID
- `USERNAME` — Username to revoke access

**Examples:**
```bash
gulp-cli operation revoke-user my_investigation alice
```

---

## Ingestion (`ingest`)

#### `file`

Ingest one or more files into an operation.

```bash
gulp-cli ingest file OPERATION_ID PLUGIN FILE [FILE...] [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation
- `PLUGIN` — Plugin name (e.g., `win_evtx`, `syslog`, `csv`)
- `FILE` — File path or glob pattern (multiple allowed)

**Options:**
- `--context-name TEXT` — Context name used for source grouping (default: `sdk_context`)
- `--plugin-params TEXT` — JSON string with plugin parameters
- `--flt TEXT` — JSON object for `GulpIngestionFilter`
- `--reset-operation` — Delete and recreate the operation before ingest starts
- `--create-operation` — Create operation automatically when it does not exist
- `--preview` — Run preview-only ingestion (no persistence)
- `--wait` — Wait for completion with progress
- `--timeout INTEGER` — Timeout in seconds for `--wait` mode

**Examples:**
```bash
# Single file
gulp-cli ingest file my_op win_evtx /path/to/System.evtx

# Multiple files
gulp-cli ingest file my_op win_evtx /path/file1.evtx /path/file2.evtx

# Wildcard pattern
gulp-cli ingest file my_op win_evtx 'samples/win_evtx/*.evtx'

# Multiple patterns
gulp-cli ingest file my_op win_evtx '**/*.evtx' '/logs/*.json'

# With plugin parameters
gulp-cli ingest file my_op csv file.csv --plugin-params '{"delimiter":";","encoding":"utf-8"}'

# Preview mode (no ingestion persisted)
gulp-cli ingest file my_op win_evtx /path/to/System.evtx --preview

# Reset operation data before ingest (destructive for collab/request data)
gulp-cli ingest file my_op win_evtx 'samples/win_evtx/*.evtx' --reset-operation

# Wait for completion
gulp-cli ingest file my_op win_evtx 'samples/win_evtx/*.evtx' --wait
```

---

#### `file-to-source`

Add files to an existing source.

```bash
gulp-cli ingest file-to-source SOURCE_ID FILE [FILE...] [OPTIONS]
```

**Arguments:**
- `SOURCE_ID` — Source ID
- `FILE` — File path or glob pattern (multiple allowed)

**Options:**
- `--plugin-params TEXT` — JSON object for plugin_params (overrides source defaults)
- `--flt TEXT` — JSON object for GulpIngestionFilter
- `--wait` — Wait for completion with progress
- `--timeout INTEGER` — Timeout in seconds for `--wait` mode

**Examples:**
```bash
gulp-cli ingest file-to-source source123 /new/System.evtx --wait
gulp-cli ingest file-to-source source123 '/new/*.evtx'
```

---

#### `zip`

Ingest from a ZIP archive.

```bash
gulp-cli ingest zip OPERATION_ID ZIP_FILE [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation
- `ZIP_FILE` — Path to ZIP file

**Options:**
- `--context-name TEXT` — Context name used for source grouping (default: `sdk_context`)
- `--flt TEXT` — JSON object for `GulpIngestionFilter`
- `--create-operation` — Create operation automatically when it does not exist
- `--wait` — Wait for completion
- `--timeout INTEGER` — Timeout in seconds for `--wait` mode

**Examples:**
```bash
gulp-cli ingest zip my_op /data/evidence.zip --wait
gulp-cli ingest zip my_op /data/evidence.zip --create-operation
```

---

#### `raw`

Ingest raw payload chunks into an operation.

```bash
gulp-cli ingest raw OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--data TEXT` — Raw payload text (JSON recommended)
- `--data-file TEXT` — Path to file containing raw payload
- `--plugin TEXT` — Plugin used to process the raw payload (default: `raw`)
- `--plugin-params TEXT` — JSON object for `plugin_params`
- `--flt TEXT` — JSON object for `GulpIngestionFilter`
- `--req-id TEXT` — Optional request ID for chunked ingestion
- `--last` — Mark this payload as the last raw chunk
- `--create-operation` — Create operation automatically when it does not exist
- `--wait` — Wait for completion
- `--timeout INTEGER` — Timeout in seconds for `--wait` mode

**Examples:**
```bash
gulp-cli ingest raw my_op --data '[{"id":"doc-1","@timestamp":"2026-01-01T00:00:00Z"}]' --wait
gulp-cli ingest raw my_op --data-file /tmp/raw_chunk.json --last --wait
```

---


## Query (`query`)

#### `raw`

Execute a raw OpenSearch query.

```bash
gulp-cli query raw OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--q TEXT` — OpenSearch query JSON (required)
- `--q-options TEXT` — Query options JSON
- `--preview` — Enable `q_options.preview_mode=true` (synchronous preview result)
- `--limit INTEGER` — Set `q_options.limit`
- `--offset INTEGER` — Set `q_options.offset`
- `--wait` — Wait for query completion

**Examples:**
```bash
# Match all documents
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}'

# Search specific field
gulp-cli query raw my_op --q '{"query":{"term":{"EventID":4688}}}'

# Preview mode (synchronous, limited result set)
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' --preview

# Pagination override
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' --limit 100 --offset 200

# Wait for completion
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' --wait

# Preview mode can also be provided through q-options
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' --q-options '{"preview_mode":true}'
```

---

#### `gulp`

Query using gULP's native document structure.

```bash
gulp-cli query gulp OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--flt TEXT` — Filter JSON
- `--q-options TEXT` — Query options JSON
- `--preview` — Enable `q_options.preview_mode=true` (synchronous preview result)
- `--limit INTEGER` — Set `q_options.limit`
- `--offset INTEGER` — Set `q_options.offset`
- `--wait` — Wait for completion

**Examples:**
```bash
# Get documents with default options
gulp-cli query gulp my_op

# Filter by source
gulp-cli query gulp my_op --flt '{"source_ids":["security"]}'

# Filter by tag
gulp-cli query gulp my_op --flt '{"tags":["suspicious"]}'

# Preview mode
gulp-cli query gulp my_op --flt '{"tags":["suspicious"]}' --preview

# Pagination override
gulp-cli query gulp my_op --flt '{"tags":["suspicious"]}' --limit 200 --offset 400
```

---

#### `document-get-by-id`

Get a single document by OpenSearch `_id`.

```bash
gulp-cli query document-get-by-id OPERATION_ID DOC_ID
```

**Arguments:**
- `OPERATION_ID` — Target operation
- `DOC_ID` — Document `_id`

**Examples:**
```bash
gulp-cli query document-get-by-id incident-001 AVY84pUBM0e5DCHhCzDq
```

---

#### `aggregation`

Run a synchronous OpenSearch aggregation query.

```bash
gulp-cli query aggregation OPERATION_ID --q JSON
```

**Options:**
- `--q TEXT` — Aggregation query JSON object (required)

**Examples:**
```bash
gulp-cli query aggregation incident-001 \
  --q '{"size":0,"aggs":{"by_event_code":{"terms":{"field":"event.code"}}}}'
```

---

#### `history-get`

Get query history for the authenticated user.

```bash
gulp-cli query history-get
```

**Examples:**
```bash
gulp-cli query history-get
```

---

#### `max-min-per-field`

Get max/min timeline values (`@timestamp`, `gulp.timestamp`, `event.code`) with optional grouping.

```bash
gulp-cli query max-min-per-field OPERATION_ID [OPTIONS]
```

**Options:**
- `--flt TEXT` — `GulpQueryFilter` JSON object
- `--group-by TEXT` — Optional group-by field (for example: `event.code`)

**Examples:**
```bash
gulp-cli query max-min-per-field incident-001
gulp-cli query max-min-per-field incident-001 --group-by event.code
gulp-cli query max-min-per-field incident-001 --flt '{"source_ids":["security"]}'
```

---

#### `gulp-export`

Export `query_gulp` results to a local JSON file (streamed download).

```bash
gulp-cli query gulp-export OPERATION_ID --output PATH [OPTIONS]
```

**Options:**
- `--output TEXT` — Output file path (required)
- `--flt TEXT` — `GulpQueryFilter` JSON object
- `--q-options TEXT` — `GulpQueryParameters` JSON object
- `--preview` — Set `q_options.preview_mode` (ignored server-side by export API)
- `--limit INTEGER` — Set `q_options.limit`
- `--offset INTEGER` — Set `q_options.offset`

**Examples:**
```bash
gulp-cli query gulp-export incident-001 \
  --flt '{"source_ids":["security"]}' \
  --output ./incident-001-security.json
```

---

#### `sigma`

Execute Sigma rule against documents.

```bash
gulp-cli query sigma OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--rule-file TEXT` — Path to Sigma YAML rule file (required)
- `--src-ids TEXT` — Comma-separated source IDs to query
- `--levels TEXT` — Comma-separated severity levels (critical, high, medium, low)
- `--wait` — Wait for completion
- `--timeout INTEGER` — Timeout in seconds

**Examples:**
```bash
# Run Sigma rule
gulp-cli query sigma my_op --rule-file /rules/process_creation.yml

# Filter by source
gulp-cli query sigma my_op --rule-file /rules/process_creation.yml --src-ids windows

# Filter by severity
gulp-cli query sigma my_op --rule-file /rules/process_creation.yml --levels critical,high

# Wait for completion
gulp-cli query sigma my_op --rule-file /rules/process_creation.yml --wait
```

---

#### `sigma-zip`

Execute Sigma rules from a ZIP archive (extension command).

```bash
gulp-cli query sigma-zip OPERATION_ID --zip-file PATH [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--zip-file TEXT` — Path to ZIP archive containing Sigma YAML rules (required)
- `--src-ids TEXT` — Comma-separated source IDs
- `--levels TEXT` — Comma-separated severity levels (`critical,high,medium,low,informational`)
- `--tags TEXT` — Comma-separated sigma tags
- `--products TEXT` — Comma-separated sigma logsource products
- `--categories TEXT` — Comma-separated sigma logsource categories
- `--services TEXT` — Comma-separated sigma logsource services
- `--q-options TEXT` — `GulpQueryParameters` JSON object
- `--wait` — Wait for completion
- `--timeout INTEGER` — Wait timeout in seconds (`0` means no timeout)

**Examples:**
```bash
# Query using zipped Sigma rules
gulp-cli query sigma-zip incident-001 --zip-file /rules/windows_small.zip

# Restrict to selected source and levels
gulp-cli query sigma-zip incident-001 \
  --zip-file /rules/windows_small.zip \
  --src-ids security \
  --levels critical,high \
  --wait

# Add q_options for paging or highlighting behavior
gulp-cli query sigma-zip incident-001 \
  --zip-file /rules/windows_small.zip \
  --q-options '{"limit":200,"highlight_results":false}'
```

---

#### `external`

Query using an external plugin.

```bash
gulp-cli query external OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--plugin TEXT` — Plugin name (required)
- `--q TEXT` — Query payload (JSON or plain text)
- `--plugin-params TEXT` — `GulpPluginParameters` JSON object (required)
- `--q-options TEXT` — `GulpQueryParameters` JSON object
- `--preview` — Enable `q_options.preview_mode=true`
- `--limit INTEGER` — Set `q_options.limit`
- `--offset INTEGER` — Set `q_options.offset`
- `--wait` — Wait for completion

**Examples:**
```bash
gulp-cli query external my_op \
  --plugin query_elasticsearch \
  --plugin-params '{"custom_parameters":{"index":"my_index"}}' \
  --q '{"query":{"match_all":{}}}'

# Preview + pagination
gulp-cli query external my_op \
  --plugin query_elasticsearch \
  --plugin-params '{"custom_parameters":{"index":"my_index"}}' \
  --q '{"query":{"match":{"message":"error"}}}' \
  --preview --limit 50 --offset 0
```

---

## Dynamic Extensions

gulp-cli can load custom commands from extension modules discovered at startup.

- Internal path: `src/gulp_cli/extension/`
- External path: `~/.config/gulp-cli/extension/`
- External modules override internal ones when they share the same filename.

Each extension module must expose a callable `register_extension` function.

For implementation details and examples, see `docs/extensions.md`.

---

## Request Stats (`stats`)

#### `get`

Get one `GulpRequestStats` object by request id.

```bash
gulp-cli stats get REQ_ID [OPTIONS]
```

**Options:**

**Examples:**
```bash
gulp-cli stats get 903546ff-c01e-4875-a585-d7fa34a0d237
gulp-cli --verbose --as-user admin stats get 903546ff-c01e-4875-a585-d7fa34a0d237
```

---

#### `list`

List `GulpRequestStats` for an operation.

```bash
gulp-cli stats list OPERATION_ID [OPTIONS]
```

**Default behavior:**
- Shows only ongoing stats (`--ongoing-only` enabled)
- Renders a live table (`--live` enabled)
- Default columns: `user_id`, `ws_id`, `req_id`, `status`, `req_type`, `time_updated`, `data`, `errors`

**Options:**
- `--ongoing-only / --all` — Show only ongoing (default) or all stats
- `--user-id TEXT` — Filter by user id
- `--req-type TEXT` — Filter by request type (for example: `ingest`, `query`, `enrich`)
- `--server-id TEXT` — Filter by server id
- `--time-created-from TEXT` — Include stats created at/after timestamp (epoch sec/ms or ISO8601)
- `--time-created-to TEXT` — Include stats created at/before timestamp (epoch sec/ms or ISO8601)
- `--errors [any|present|absent]` — Filter by error presence (default: `any`)
- `--live / --no-live` — Enable or disable live refresh
- `--refresh-seconds FLOAT` — Live refresh interval (default: `1.0`)
- `--limit INTEGER` — Max rows to render (default: `100`)

**Examples:**
```bash
# Default: ongoing-only + live refresh
gulp-cli stats list incident-001

# Show all stats once (no live refresh)
gulp-cli stats list incident-001 --all --no-live

# Only stats with errors
gulp-cli stats list incident-001 --all --errors present --no-live

# Only stats without errors
gulp-cli stats list incident-001 --all --errors absent --no-live

# Filter by user and request type
gulp-cli stats list incident-001 --all --user-id admin --req-type ingest

# Filter by server id
gulp-cli stats list incident-001 --all --server-id my-server-1 --no-live

# Filter by creation time window (ISO8601)
gulp-cli stats list incident-001 --all \
  --time-created-from '2026-03-27T00:00:00Z' \
  --time-created-to '2026-03-27T23:59:59Z' \
  --no-live

# Faster live refresh while monitoring active ingestion
gulp-cli stats list incident-001 --refresh-seconds 0.5
```

---

#### `delete-bulk`

Delete request stats using the server-side `object_delete_bulk` API.

```bash
gulp-cli stats delete-bulk OPERATION_ID [OPTIONS]
```

**Important:**
- You must provide `--flt` or explicitly pass `--all`.

**Options:**
- `--flt TEXT` — `GulpCollabFilter` JSON object
- `--all` — Delete all request stats in the operation

**Examples:**
```bash
# Delete stats of a specific type
gulp-cli stats delete-bulk incident-001 \
  --flt '{"types":["request_stats"],"user_ids":["admin"]}'

# Delete all request stats in the operation
gulp-cli stats delete-bulk incident-001 --all
```

---

#### `cancel`

Cancel a running request using the server-side `request_cancel` API.

```bash
gulp-cli stats cancel REQ_ID [OPTIONS]
```

**Options:**
- `--expire-now` — Immediately expire and delete the request stats entry after cancellation

**Examples:**
```bash
# Cancel request and keep default grace period before cleanup
gulp-cli stats cancel 903546ff-c01e-4875-a585-d7fa34a0d237

# Cancel and remove stats immediately
gulp-cli stats cancel 903546ff-c01e-4875-a585-d7fa34a0d237 --expire-now
```

---

## Database (`db`)

#### `rebase-by-query`

Rebase document timestamps in-place using the server-side `rebase_by_query` API.

```bash
gulp-cli db rebase-by-query OPERATION_ID --offset-msec OFFSET [OPTIONS]
```

**Options:**
- `--offset-msec INTEGER` — Milliseconds to add to timestamps (negative to subtract)
- `--flt TEXT` — `GulpQueryFilter` JSON object to restrict documents
- `--script TEXT` — Custom Painless script override
- `--wait` — Wait for completion with websocket-driven progress
- `--timeout INTEGER` — Timeout in seconds when `--wait` is used

**Examples:**
```bash
# Shift all documents forward by one hour
gulp-cli db rebase-by-query incident-001 --offset-msec 3600000 --wait

# Shift only Security-source documents backward by five minutes
gulp-cli db rebase-by-query incident-001 \
  --offset-msec -300000 \
  --flt '{"source_ids":["security"]}' \
  --wait

# Use a custom script
gulp-cli db rebase-by-query incident-001 \
  --offset-msec 0 \
  --script 'ctx._source["custom_ts"] = params.now;'
```

---

## Enrichment & Tagging (`enrich`)

#### `tag`

Add tags to documents matching a filter.

```bash
gulp-cli enrich tag OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--flt TEXT` — Filter JSON (required)
- `--tag TEXT` — Tag to add (multiple allowed, at least one required)
- `--wait` — Wait for completion

**Examples:**
```bash
# Add single tag
gulp-cli enrich tag my_op --flt '{"source":"Security"}' --tag "reviewed"

# Add multiple tags
gulp-cli enrich tag my_op \
  --flt '{"event_id":"4688"}' \
  --tag "suspicious" \
  --tag "requires-review" \
  --tag "process-creation"
```

---

#### `untag`

Remove tags from documents.

```bash
gulp-cli enrich untag OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--flt TEXT` — Filter JSON (required)
- `--tag TEXT` — Tag to remove (multiple allowed)
- `--wait` — Wait for completion

**Examples:**
```bash
gulp-cli enrich untag my_op --flt '{"tag":"pending"}' --tag "pending"
```

---

#### `update`

Update field values on documents.

```bash
gulp-cli enrich update OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--flt TEXT` — Filter JSON (required)
- `--fields TEXT` — Fields JSON to update (required)
- `--wait` — Wait for completion

**Examples:**
```bash
# Set threat level
gulp-cli enrich update my_op \
  --flt '{"event_id":"4688"}' \
  --fields '{"threat_level":"high"}'
```

---

#### `remove`

Remove fields from documents.

```bash
gulp-cli enrich remove OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--flt TEXT` — Filter JSON (required)
- `--fields TEXT` — Field names to remove (comma-separated)
- `--wait` — Wait for completion

**Examples:**
```bash
gulp-cli enrich remove my_op \
  --flt '{"done":true}' \
  --fields "temporary_field,debug_info"
```

---

#### `documents`

Run enrichment plugin on documents matching a filter.

```bash
gulp-cli enrich documents OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--plugin TEXT` — Plugin name (required)
- `--plugin-params TEXT` — Plugin parameters JSON
- `--flt TEXT` — Filter JSON
- `--wait` — Wait for completion

**Examples:**
```bash
gulp-cli enrich documents my_op \
  --plugin my_enricher \
  --plugin-params '{"api_key":"..."}'  \
  --flt '{"enriched":false}'
```

---

#### `single-id`

Enrich a single document by ID.

```bash
gulp-cli enrich single-id OPERATION_ID DOCUMENT_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation
- `DOCUMENT_ID` — Document ID

**Options:**
- `--plugin TEXT` — Plugin name (required)
- `--plugin-params TEXT` — Plugin parameters JSON
- `--wait` — Wait for completion

**Examples:**
```bash
gulp-cli enrich single-id my_op doc123 --plugin my_enricher
```

---

## Collaboration Objects (`collab`)

Manage collaboration objects attached to an operation: notes, links, and highlights.

#### `note list`

List notes in operation.

```bash
gulp-cli collab note list OPERATION_ID [OPTIONS]
```

**Options:**

**Default columns:**
- `id`, `operation_id`, `user_id`, `server_id`, `context_id`, `source_id`, `time_pin`, `text`

**Examples:**
```bash
gulp-cli collab note list incident-001
gulp-cli --verbose collab note list incident-001
```

---

#### `note create`

Create a note for a specific context/source.

```bash
gulp-cli collab note create OPERATION_ID CONTEXT_ID SOURCE_ID NAME TEXT [OPTIONS]
```

**Important:**
- At least one of `--time-pin` or `--doc` is required.

**Options:**
- `--tags TEXT` — Comma-separated tags
- `--glyph-id TEXT` — Glyph ID
- `--color TEXT` — Color string
- `--private` — Create the note as private
- `--time-pin INTEGER` — Time pin in nanoseconds
- `--doc TEXT` — JSON object for associated document

**Examples:**
```bash
# Time-pinned note
gulp-cli collab note create incident-001 sdk_context security "Analyst note" "Suspicious login spike" \
  --time-pin 1774626000000000000 \
  --tags suspicious,review

# Document-associated note
gulp-cli collab note create incident-001 sdk_context security "IOC note" "Check parent process" \
  --doc '{"_id":"doc-123","gulp.operation_id":"incident-001","gulp.source_id":"security"}'
```

---

#### `note update`

Update an existing note.

```bash
gulp-cli collab note update NOTE_ID [OPTIONS]
```

**Options:**
- `--name TEXT` — Update note name
- `--text TEXT` — Update note text
- `--tags TEXT` — Replace tags with comma-separated values
- `--glyph-id TEXT` — Update glyph ID
- `--color TEXT` — Update color
- `--time-pin INTEGER` — Update time pin in nanoseconds
- `--doc TEXT` — Replace associated document with JSON object

**Examples:**
```bash
gulp-cli collab note update note-123 --text "Updated note text" --tags reviewed,done
gulp-cli collab note update note-123 --time-pin 1774627000000000000
```

---

#### `note delete`

Delete a note.

```bash
gulp-cli collab note delete NOTE_ID
```

**Examples:**
```bash
gulp-cli collab note delete note-123
```

---

#### `note delete-bulk`

Delete multiple notes in an operation using the server-side `object_delete_bulk` API.

```bash
gulp-cli collab note delete-bulk OPERATION_ID [OPTIONS]
```

**Important:**
- You must provide `--flt` or explicitly pass `--all`.

**Options:**
- `--flt TEXT` — `GulpCollabFilter` JSON object
- `--all` — Delete all notes in the operation

**Examples:**
```bash
# Delete notes by source and tag
gulp-cli collab note delete-bulk incident-001 \
  --flt '{"source_ids":["security"],"tags":["reviewed"]}'

# Delete all notes in the operation
gulp-cli collab note delete-bulk incident-001 --all
```

---

#### `link list`

List links in operation.

```bash
gulp-cli collab link list OPERATION_ID [OPTIONS]
```


**Default columns:**
- `id`, `operation_id`, `user_id`, `server_id`, `doc_id_from`, `doc_ids`

**Examples:**
```bash
gulp-cli collab link list incident-001
gulp-cli --verbose collab link list incident-001
```

---

#### `link create`

Create a link from one document to one or more target documents.

```bash
gulp-cli collab link create OPERATION_ID DOC_ID_FROM --doc-ids DOC1,DOC2 [OPTIONS]
```

**Options:**
- `--name TEXT` — Link name
- `--description TEXT` — Link description
- `--tags TEXT` — Comma-separated tags
- `--glyph-id TEXT` — Glyph ID
- `--color TEXT` — Color string
- `--private` — Create the link as private

**Examples:**
```bash
gulp-cli collab link create incident-001 doc-a --doc-ids doc-b,doc-c \
  --name "lateral movement" \
  --description "Documents connected by same process tree"
```

---

#### `link update`

Update an existing link.

```bash
gulp-cli collab link update LINK_ID [OPTIONS]
```

**Options:**
- `--name TEXT` — Update link name
- `--description TEXT` — Update description
- `--tags TEXT` — Replace tags with comma-separated values
- `--glyph-id TEXT` — Update glyph ID
- `--color TEXT` — Update color
- `--doc-ids TEXT` — Replace target document IDs with comma-separated values

**Examples:**
```bash
gulp-cli collab link update link-123 --description "Updated correlation rationale"
gulp-cli collab link update link-123 --doc-ids doc-b,doc-d
```

---

#### `link delete`

Delete a link.

```bash
gulp-cli collab link delete LINK_ID
```

**Examples:**
```bash
gulp-cli collab link delete link-123
```

---

#### `link delete-bulk`

Delete multiple links in an operation using the server-side `object_delete_bulk` API.

```bash
gulp-cli collab link delete-bulk OPERATION_ID [OPTIONS]
```

**Important:**
- You must provide `--flt` or explicitly pass `--all`.

**Options:**
- `--flt TEXT` — `GulpCollabFilter` JSON object
- `--all` — Delete all links in the operation

**Examples:**
```bash
# Delete links that involve a specific document id
gulp-cli collab link delete-bulk incident-001 \
  --flt '{"doc_ids":["doc-a"]}'

# Delete all links in the operation
gulp-cli collab link delete-bulk incident-001 --all
```

---

#### `highlight list`

List highlights in operation.

```bash
gulp-cli collab highlight list OPERATION_ID [OPTIONS]
```


**Default columns:**
- `id`, `operation_id`, `user_id`, `server_id`, `time_range`

**Examples:**
```bash
gulp-cli collab highlight list incident-001
gulp-cli --verbose collab highlight list incident-001
```

---

#### `highlight create`

Create a highlight over a time range.

```bash
gulp-cli collab highlight create OPERATION_ID --time-range START_NS,END_NS [OPTIONS]
```

**Options:**
- `--name TEXT` — Highlight name
- `--description TEXT` — Description
- `--tags TEXT` — Comma-separated tags
- `--glyph-id TEXT` — Glyph ID
- `--color TEXT` — Color string
- `--private` — Create the highlight as private

**Examples:**
```bash
gulp-cli collab highlight create incident-001 \
  --time-range 1774626000000000000,1774626060000000000 \
  --name "Burst of activity" \
  --color red
```

---

#### `highlight update`

Update an existing highlight.

```bash
gulp-cli collab highlight update HIGHLIGHT_ID [OPTIONS]
```

**Options:**
- `--name TEXT` — Update highlight name
- `--description TEXT` — Update description
- `--tags TEXT` — Replace tags with comma-separated values
- `--glyph-id TEXT` — Update glyph ID
- `--color TEXT` — Update color
- `--time-range TEXT` — Replace time range using `START_NS,END_NS`

**Examples:**
```bash
gulp-cli collab highlight update hl-123 --time-range 1774626000000000000,1774626120000000000
gulp-cli collab highlight update hl-123 --description "Expanded reviewed window"
```

---

#### `highlight delete`

Delete a highlight.

```bash
gulp-cli collab highlight delete HIGHLIGHT_ID
```

**Examples:**
```bash
gulp-cli collab highlight delete hl-123
```

---

#### `highlight delete-bulk`

Delete multiple highlights in an operation using the server-side `object_delete_bulk` API.

```bash
gulp-cli collab highlight delete-bulk OPERATION_ID [OPTIONS]
```

**Important:**
- You must provide `--flt` or explicitly pass `--all`.

**Options:**
- `--flt TEXT` — `GulpCollabFilter` JSON object
- `--all` — Delete all highlights in the operation

**Examples:**
```bash
# Delete highlights in a creation-time window
gulp-cli collab highlight delete-bulk incident-001 \
  --flt '{"time_created_range":[1774626000000,1774629600000]}'

# Delete all highlights in the operation
gulp-cli collab highlight delete-bulk incident-001 --all
```

---

#### `story` (extension)

Story management commands provided by the `story` extension plugin.

```bash
gulp-cli collab story [COMMAND]
```

**Commands:**
- `create` — Create a story object
- `update` — Update an existing story
- `delete` — Delete a story by id
- `get` — Retrieve a story by id
- `list` — List stories for an operation

---

#### `story create` (extension)

```bash
gulp-cli collab story create OPERATION_ID --name TEXT --doc-ids DOC1,DOC2 [OPTIONS]
```

**Options:**
- `--highlight-ids TEXT` — Comma-separated highlight IDs
- `--include-whole-documents` — Include all document fields in each story entry
- `--description TEXT` — Story description
- `--tags TEXT` — Comma-separated tags
- `--glyph-id TEXT` — Glyph ID
- `--color TEXT` — Color string
- `--private` — Create as private object
- `--wait` — Wait for completion if endpoint returns pending
- `--timeout INTEGER` — Wait timeout in seconds (`0` means no timeout)

**Examples:**
```bash
gulp-cli collab story create incident-001 \
  --name "Executive summary" \
  --doc-ids doc-a,doc-b \
  --highlight-ids hl-1,hl-2
```

---

#### `story update` (extension)

```bash
gulp-cli collab story update STORY_ID [OPTIONS]
```

**Options:**
- `--name TEXT` — Update story title
- `--doc-ids TEXT` — Replace target document IDs
- `--highlight-ids TEXT` — Replace highlight IDs
- `--include-whole-documents` — Include all document fields in each story entry
- `--description TEXT` — Update description
- `--tags TEXT` — Replace tags
- `--glyph-id TEXT` — Update glyph ID
- `--color TEXT` — Update color
- `--wait` — Wait for completion if endpoint returns pending
- `--timeout INTEGER` — Wait timeout in seconds (`0` means no timeout)

---

#### `story delete` (extension)

```bash
gulp-cli collab story delete STORY_ID [OPTIONS]
```

**Options:**
- `--wait` — Wait for completion if endpoint returns pending
- `--timeout INTEGER` — Wait timeout in seconds (`0` means no timeout)

---

#### `story get` (extension)

```bash
gulp-cli collab story get OPERATION_ID STORY_ID
```

---

#### `story list` (extension)

```bash
gulp-cli collab story list OPERATION_ID [OPTIONS]
```

**Options:**
- `--flt TEXT` — `GulpCollabFilter` JSON object

**Examples:**
```bash
gulp-cli collab story list incident-001
gulp-cli collab story list incident-001 --flt '{"tags":["executive"]}'
```

---

#### `db list-indexes`

List all OpenSearch datastreams/indexes (admin required).

```bash
gulp-cli db list-indexes [OPTIONS]
```

**Examples:**
```bash
gulp-cli db list-indexes
gulp-cli --verbose db list-indexes
```

---

#### `db refresh-index`

Refresh an OpenSearch index so newly ingested documents become searchable (ingest permission required).

```bash
gulp-cli db refresh-index INDEX
```

**Arguments:**
- `INDEX` — Index / datastream name (usually the operation ID)

**Examples:**
```bash
gulp-cli db refresh-index incident-001
```

---

#### `db delete-index`

Delete an OpenSearch datastream/index and (by default) its associated collab operation.

**WARNING:** all document data in the index will be permanently lost.

```bash
gulp-cli db delete-index INDEX [OPTIONS]
```

**Arguments:**
- `INDEX` — Index / datastream name

**Options:**
- `--keep-operation` — Do NOT delete the corresponding collab operation
- `--yes / -y` — Skip the confirmation prompt

**Examples:**
```bash
# Interactive confirmation
gulp-cli db delete-index incident-001

# Delete index only, keep the operation
gulp-cli db delete-index incident-001 --keep-operation --yes

# Non-interactive (CI/scripts)
gulp-cli db delete-index incident-001 --yes
```

---

## User Group Management (`user-group`)

All commands require **admin** permission.

#### `user-group list`

List user groups.

```bash
gulp-cli user-group list [OPTIONS]
```

**Options:**
- `--flt TEXT` — `GulpCollabFilter` JSON for filtering

**Examples:**
```bash
gulp-cli user-group list
gulp-cli user-group list --verbose
gulp-cli user-group list --flt '{"names":["analysts"]}'
```

---

#### `user-group get`

Get a user group by ID.

```bash
gulp-cli user-group get GROUP_ID
```

**Examples:**
```bash
gulp-cli user-group get analysts
```

---

#### `user-group create`

Create a new user group.

```bash
gulp-cli user-group create NAME --permission PERMS [OPTIONS]
```

**Arguments:**
- `NAME` — Group name (also used as ID)

**Options:**
- `--permission TEXT` — Comma-separated permissions: `read`, `edit`, `ingest`, `admin` (required)
- `--description / -d TEXT` — Optional description
- `--glyph-id TEXT` — Optional glyph ID

**Examples:**
```bash
gulp-cli user-group create analysts --permission read,edit
gulp-cli user-group create ingestors --permission read,edit,ingest --description "Can run ingestion"
```

---

#### `user-group update`

Update a user group's properties.

```bash
gulp-cli user-group update GROUP_ID [OPTIONS]
```

**Options:**
- `--permission TEXT` — New comma-separated permissions
- `--description / -d TEXT` — New description
- `--glyph-id TEXT` — New glyph ID

**Examples:**
```bash
gulp-cli user-group update analysts --permission read,edit,ingest
gulp-cli user-group update analysts --description "Read + edit + ingest access"
```

---

#### `user-group delete`

Delete a user group. Members are **not** deleted.

```bash
gulp-cli user-group delete GROUP_ID
```

**Examples:**
```bash
gulp-cli user-group delete analysts
```

---

#### `user-group add-user`

Add a user to a group.

```bash
gulp-cli user-group add-user GROUP_ID USER_ID
```

**Examples:**
```bash
gulp-cli user-group add-user analysts alice
```

---

#### `user-group remove-user`

Remove a user from a group.

```bash
gulp-cli user-group remove-user GROUP_ID USER_ID
```

**Examples:**
```bash
gulp-cli user-group remove-user analysts alice
```

---

## Object ACL Management (`acl`)

Manage access control for collaboration objects. The caller must be the object **owner** or have **admin** permission.

#### `acl add-user`

Grant a specific user access to an object.

```bash
gulp-cli acl add-user OBJ_ID --obj-type TYPE --user-id USER_ID
```

**Arguments:**
- `OBJ_ID` — ID of the object

**Options:**
- `--obj-type TEXT` — Object collab type (e.g. `note`, `operation`, `link`, `highlight`) (required)
- `--user-id TEXT` — User ID to grant access (required)

**Examples:**
```bash
gulp-cli acl add-user note-123 --obj-type note --user-id alice
gulp-cli acl add-user incident-001 --obj-type operation --user-id alice
```

---

#### `acl remove-user`

Revoke a user's access to an object.

```bash
gulp-cli acl remove-user OBJ_ID --obj-type TYPE --user-id USER_ID
```

**Examples:**
```bash
gulp-cli acl remove-user note-123 --obj-type note --user-id alice
```

---

#### `acl add-group`

Grant a group access to an object.

```bash
gulp-cli acl add-group OBJ_ID --obj-type TYPE --group-id GROUP_ID
```

**Options:**
- `--obj-type TEXT` — Object collab type (required)
- `--group-id TEXT` — Group ID to grant access (required)

**Examples:**
```bash
gulp-cli acl add-group incident-001 --obj-type operation --group-id analysts
gulp-cli acl add-group note-123 --obj-type note --group-id analysts
```

---

#### `acl remove-group`

Revoke a group's access to an object.

```bash
gulp-cli acl remove-group OBJ_ID --obj-type TYPE --group-id GROUP_ID
```

**Examples:**
```bash
gulp-cli acl remove-group incident-001 --obj-type operation --group-id analysts
```

---

#### `acl make-private`

Make an object private. Only the owner and admins will be able to access it.

```bash
gulp-cli acl make-private OBJ_ID --obj-type TYPE
```

**Examples:**
```bash
gulp-cli acl make-private note-123 --obj-type note
gulp-cli acl make-private link-456 --obj-type link
```

---

#### `acl make-public`

Make an object public (accessible by everyone). Clears all explicit grants.

```bash
gulp-cli acl make-public OBJ_ID --obj-type TYPE
```

**Examples:**
```bash
gulp-cli acl make-public note-123 --obj-type note
```

---

## Storage Management (`storage`)

Manage files on the S3-compatible filestore.

#### `storage list-files`

List files from storage, optionally filtered by operation/context.

```bash
gulp-cli storage list-files [OPTIONS]
```

**Options:**
- `--operation-id TEXT` — Filter by operation ID
- `--context-id TEXT` — Filter by context ID
- `--continuation-token TEXT` — Pagination token from previous response
- `--max-results INTEGER` — Results per page (default: `100`, max: `1000`)

**Examples:**
```bash
# List files for one operation
gulp-cli storage list-files --operation-id incident-001

# Paginate next page
gulp-cli storage list-files --operation-id incident-001 --continuation-token abc123

# Global list (admin)
gulp-cli storage list-files --verbose
```

---

#### `storage get-file`

Download a file by storage ID.

```bash
gulp-cli storage get-file OPERATION_ID STORAGE_ID --output PATH
```

**Arguments:**
- `OPERATION_ID` — Operation ID used for permission check
- `STORAGE_ID` — Storage ID (`gulp.storage_id`)

**Options:**
- `--output TEXT` — Local output file path (required)

**Examples:**
```bash
gulp-cli storage get-file incident-001 \
  incident-001/context-a/source-security/System.evtx \
  --output ./downloads/System.evtx
```

---

#### `storage delete-by-id`

Delete a single storage file by storage ID.

```bash
gulp-cli storage delete-by-id OPERATION_ID STORAGE_ID
```

**Examples:**
```bash
gulp-cli storage delete-by-id incident-001 \
  incident-001/context-a/source-security/System.evtx
```

---

#### `storage delete-by-tags`

Delete storage files by operation/context tags.

```bash
gulp-cli storage delete-by-tags [OPTIONS]
```

**Important:**
- Provide at least one filter (`--operation-id` and/or `--context-id`) or explicitly pass `--all`.

**Options:**
- `--operation-id TEXT` — Filter by operation ID
- `--context-id TEXT` — Filter by context ID
- `--all` — Delete across all operations/contexts
- `--yes / -y` — Skip confirmation prompt when using `--all`

**Examples:**
```bash
# Delete all files in one operation
gulp-cli storage delete-by-tags --operation-id incident-001

# Delete by operation + context
gulp-cli storage delete-by-tags --operation-id incident-001 --context-id sdk_context

# Global delete (dangerous)
gulp-cli storage delete-by-tags --all --yes
```

---

## Plugin & Mapping Management

#### `plugin list`

List all plugins.

```bash
gulp-cli plugin list [OPTIONS]
```

**Options:**
- `--plugin-type [extension|external|ingestion|enrichment]` — Filter plugins by functional type

**Examples:**
```bash
# List only ingestion plugins
gulp-cli plugin list --plugin-type ingestion

# List only enrichment plugins
gulp-cli plugin list --plugin-type enrichment

# List only extension plugins
gulp-cli plugin list --plugin-type extension

# List only external/query plugins
gulp-cli plugin list --plugin-type external
```

#### `plugin list-ui`

List UI plugins.

```bash
gulp-cli plugin list-ui [OPTIONS]
```

---

#### `plugin upload`

Upload a new plugin.

```bash
gulp-cli plugin upload PLUGIN_FILE [OPTIONS]
```

#### `plugin download`

Download a plugin.

```bash
gulp-cli plugin download FILENAME OUTPUT_PATH [OPTIONS]
```

#### `plugin delete`

Delete a plugin.

```bash
gulp-cli plugin delete FILENAME [OPTIONS]
```

---

#### `mapping list`

List all mapping files.

```bash
gulp-cli mapping list [OPTIONS]
```

#### `mapping upload`

Upload a mapping file.

```bash
gulp-cli mapping upload FILE_PATH [OPTIONS]
```

#### `mapping download`

Download a mapping file.

```bash
gulp-cli mapping download FILENAME OUTPUT_PATH [OPTIONS]
```

#### `mapping delete`

Delete a mapping file.

```bash
gulp-cli mapping delete FILENAME [OPTIONS]
```

---

## Enhance Map Management (`enhance-map`)

Map document field criteria per plugin to a glyph and/or color used by the UI. Criteria can be simple values for exact matches or operator dicts for numeric comparisons.

#### `enhance-map create`

```bash
gulp-cli enhance-map create PLUGIN MATCH_CRITERIA [--glyph-id GLYPH_ID] [--color COLOR]
```

Where `MATCH_CRITERIA` is a JSON dict mapping document field names to criteria values:
- Simple values for exact match: `'{"field":"value"}'`
- Operator dicts for numeric comparisons: `'{"field":{"eq":value}}'`, `'{"field":{"gte":min,"lte":max}}'`
- Multiple criteria (all must match): `'{"field1":"value","field2":{"gte":10}}'`

Examples:
```bash
gulp-cli enhance-map create win_evtx '{"gulp.event_code":{"eq":4624}}' --glyph-id logon_glyph
gulp-cli enhance-map create win_evtx '{"severity":{"gte":7,"lte":10}}' --color "#ff0000"
```

#### `enhance-map update`

```bash
gulp-cli enhance-map update OBJ_ID [--glyph-id GLYPH_ID] [--color COLOR]
```

#### `enhance-map delete`

```bash
gulp-cli enhance-map delete OBJ_ID
```

#### `enhance-map get`

```bash
gulp-cli enhance-map get OBJ_ID
```

#### `enhance-map list`

```bash
gulp-cli enhance-map list [--flt '{"plugin":"win_evtx"}']
```

---

## Glyph Management (`glyph`)

Create and manage glyph objects used in collaboration and enhance mappings.

#### `glyph create`

```bash
gulp-cli glyph create [--img-path ./icon.png] [--name GLYPH_NAME] [--private]
```

#### `glyph update`

```bash
gulp-cli glyph update OBJ_ID [--name NEW_NAME] [--img-path ./icon_new.png]
```

#### `glyph delete`

```bash
gulp-cli glyph delete OBJ_ID
```

#### `glyph get`

```bash
gulp-cli glyph get OBJ_ID
```

#### `glyph list`

```bash
gulp-cli glyph list [--flt '{"private":false}']
```

---

## See Also

- [Getting Started Guide](getting-started.md)
- [Practical Examples](examples.md)
- [Troubleshooting](troubleshooting-cli.md)
