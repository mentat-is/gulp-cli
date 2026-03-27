# gulp-cli Command Reference

Complete documentation of all available gulp-cli commands and options.

---

## Guide

Commands are organized hierarchically (e.g., `gulp-cli auth login`). This reference uses the format:

```
gulp-cli <group> <command> [OPTIONS] [ARGUMENTS]
```

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
gulp-cli auth login  # Prompts for missing values
```

---

#### `logout`

Clear stored authentication token.

```bash
gulp-cli auth logout [OPTIONS]
```

**Options:**
- `--config-dir TEXT` — Config directory override

**Examples:**
```bash
gulp-cli auth logout
```

---

#### `whoami`

Display current authenticated user info.

```bash
gulp-cli auth whoami [OPTIONS]
```

**Options:**
- `--config-dir TEXT` — Config directory override

**Examples:**
```bash
gulp-cli auth whoami
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

#### `session-delete`

Delete a specific user session.

```bash
gulp-cli user session-delete USERNAME SESSION_ID [OPTIONS]
```

**Arguments:**
- `USERNAME` — Username
- `SESSION_ID` — Session ID to delete

**Examples:**
```bash
gulp-cli user session-delete alice abc123def456
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
- `--plugin-params TEXT` — JSON string with plugin parameters
- `--source-id TEXT` — Add to existing source (optional)
- `--wait` — Wait for completion with progress
- `--timeout INTEGER` — Timeout in seconds (default: 3600)

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

# Wait for completion
gulp-cli ingest file my_op win_evtx 'samples/win_evtx/*.evtx' --wait
```

---

#### `file-to-source`

Add files to an existing source.

```bash
gulp-cli ingest file-to-source OPERATION_ID SOURCE_ID PLUGIN FILE [FILE...] [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation
- `SOURCE_ID` — Source ID
- `PLUGIN` — Plugin name
- `FILE` — File path

**Options:**
- `--plugin-params TEXT` — JSON plugin parameters
- `--wait` — Wait for completion

**Examples:**
```bash
gulp-cli ingest file-to-source my_op source123 win_evtx /new/System.evtx --wait
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
- `--wait` — Wait for completion

**Examples:**
```bash
gulp-cli ingest zip my_op /data/evidence.zip --wait
```

---

#### `zip-prepare`

Prepare a ZIP archive for ingestion.

```bash
gulp-cli ingest zip-prepare OUTPUT_ZIP PLUGIN FILE [FILE...] [OPTIONS]
```

**Arguments:**
- `OUTPUT_ZIP` — Output ZIP file path
- `PLUGIN` — Plugin name
- `FILE` — Files to include (multiple allowed)

**Options:**
- `--original-path TEXT` — Original path for each file (multiple allowed)
- `--tags TEXT` — Comma-separated tags

**Examples:**
```bash
gulp-cli ingest zip-prepare evidence.zip win_evtx System.evtx Security.evtx

gulp-cli ingest zip-prepare evidence.zip win_evtx \
  /data/System.evtx /data/Security.evtx \
  --tags "production,critical"
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
- `--wait` — Wait for query completion
- `--timeout INTEGER` — Timeout in seconds
- `--limit INTEGER` — Result limit
- `--output-file TEXT` — Save results to file

**Examples:**
```bash
# Match all documents
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}'

# Search specific field
gulp-cli query raw my_op --q '{"query":{"term":{"EventID":4688}}}'

# With limit
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' --limit 100

# Wait for completion
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' --wait

# Save results
gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' --output-file results.json
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
- `--limit INTEGER` — Result limit (default: 50)
- `--offset INTEGER` — Offset
- `--wait` — Wait for completion

**Examples:**
```bash
# Get all documents
gulp-cli query gulp my_op --limit 100

# Filter by source
gulp-cli query gulp my_op --flt '{"source":"Security"}'

# Filter by tag
gulp-cli query gulp my_op --flt '{"tag":"suspicious"}'
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

#### `external`

Query using an external plugin.

```bash
gulp-cli query external OPERATION_ID [OPTIONS]
```

**Arguments:**
- `OPERATION_ID` — Target operation

**Options:**
- `--plugin TEXT` — Plugin name (required)
- `--plugin-params TEXT` — Plugin parameters JSON
- `--q TEXT` — Query JSON
- `--wait` — Wait for completion

**Examples:**
```bash
gulp-cli query external my_op \
  --plugin query_elasticsearch \
  --plugin-params '{"index":"my_index"}' \
  --q '{"query":{"match_all":{}}}'
```

---

## Request Stats (`stats`)

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

#### `note list`

List notes in operation.

```bash
gulp-cli collab note list OPERATION_ID [OPTIONS]
```

**Options:**
- `--limit INTEGER` — Max results (default: 50)
- `--flt TEXT` — Filter JSON

---

#### `note delete`

Delete a note.

```bash
gulp-cli collab note delete OPERATION_ID [OPTIONS]
```

**Options:**
- `--note-id TEXT` — Note ID (required)
- `--confirm` — Skip confirmation

---

#### `link list`

List links.

```bash
gulp-cli collab link list OPERATION_ID [OPTIONS]
```

---

#### `highlight list`

List highlights.

```bash
gulp-cli collab highlight list OPERATION_ID [OPTIONS]
```

---

## Plugin & Mapping Management

#### `plugin list`

List all plugins.

```bash
gulp-cli plugin list [OPTIONS]
```

---

#### `plugin upload`

Upload a new plugin.

```bash
gulp-cli plugin upload PLUGIN_FILE [OPTIONS]
```

---

#### `mapping list`

List all mapping files.

```bash
gulp-cli mapping list [OPTIONS]
```

---

## Global Options

Available on all commands:

- `--help` — Show help message
- `--verbose` — Enable verbose output
- `--no-color` — Disable colored output
- `--output-format TEXT` — Output format (table, json, text)

**Examples:**
```bash
gulp-cli operation list --help
gulp-cli operation list --verbose
gulp-cli operation list --output-format json
```

---

## See Also

- [Getting Started Guide](getting-started.md)
- [Practical Examples](examples.md)
- [Troubleshooting](troubleshooting-cli.md)
