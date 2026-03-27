# Gulp CLI - Resource Management Commands

This document covers the new CLI commands for managing Gulp resources:
- **Context Management** - Organize investigations into logical contexts
- **Source Management** - Create sources within contexts
- **Plugin Management** - Upload, list, and download plugins
- **Mapping File Management** - Upload and manage mapping files
- **Enhance Document Map Management** - Map `gulp.event_code` to glyph/color per plugin
- **Glyph Management** - Create and manage custom glyphs used by maps and collab objects

## Context Management

Contexts are used to organize data within an operation. For example, in a security investigation, you might have contexts for different systems or departments.

### List Contexts

List all contexts in an operation:

```bash
gulp context list test_operation
```

Output:
```
╭─ Contexts in test_operation ────────────────────────────┬──────────┬─────────╮
│ id                                                       │ name     │ color   │
├──────────────────────────────────────────────────────────┼──────────┼─────────┤
│ ctx_dc01_1234567890                                      │ DC01     │ #FF0000 │
│ ctx_fileserv_1234567891                                  │ FileServ │ #00FF00 │
╰──────────────────────────────────────────────────────────┴──────────┴─────────╯
```

With verbose output (full JSON):

```bash
gulp context list test_operation --verbose
```

### Get Context Details

Get detailed information about a specific context:

```bash
gulp context get ctx_dc01_1234567890
```

### Create Context

Create a new context in an operation:

```bash
# Basic creation
gulp context create test_operation "DC01"

# With color and description
gulp context create test_operation "DC01" \
  --color "#FF0000" \
  --description "Primary Domain Controller"

# Fail if already exists
gulp context create test_operation "DC01" --fail-if-exists
```

Response includes context ID, creation timestamp, and metadata.

### Update Context

Update context metadata (description, color, glyph):

```bash
gulp context update ctx_dc01_1234567890 \
  --description "Updated description" \
  --color "#00FF00"
```

At least one of `--description`, `--color`, or `--glyph-id` must be provided.

### Delete Context

Delete a context and optionally its data:

```bash
# Delete context and all related data
gulp context delete ctx_dc01_1234567890

# Delete context only (keep data in storage)
gulp context delete ctx_dc01_1234567890 --delete-data=False
```

---

## Source Management

Sources represent individual data collection points within a context. For example, a source might be a specific Windows Event Log or a CSV file.

### List Sources

List all sources in a context:

```bash
gulp source list test_operation ctx_dc01_1234567890
```

Output:
```
╭─ Sources in ctx_dc01_1234567890 ─────────────────────────┬─────────────┬────────────╮
│ id                                                        │ name        │ plugin     │
├───────────────────────────────────────────────────────────┼─────────────┼────────────┤
│ src_security_1234567890                                   │ Security    │ win_evtx   │
│ src_sysmon_1234567891                                     │ Sysmon      │ win_evtx   │
╰───────────────────────────────────────────────────────────┴─────────────┴────────────╯
```

### Get Source Details

Get detailed information about a specific source:

```bash
gulp source get src_security_1234567890
```

### Create Source

Create a new source in a context:

```bash
# Basic creation
gulp source create test_operation ctx_dc01_1234567890 "Security" --plugin win_evtx

# With color and description
gulp source create test_operation ctx_dc01_1234567890 "Security" \
  --plugin win_evtx \
  --description "Windows Security event log" \
  --color "#FF9900"

# Fail if already exists
gulp source create test_operation ctx_dc01_1234567890 "Security" \
  --plugin win_evtx \
  --fail-if-exists
```

### Update Source

Update source metadata:

```bash
gulp source update src_security_1234567890 \
  --description "Updated Security configuration" \
  --color "#00FF00"
```

At least one of `--description`, `--color`, or `--glyph-id` must be provided.

### Delete Source

Delete a source and optionally its data:

```bash
# Delete source and all related data
gulp source delete src_security_1234567890

# Delete source only (keep data in storage)
gulp source delete src_security_1234567890 --delete-data=False
```

---

## Plugin Management

Plugins are Python modules that handle data ingestion, enrichment, and analysis.

### List Plugins

List all installed plugins:

```bash
gulp plugin list
```

Output:
```
╭─ Installed Plugins ──────────────────────────────────────────┬──────────────┬──────────╮
│ filename              │ display_name          │ type         │ desc         │ version  │
├──────────────────────┬───────────────────────┼──────────────┼──────────────┼──────────┤
│ win_evtx.py          │ Windows Event Log     │ ingestion    │ Parse evtx   │ 1.0      │
│ csv.py               │ CSV Parser            │ ingestion    │ Parse CSV    │ 1.0      │
│ enrich_abuse.py      │ Abuse.ch URL Enrich  │ enrichment   │ URL enricher │ 1.0      │
╰──────────────────────┴───────────────────────┴──────────────┴──────────────┴──────────╯
```

### List UI Plugins

List available UI plugins:

```bash
gulp plugin list-ui
```

### Upload Plugin

Upload a custom plugin:

```bash
# Upload as default plugin
gulp plugin upload /path/to/my_plugin.py

# Upload as extension plugin
gulp plugin upload /path/to/my_extension.py --type extension

# Upload as UI plugin
gulp plugin upload /path/to/my_ui_plugin.py --type ui

# Fail if already exists
gulp plugin upload /path/to/my_plugin.py --fail-if-exists
```

Response includes the file path where the plugin was saved on the server.

### Download Plugin

Download a plugin from the server:

```bash
# Download default plugin
gulp plugin download win_evtx.py /local/path/win_evtx.py

# Download extension plugin
gulp plugin download my_extension.py /path/to/save --type extension

# Download UI plugin
gulp plugin download my_ui.py /path/to/save --type ui
```

### Delete Plugin

Delete a plugin from the server:

```bash
# Delete default plugin
gulp plugin delete my_plugin.py

# Delete extension plugin
gulp plugin delete my_extension.py --type extension

# Delete UI plugin
gulp plugin delete my_ui.py --type ui
```

---

## Mapping File Management

Mapping files define data transformations and field mappings for ingestion plugins.

### List Mapping Files

List all available mapping files:

```bash
gulp mapping list
```

Output:
```
╭─ Available Mapping Files ────────────────────────────────────┬──────────────────────╮
│ filename          │ path                 │ plugins          │ mapping_ids          │
├───────────────────┼──────────────────────┼──────────────────┼──────────────────────┤
│ windows.json      │ /opt/gulp/mapping... │ win_evtx.py      │ windows              │
│ splunk.json       │ /opt/gulp/mapping... │ splunk.py        │ splunk               │
│ mftecmd_csv.json  │ /opt/gulp/mapping... │ csv.py           │ record,boot,j,sds    │
╰───────────────────┴──────────────────────┴──────────────────┴──────────────────────╯
```

### Upload Mapping File

Upload a custom mapping file:

```bash
# Basic upload
gulp mapping upload /path/to/my_mapping.json

# Fail if already exists
gulp mapping upload /path/to/my_mapping.json --fail-if-exists
```

Response includes the path where the mapping was saved on the server.

### Download Mapping File

Download a mapping file from the server:

```bash
gulp mapping download windows.json /local/path/windows.json
```

### Delete Mapping File

Delete a mapping file from the server:

```bash
gulp mapping delete my_mapping.json
```

---

## Enhance Document Map Management

Enhance document maps let you bind a plugin-specific `gulp.event_code` to a visual style (`glyph_id` and/or `color`).

### List Enhance Maps

```bash
gulp-cli enhance-map list

# Filter by plugin
gulp-cli enhance-map list --flt '{"plugin":"win_evtx"}'

# Filter by event code (as string)
gulp-cli enhance-map list --flt '{"gulp_event_code":"4624"}'
```

### Create Enhance Map

```bash
# Map Windows logon event to a glyph
gulp-cli enhance-map create 4624 win_evtx --glyph-id glyph_logon

# Map event to color only
gulp-cli enhance-map create 4625 win_evtx --color "#ff3300"

# Map event to both glyph and color
gulp-cli enhance-map create 4688 win_evtx --glyph-id glyph_process --color "#ffaa00"
```

### Update/Get/Delete Enhance Map

```bash
gulp-cli enhance-map get <enhance_map_id>
gulp-cli enhance-map update <enhance_map_id> --color "#00cc66"
gulp-cli enhance-map delete <enhance_map_id>
```

---

## Glyph Management

Glyphs are small images (max 16KB) that can be assigned to contexts, sources, and enhance maps.

### List Glyphs

```bash
gulp-cli glyph list

# Filter example
gulp-cli glyph list --flt '{"private":false}'
```

### Create Glyph

```bash
# Create from image
gulp-cli glyph create --img-path ./icons/logon.png --name glyph_logon

# Create by name only (server-side resolved glyph)
gulp-cli glyph create --name existing_builtin_glyph
```

### Update/Get/Delete Glyph

```bash
gulp-cli glyph get <glyph_id>
gulp-cli glyph update <glyph_id> --name glyph_logon_v2
gulp-cli glyph update <glyph_id> --img-path ./icons/logon_new.png
gulp-cli glyph delete <glyph_id>
```

---

## Verbose Output

All commands support the `--verbose` flag to show the complete JSON response:

```bash
# Show full JSON instead of formatted table
gulp context list test_operation --verbose

# Show detailed context object
gulp context get ctx_dc01_1234567890 --verbose

# Show plugin metadata
gulp plugin list --verbose
```

## Error Handling

Common errors and solutions:

| Error | Cause | Solution |
|-------|-------|----------|
| `Context not found` | Invalid context ID | Use `gulf context list` to find valid IDs |
| `Permission denied` | Insufficient permissions | Ensure you're logged in with appropriate role |
| `Context already exists` | Context name collision | Use `--fail-if-exists` flag or choose different name |
| `File not found` | Plugin/mapping file doesn't exist | Verify file path; use `--list` to see available files |

## Example Workflow: Investigation Setup

Complete example setting up a multi-host investigation:

```bash
# 1. Create operation
gulp operation create "Ransomware Investigation" --description "APT ransomware incident response"

# 2. Create contexts for each affected system
gulp context create ransomware_investigation "DC01" --color "#FF0000"
gulf context create ransomware_investigation "FileServer" --color "#FF6600"
gulf context create ransomware_investigation "Workstation" --color "#FFFF00"

# 3. Create sources for each system's logs
gulf source create ransomware_investigation ctx_dc01_xxx "Security Events" --plugin win_evtx
gulf source create ransomware_investigation ctx_dc01_xxx "Sysmon" --plugin win_evtx

gulf source create ransomware_investigation ctx_fileserv_xxx "Security Events" --plugin win_evtx
gulf source create ransomware_investigation ctx_fileserv_xxx "File Access" --plugin win_evtx

# 4. Upload any custom mapping files needed
gulf mapping upload custom_ransomware_indicators.json

# 5. Ingest data using the sources
gulf ingest file ransomware_investigation src_security_xxx win_evtx samples/win_evtx/Security.evtx
```

---

## Related Documentation

- [Operations API](../docs/api_context_source.md)
- [Plugin Development](../docs/plugins_and_mapping.md)
- [Mapping File Format](../docs/plugins_and_mapping.md#mapping-files)
- [SDK Examples](../gulp-sdk/docs/examples/context_source_management.py)
