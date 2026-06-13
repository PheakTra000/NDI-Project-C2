import threading
import socketserver
from server.handler import C2Handler
from server.agents import AgentManager


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class C2Server:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.manager = AgentManager()
        self.server = None
        self.thread = None
        self.running = False

    def start(self, log_buffer=None, public_url=None, token=""):
        C2Handler.manager = self.manager
        C2Handler.log_buffer = log_buffer
        C2Handler.server_token = token
        if public_url:
            C2Handler.server_url = public_url
        self.server = ThreadedHTTPServer((self.host, self.port), C2Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.running = True

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.running = False

    def agent_count(self):
        return len(self.manager.list())
