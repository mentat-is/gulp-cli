# gulp-cli Practical Examples

Real-world workflows and recipes for common investigation scenarios.

---

## Quick Reference Examples

### Authentication

```bash
# Login (first time setup)
gulp-cli auth login --url http://localhost:8080 --username admin --password admin

# Check who you are
gulp-cli auth whoami

# Switch server
gulp-cli auth login --url http://prod.server.local:8080 --username analyst --password pass

# Logout
gulp-cli auth logout
```

---

## Ingestion Workflows

### Single File Ingestion

```bash
# Ingest one event log
gulp-cli ingest file incident-001 win_evtx /path/to/System.evtx
```

### Bulk File Ingestion with Wildcard

```bash
# Ingest all .evtx files from directory
gulp-cli ingest file incident-001 win_evtx '/evidence/**/*.evtx'

# Ingest from multiple locations
gulp-cli ingest file incident-001 win_evtx '/suspect-machine/*.evtx' '/network-share/backups/*.evtx'
```

### Concurrent Multi-Source Ingestion

```bash
# Create operation for multi-source investigation
gulp-cli operation create incident-2026-001

# Ingest evidence from different sources concurrently
gulp-cli ingest file incident-2026-001 win_evtx '/forensic/windows/*.evtx' --wait &
gulp-cli ingest file incident-2026-001 syslog '/forensic/linux/**/*.log' --wait &
gulp-cli ingest file incident-2026-001 pcap '/forensic/network/*.pcap' --wait &

wait  # Wait for all background jobs
```

### CSV Data Ingestion with Custom Parameters

```bash
# Ingest CSV with specific delimiter and encoding
gulp-cli ingest file incident-001 csv /data/access_log.csv \
  --plugin-params '{"delimiter":";","encoding":"iso-8859-1","has_header":true}'
```

### JSON Logs Ingestion

```bash
# Ingest JSON logs
gulp-cli ingest file incident-001 json '/logs/**/*.json' --wait
```

### Add More Evidence to Existing Source

```bash
# First ingestion creates data-2026-001 source
gulp-cli ingest file incident-001 win_evtx /initial/evidence.evtx

# Later, add more files to same source
gulp-cli ingest file-to-source incident-001 data-2026-001 win_evtx /additional/evidence.evtx --wait
```

---

## Query Workflows

### Match All Documents (Discovery)

```bash
# Get overview of ingested data
gulp-cli query raw incident-001 --q '{"query":{"match_all":{}}}' --limit 100
```

### Search by Field Value

```bash
# Find all login events
gulp-cli query raw incident-001 \
  --q '{"query":{"term":{"EventID":{"value":4624}}}}'

# Find events from specific computer
gulp-cli query raw incident-001 \
  --q '{"query":{"term":{"Computer":"value":"SUSPECT-PC-001"}}}'
```

### Complex Queries (Range, Boolean)

```bash
# Find security events from last 24 hours
gulp-cli query raw incident-001 \
  --q '{
    "query": {
      "bool": {
        "must": [
          {"term": {"EventID": 4688}},
          {"range": {"EventTime": {"gte": "now-24h"}}}
        ]
      }
    }
  }'

# Multiple OR conditions
gulp-cli query raw incident-001 \
  --q '{
    "query": {
      "bool": {
        "should": [
          {"term": {"EventID": 4625}},
          {"term": {"EventID": 4624}},
          {"term": {"EventID": 4688}}
        ],
        "minimum_should_match": 1
      }
    }
  }'
```

### Filter by Source

```bash
# Query only Security events
gulp-cli query gulp incident-001 --flt '{"source":"Security"}' --limit 100

# Query only events tagged as "suspicious"
gulp-cli query gulp incident-001 --flt '{"tag":"suspicious"}' --limit 100
```

### Save Query Results

```bash
# Save all results to JSON file for processing
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --output-file findings.json

# Now process with external tools
cat findings.json | jq '.documents | length'
```

---

## Sigma Rule Queries

### Run Single Sigma Rule

```bash
# Detect process creation events matching rule
gulp-cli query sigma incident-001 \
  --rule-file /rules/process_creation_cmd.yml
```

### Run Rule with Severity Filtering

```bash
# Find only critical and high severity matches
gulp-cli query sigma incident-001 \
  --rule-file /rules/process_creation_cmd.yml \
  --levels critical,high
```

### Run Rule on Specific Source

```bash
# Run rule only on Security event log
gulp-cli query sigma incident-001 \
  --rule-file /rules/suspicious_activity.yml \
  --src-ids Security
```

### Multiple Sigma Rules in Batch

```bash
# Process multiple rule files
for rule in /rules/windows/*.yml; do
  echo "Processing: $rule"
  gulp-cli query sigma incident-001 --rule-file "$rule" --wait
done
```

---

## Enrichment & Tagging Workflows

### Tag Suspicious Events

```bash
# Tag all process creation events as "needs-review"
gulp-cli enrich tag incident-001 \
  --flt '{"event_id":"4688"}' \
  --tag "needs-review"

# Tag failed logins as "security-relevant"
gulp-cli enrich tag incident-001 \
  --flt '{"event_id":"4625"}' \
  --tag "security-relevant" \
  --tag "failed-login"
```

### Apply Threat Level Classification

```bash
# Mark critical events
gulp-cli enrich update incident-001 \
  --flt '{"event_id":["4688","4672","4720"]}' \
  --fields '{"threat_level":"critical","reviewed":false}'

# Mark medium events
gulp-cli enrich update incident-001 \
  --flt '{"event_id":["4625","4634"]}' \
  --fields '{"threat_level":"medium"}'
```

### Track Analysis Progress

```bash
# Mark analyzed events
gulp-cli enrich tag incident-001 \
  --flt '{"threat_level":"critical"}' \
  --tag "analyzed"

# Remove temporary tags
gulp-cli enrich untag incident-001 \
  --flt '{"tag":"temp_analysis"}' \
  --tag "temp_analysis"
```

### Remove Enrichment Data

```bash
# Clean up temporary enrichment fields
gulp-cli enrich remove incident-001 \
  --flt '{"status":"done"}' \
  --fields "temp_field_1,temp_field_2,debug_info"
```

---

## User & Operation Management

### Create Multi-User Investigation Environment

```bash
# Create operation
gulp-cli operation create incident-2026-001 \
  --description "Critical malware incident"

# Create users for investigation team
gulp-cli user create analyst1 --password secure123 --permissions read,write
gulp-cli user create analyst2 --password secure456 --permissions read,write
gulp-cli user create reviewer --password secure789 --permissions read

# Grant access to investigation
gulp-cli operation grant-user incident-2026-001 analyst1
gulp-cli operation grant-user incident-2026-001 analyst2
gulp-cli operation grant-user incident-2026-001 reviewer

# Now each analyst can work on the operation
```

### Archive Investigation (Revoke Access)

```bash
# When investigation complete, revoke external access
gulp-cli operation revoke-user incident-2026-001 analyst1
gulp-cli operation revoke-user incident-2026-001 analyst2

# Or archive by deleting if not needed anymore
gulp-cli operation delete incident-2026-001 --confirm
```

---

## Advanced Workflows

### Full Forensic Investigation Pipeline

```bash
#!/bin/bash
# Complete investigation workflow script

INCIDENT="incident-2026-042"
EVIDENCE_DIR="/forensic/evidence"
RULES_DIR="/sigma-rules"

# 1. Setup
echo "Creating operation..."
gulp-cli operation create $INCIDENT \
  --description "Incident response - $(date +%Y-%m-%d)"

# 2. Ingest all evidence
echo "Ingesting Windows event logs..."
gulp-cli ingest file $INCIDENT win_evtx "$EVIDENCE_DIR/windows/**/*.evtx" --wait

echo "Ingesting syslog files..."
gulp-cli ingest file $INCIDENT syslog "$EVIDENCE_DIR/linux/**/*.log" --wait

echo "Ingesting network capture..."
gulp-cli ingest file $INCIDENT pcap "$EVIDENCE_DIR/network/*.pcap" --wait

# 3. Baseline queries
echo "Running baseline queries..."
gulp-cli query raw $INCIDENT --q '{"query":{"match_all":{}}}' --limit 10 > baseline.json

# 4. Run Sigma rules
echo "Executing Sigma rules..."
for rule in $RULES_DIR/*.yml; do
  gulp-cli query sigma $INCIDENT --rule-file "$rule" --wait
done

# 5. Tag findings
echo "Tagging suspicious activity..."
gulp-cli enrich tag $INCIDENT \
  --flt '{"sigma_match":true}' \
  --tag "sigma-detected" \
  --tag "requires-review"

# 6. Classify by threat level
echo "Classifying threat levels..."
gulp-cli enrich update $INCIDENT \
  --flt '{"sigma_level":"critical"}' \
  --fields '{"threat_priority":1}'

gulp-cli enrich update $INCIDENT \
  --flt '{"sigma_level":["high"]}' \
  --fields '{"threat_priority":2}'

# 7. Export results
echo "Exporting findings..."
gulp-cli query gulp $INCIDENT \
  --flt '{"tag":"sigma-detected"}' \
  --limit 10000 \
  --output-file results_${INCIDENT}.json

echo "Investigation complete. Results in results_${INCIDENT}.json"
```

### Batch Processing Multiple Operations

```bash
#!/bin/bash
# Process multiple incidents in batch

INCIDENTS=("incident-001" "incident-002" "incident-003")
PLUGIN="win_evtx"
EVIDENCE_BASE="/forensic"

for incident in "${INCIDENTS[@]}"; do
  echo "Processing $incident..."
  
  # Ingest
  gulp-cli ingest file "$incident" "$PLUGIN" \
    "$EVIDENCE_BASE/$incident/**/*.evtx" --wait
  
  # Query
  gulp-cli query raw "$incident" \
    --q '{"query":{"match_all":{}}}' \
    --output-file "${incident}_results.json"
  
  # Statistics
  COUNT=$(jq '.documents | length' "${incident}_results.json")
  echo "$incident: $COUNT documents ingested"
done
```

### Integration with External Tools

```bash
# Query with jq for complex processing
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --output-format json | \
  jq '.documents | group_by(.source) | map({source: .[0].source, count: length})'

# Feed to grep for pattern search
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --output-format json | \
  jq -r '.documents[].content' | \
  grep -i "malware"

# Export to CSV
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --output-format json | \
  jq -r '.documents[] | [.timestamp, .event_id, .source] | @csv' > events.csv
```

---

## Tips & Tricks

### Use Aliases for Speed

```bash
alias gop='gulp-cli operation'
alias gq='gulp-cli query'
alias gei='gulp-cli enrich'
alias gin='gulp-cli ingest'

# Usage
gop list
gq raw my_op --q '{"query":{"match_all":{}}}'
gei tag my_op --flt '{"important":true}' --tag "reviewed"
gin file my_op win_evtx 'samples/**/*.evtx'
```

### Use Environment Variables for Repetitive Tasks

```bash
# Set default operation
export GULP_DEFAULT_OP="incident-001"

# Set output format
export GULP_OUTPUT_FORMAT="json"

# Use in scripts
gulp-cli query raw $GULP_DEFAULT_OP --q '{"query":{"match_all":{}}}'
```

### Parallel Processing with GNU Parallel

```bash
# Ingest multiple files in parallel
find /evidence -name "*.evtx" | \
  parallel gulp-cli ingest file incident-001 win_evtx {}

# Run Sigma rules in parallel
find /rules -name "*.yml" | \
  parallel gulp-cli query sigma incident-001 --rule-file {} --wait
```

### Monitor Long-Running Operations

```bash
# Run with custom timeout
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --wait \
  --timeout 7200  # 2 hours

# Or run in background
gulp-cli ingest file incident-001 win_evtx 'samples/**/*.evtx' --wait &
JOB_PID=$!
while kill -0 $JOB_PID 2>/dev/null; do
  echo "Still processing..."
  sleep 5
done
echo "Complete!"
```

---

## Common Error Handling

```bash
#!/bin/bash
# Robust error handling

set -e  # Exit on error

trap 'echo "Error on line $LINENO"' ERR

if ! gulp-cli auth whoami > /dev/null 2>&1; then
  echo "Not authenticated. Please login first."
  gulp-cli auth login
fi

if ! gulp-cli operation get "$INCIDENT" > /dev/null 2>&1; then
  echo "Creating operation $INCIDENT..."
  gulp-cli operation create "$INCIDENT"
fi

echo "Ready for investigations!"
```

---

## See Also

- [Command Reference](command-reference.md) — complete command documentation
- [Getting Started](getting-started.md) — beginner guide
- [Troubleshooting](troubleshooting-cli.md) — problem resolution
