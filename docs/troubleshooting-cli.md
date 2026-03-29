# gulp-cli Troubleshooting Guide

Solutions for common issues and problems.

---

## Connection & Authentication Issues

### `Connection refused` or `Cannot connect to server`

**Problem:** 
```
Error: Cannot connect to http://localhost:8080
Connection refused
```

**Solutions:**

1. **Verify gULP is running:**
   ```bash
   curl -i http://localhost:8080/api/config
   ```
   Should return HTTP 200.

2. **Start gULP if not running:**
   ```bash
   gulp --reset-collab --create test_operation
   ```

3. **Check URL:**
   ```bash
   gulp-cli auth whoami  # Should show current URL
   
   # Or login with explicit URL
   gulp-cli auth login --url http://localhost:8080 --username admin --password admin
   ```

4. **Check firewall:**
   ```bash
   # On localhost
   netstat -an | grep 8080
   
   # On remote server
   ping server.example.com
   telnet server.example.com 8080  # Must connect
   ```

---

### `Authentication failed` / `Invalid credentials`

**Problem:**
```
Error: Authentication failed: Invalid username or password
```

**Solutions:**

1. **Verify credentials:**
   - Default users are `admin/admin` and `guest/guest`
   - Check if user exists: `gulp-cli user list`

2. **Clear and retry:**
   ```bash
   rm ~/.config/gulp-cli/config.json
   gulp-cli auth login --url http://localhost:8080 --username admin --password admin
   ```

3. **Check token expiration:**
   - Tokens may expire. Re-authenticate:
   ```bash
   gulp-cli auth logout
   gulp-cli auth login
   ```

4. **Verify admin privileges for management commands:**
   ```bash
   # If using guest account (read-only):
   gulp-cli auth login --username admin --password admin
   ```

---

### `Auth token not found` / `Not authenticated`

**Problem:**
```
Error: No authentication token found. Please login first.
```

**Solution:**
```bash
gulp-cli auth login --url http://localhost:8080 --username admin --password admin
```

---

## Ingestion Issues

### `File not found` when using wildcard

**Problem:**
```
Error: No files matching pattern: samples/win_evtx/*.evtx
```

**Solutions:**

1. **Check path exists:**
   ```bash
   ls -la samples/win_evtx/
   ```

2. **Test glob pattern:**
   ```bash
   python3 -c "from glob import glob; print(glob('samples/win_evtx/*.evtx'))"
   ```

3. **Use absolute paths:**
   ```bash
   gulp-cli ingest file my_op win_evtx /absolute/path/to/files/*.evtx
   ```

4. **Quote patterns correctly:**
   ```bash
   # DO THIS (quote pattern)
   gulp-cli ingest file my_op win_evtx 'samples/**/*.evtx'
   
   # NOT THIS (shell expands glob)
   gulp-cli ingest file my_op win_evtx samples/**/*.evtx
   ```

---

### `Ingestion timeout` / Slow ingestion

**Problem:**
```
Error: Ingestion timeout after 3600 seconds
```

**Solutions:**

1. **Increase timeout:**
   ```bash
   gulp-cli ingest file my_op win_evtx large_file.evtx --timeout 10800  # 3 hours
   ```

2. **Check gULP resource usage:**
   ```bash
   # On gULP host
   top
   htop
   ```

3. **Ingest smaller batches:**
   ```bash
   # Instead of all at once
   gulp-cli ingest file my_op win_evtx 'samples/win_evtx/System.evtx'
   gulp-cli ingest file my_op win_evtx 'samples/win_evtx/Security.evtx'
   gulp-cli ingest file my_op win_evtx 'samples/win_evtx/Application.evtx'
   ```

4. **Monitor ingestion progress:**
   ```bash
   # In separate terminal
   while true; do
     curl http://localhost:8080/api/ingest/stats | jq '.document_count'
     sleep 5
   done
   ```

---

### `Plugin not found` / Invalid plugin name

**Problem:**
```
Error: Plugin 'win_evtx' not found
```

**Solutions:**

1. **List available plugins:**
   ```bash
   gulp-cli plugin list
   ```

2. **Check plugin name spelling:**
   ```bash
   # Correct names usually lowercase with underscores
   gulp-cli ingest file my_op win_evtx file.evtx
   ```

3. **Load plugin in gULP:**
   - Some plugins may need to be configured first
   - Check `/gulp/gulp_cfg.json` for available plugins

---

### File already ingested / Duplicate ingestion

**Problem:**
```
Warning: File already ingested in this source
```

**Solution:**

If you need to re-ingest:
1. Use `--force` flag (if available) in next version
2. Or create a new source:
   ```bash
   # Instead of reusing same source, ingest into new source
   gulp-cli ingest file my_op win_evtx new_file.evtx
   ```

---

## Query Issues

### `No results` from query

**Problem:**
```
Query executed successfully but no documents returned
```

**Possible causes & solutions:**

1. **No documents ingested yet:**
   ```bash
   # Check what's in operation
   gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' --limit 10
   ```

2. **Wrong filter syntax:**
   ```bash
   # Test with match_all first
   gulp-cli query raw my_op --q '{"query":{"match_all":{}}}'
   
   # Then try filtered
   gulp-cli query raw my_op --q '{"query":{"term":{"field":"value"}}}'
   ```

3. **Field name incorrect:**
   - Check actual field names by querying all documents
   - Use jq to inspect structure:
   ```bash
   gulp-cli query raw my_op --q '{"query":{"match_all":{}}}' \
     --limit 1 --output-file sample.json
   jq . sample.json
   ```

4. **Case sensitivity:**
   - Field searches may be case-sensitive
   - Try lowercase or exact match

---

### `Sigma rule returns no matches`

**Problem:**
```
Sigma query executed but no matching events
```

**Solutions:**

1. **Verify rule file syntax:**
   ```bash
   # Check rule parses as valid YAML
   cat /path/to/rule.yml | head -20
   ```

2. **Check rule targets correct events:**
   - Sigma rule checks for specific event IDs
   - Verify your data has matching events:
   ```bash
   gulp-cli query raw my_op --q '{"query":{"term":{"EventID":4688}}}'
   ```

3. **Run without severity filter first:**
   ```bash
   # Try without level restriction
   gulp-cli query sigma my_op --rule-file rule.yml
   
   # Then with specific levels
   gulp-cli query sigma my_op --rule-file rule.yml --levels critical,high
   ```

4. **Enable verbose output:**
   ```bash
   gulp-cli --verbose query sigma my_op --rule-file rule.yml 
   ```

---

## Tag & Enrichment Issues

### `Tag operation failed`

**Problem:**
```
Error: Failed to tag documents
```

**Solutions:**

1. **Check filter is valid:**
   ```bash
   # Test filter first
   gulp-cli query gulp my_op --flt '{"source":"Security"}'
   
   # If results, tag them
   gulp-cli enrich tag my_op --flt '{"source":"Security"}' --tag "reviewed"
   ```

2. **At least one tag required:**
   ```bash
   # WRONG: no tags specified
   gulp-cli enrich tag my_op --flt '{"important":true}'
   
   # CORRECT: specify tag
   gulp-cli enrich tag my_op --flt '{"important":true}' --tag "reviewed"
   ```

3. **Check operation exists:**
   ```bash
   gulp-cli operation get my_op
   ```

---

### `Update fails` / Field update not applied

**Problem:**
```
Error: Failed to update documents
```

**Solutions:**

1. **Verify filter matches documents:**
   ```bash
   # Check how many docs match
   gulp-cli query gulp my_op --flt '{"event_id":"4688"}'
   ```

2. **JSON syntax for fields:**
   ```bash
   # Check JSON is valid
   echo '{"threat_level":"high"}' | jq .
   
   # Use in command
   gulp-cli enrich update my_op \
     --flt '{"important":true}' \
     --fields '{"threat_level":"high"}'
   ```

3. **Field name conventions:**
   - Use lowercase with underscores
   - Some fields may be immutable (check gULP docs)

---

## Permission & Access Issues

### `Permission denied` / `Access denied`

**Problem:**
```
Error: Permission denied. You don't have access to this operation.
```

**Solutions:**

1. **Check current user:**
   ```bash
   gulp-cli auth whoami
   ```

2. **Verify operation access:**
   - Only creator and granted users can access
   - Ask admin to grant access:
   ```bash
   # (As admin)
   gulp-cli operation grant-user my_op alice
   ```

3. **Check user permissions for admin commands:**
   ```bash
   # Admin-only commands (user create, delete, etc.)
   # Need admin user
   gulp-cli auth login --username admin --password admin
   ```

---

### `Cannot delete operation` / Resource still in use

**Problem:**
```
Error: Cannot delete operation. Resource in use by active requests.
```

**Solutions:**

1. **Cancel active requests:**
   ```bash
   # List ongoing requests
   gulp-cli stats list
   
   # Cancel specific request
   gulp-cli stats cancel REQUEST_ID
   ```

2. **Wait for operations to complete:**
   - If ingestion in progress, wait for completion
   - Check `/api/stats` endpoint for pending operations

3. **Force delete (if needed):**
   ```bash
   gulp-cli operation delete my_op --confirm
   # May require cleanup of files/resources
   ```

---

## Output & Formatting Issues

### Garbled output / Special characters not displaying

**Problem:**
```
Strange characters in output like ▓ or ╫
```

**Solutions:**

1. **Disable color:**
   ```bash
   gulp-cli operation list --no-color
   ```

2. **Change output format:**
   ```bash
   # JSON format (most compatible)
   export GULP_OUTPUT_FORMAT=json
   gulp-cli operation list
   
   # Text format
   export GULP_OUTPUT_FORMAT=text
   gulp-cli operation list
   ```

3. **Check terminal encoding:**
   ```bash
   echo $LANG  # Should be something like en_US.UTF-8
   ```

---

### Too much output / Can't find information

**Problem:**
```
Output is too verbose or hard to read
```

**Solutions:**

1. **Limit results:**
   ```bash
   gulp-cli operation list --limit 10
   ```

2. **Save to file:**
   ```bash
   gulp-cli operation list > operations.txt
   grep keyword operations.txt
   ```

3. **Filter and search:**
   ```bash
   # Use grep to filter
   gulp-cli operation list | grep "incident"
   
   # Or use JSON output with jq
   gulp-cli operation list --output-format json | jq '.[] | select(.name | contains("incident"))'
   ```

4. **Quiet mode:**
   ```bash
   gulp-cli query raw my_op --q '...' --quiet
   ```

---

## Performance Issues

### Commands running very slowly

**Problem:**
```
gulp-cli operation list takes 30+ seconds
```

**Solutions:**

1. **Check network latency:**
   ```bash
   ping -c 3 localhost  # Or your server
   ```

2. **Check server load:**
   ```bash
   # On gULP host
   uptime
   top
   ```

3. **Use limit to reduce data:**
   ```bash
   # Instead of listing everything
   gulp-cli operation list --limit 50
   ```

4. **Use JSON output (faster parsing):**
   ```bash
   export GULP_OUTPUT_FORMAT=json
   gulp-cli operation list
   ```

5. **Check network saturation:**
   ```bash
   # Download speed test
   curl -O https://speed.cloudflare.com/__down?bytes=100000000
   ```

---

## Installation & Setup Issues

### `command not found: gulp-cli`

**Problem:**
```
bash: gulp-cli: command not found
```

**Solutions:**

1. **Reinstall package:**
   ```bash
   pip install -e /gulp/gulp-cli
   ```

2. **Check PATH:**
   ```bash
   which gulp-cli
   echo $PATH
   ```

3. **Verify virtual environment is activated:**
   ```bash
   # Check if venv activated
   which python
   # Should show path in venv
   
   # If not, activate it
   source ~/.venvs/gulp-cli/bin/activate
   ```

---

### `ImportError: No module named 'gulp_sdk'`

**Problem:**
```
ImportError: No module named 'gulp_sdk'
```

**Solution:**
1. Install gulp-cli properly:
   ```bash
   pip install -e /gulp/gulp-cli
   ```

2. Verify installation:
   ```bash
   python -c "import gulp_sdk; print(gulp_sdk.__file__)"
   ```

---

### `ModuleNotFoundError` for other dependencies

**Problem:**
```
ModuleNotFoundError: No module named 'typer'
```

**Solution:**
```bash
# Reinstall with all dependencies
pip install -e /gulp/gulp-cli --force-reinstall
```

---

## Getting More Help

### Enable verbose/debug output:

```bash
# All commands support --verbose
gulp-cli --verbose operation list
```

### Check logs:

```bash
# gULP logs (if running locally)
tail -f /var/log/gulp/gulp.log

# Or check gULP stdout/stderr in terminal where it started
```

### Report issues:

If you've tried solutions above:
1. Collect diagnostic info:
   ```bash
   gulp-cli auth whoami
   python -c "import sys; print(sys.version)"
   pip list | grep gulp
   ```

2. Include in bug report:
   - Command you ran
   - Error message
   - Output of `gulp-cli --help`
   - Diagnostic info from above

---

## Performance Monitoring

Monitor slow operations:

```bash
#!/bin/bash
# Time a command
time gulp-cli query raw my_op --q '{"query":{"match_all":{}}}'

# Profile with strace
strace -e trace=network,open,read gulp-cli operation list

# Monitor system resources during operation
watch -n 1 'ps aux | grep gulp-cli'
```

---

## Still Having Issues?

1. Check [Getting Started Guide](getting-started.md) — basics
2. Read [Command Reference](command-reference.md) — command details
3. Review [Examples](examples.md) — working workflows
4. Check main gULP documentation in `/docs`

For gULP server issues (not CLI), see:
- [gULP Troubleshooting](../troubleshooting.md)
- [gULP Installation](../install_docker.md)
