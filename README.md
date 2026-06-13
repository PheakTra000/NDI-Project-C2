# C2 v2 - Command & Control (Network Design Project)

## Menu Options

### 1. Start listener
Start the HTTP server on `0.0.0.0:8080`. Agents connect here via Cloudflare tunnel. Run before deploying agents.

### 2. Stop listener
Shut down the HTTP server. All agent connections drop. No new tasks delivered until restarted.

### 3. List agents
Show all registered agents: ID, hostname, OS, IP, last beacon time. Verify which machines currently have implants.

### 4. Interact with agent
Enter persistent shell on a target agent. Uses `/bin/sh` — state carries between commands (`cd`, variables, env). Type `exit` to return to menu.

### 5. Send shell command
Fire a single command to an agent and wait for output. Useful for quick one-shot checks without entering full interactive mode. Output displays then returns to menu.

### 6. Upload file
Transfer a file from your machine to the target agent. Prompts for local path and remote destination path. File is base64-encoded over HTTP.

### 7. Download file
Pull a file from the target agent back to your machine. Prompts for remote path and local save location.

### 8. Install persistence
Make the agent survive reboots. Options:
- **Cron (Linux)** — adds crontab entry
- **Systemd (Linux)** — creates + enables a systemd service
- **Registry (Windows)** — sets HKCU Run key
- **Scheduled Task (Windows)** — creates repeating schtask

### 9. Remove persistence
Remove a previously installed persistence mechanism. Prompts for method and identifier/name.

### 10. Generate backdoor payload
Create standalone agent files with the C2 URL + auth token baked in. Output options:
- Python script (`payload.py`)
- PowerShell script (`payload.ps1`)
- Bash script (`payload.sh`)
- Batch script (`payload.bat`)

Files land in current working directory. Distribute to target machines.

### 11. Agent results
View task execution history for a selected agent. Shows task ID, status, and truncated output for each completed task.

### 12. View logs
Browse the server-side log buffer. Sub-options:
- Show last 20 lines
- Show last N lines (custom)
- Follow mode (live tail, Ctrl+C to stop)
- Clear logs

### 13. Show auth token
Display the current server authentication token and one-liner commands. Token required for agent registration and beaconing. Prevents unauthorized agents from connecting.
