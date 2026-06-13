import time
from datetime import datetime
from colorama import Fore, Style


class LogBuffer:
    def __init__(self, max_size=1000):
        self.messages = []
        self.max_size = max_size
        self.followers = []

    def push(self, msg):
        self.messages.append(msg)
        if len(self.messages) > self.max_size:
            self.messages.pop(0)
        for q in self.followers:
            q.append(msg)

    def get(self, n=None):
        if n is None:
            return list(self.messages)
        return list(self.messages[-n:])

    def clear(self):
        self.messages.clear()

    def follow(self, n=20):
        self.followers.append([])
        q = self.followers[-1]
        for msg in self.messages[-n:]:
            print(msg)
        try:
            while True:
                while q:
                    print(q.pop(0))
                time.sleep(0.3)
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            if q in self.followers:
                self.followers.remove(q)


def log_viewer(log_buffer):
    while True:
        print(f"\n{Fore.YELLOW}=== LOG VIEWER ==={Style.RESET_ALL}")
        print(f"  {Fore.CYAN}1.{Style.RESET_ALL} Show last 20 lines")
        print(f"  {Fore.CYAN}2.{Style.RESET_ALL} Show last N lines")
        print(f"  {Fore.CYAN}3.{Style.RESET_ALL} Follow mode (Ctrl+C to stop)")
        print(f"  {Fore.CYAN}4.{Style.RESET_ALL} Clear logs")
        print(f"  {Fore.CYAN}0.{Style.RESET_ALL} Back to menu")
        choice = input(f"{Fore.YELLOW}Logs>{Style.RESET_ALL} ").strip()

        if choice == "1":
            for msg in log_buffer.get(20):
                print(msg)

        elif choice == "2":
            try:
                n = int(input("Lines: ").strip())
                for msg in log_buffer.get(n):
                    print(msg)
            except ValueError:
                print(f"{Fore.RED}[!] Invalid number{Style.RESET_ALL}")

        elif choice == "3":
            print(f"{Fore.CYAN}[*] Follow mode (Ctrl+C to stop){Style.RESET_ALL}")
            log_buffer.follow()

        elif choice == "4":
            log_buffer.clear()
            print(f"{Fore.GREEN}[+] Logs cleared{Style.RESET_ALL}")

        elif choice == "0":
            break
