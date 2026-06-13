import os
import base64
import time


def upload_file(manager, agent_id, local_path, remote_path):
    if not os.path.exists(local_path):
        print(f"[!] Local file not found: {local_path}")
        return

    with open(local_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()

    task_id = manager.send_task(
        agent_id,
        "upload",
        {"remote_path": remote_path, "data": data},
    )
    if not task_id:
        print("[!] Agent not found")
        return

    print(f"[*] Upload task {task_id} sent, waiting...")
    for _ in range(30):
        time.sleep(1)
        results = manager.get_results(agent_id)
        for r in results:
            if r["task_id"] == task_id:
                print(r["output"])
                return
    print("[!] Timeout")


def download_file(manager, agent_id, remote_path, local_path):
    task_id = manager.send_task(
        agent_id,
        "download",
        {"remote_path": remote_path},
    )
    if not task_id:
        print("[!] Agent not found")
        return

    print(f"[*] Download task {task_id} sent, waiting...")
    for _ in range(30):
        time.sleep(1)
        results = manager.get_results(agent_id)
        for r in results:
            if r["task_id"] == task_id:
                if r["status"] == "success":
                    data = base64.b64decode(r["output"])
                    with open(local_path, "wb") as f:
                        f.write(data)
                    print(f"[+] Saved to {local_path} ({len(data)} bytes)")
                else:
                    print(f"[!] Download failed: {r['output']}")
                return
    print("[!] Timeout")
