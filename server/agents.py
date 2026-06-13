import uuid
import threading
import time


class Agent:
    def __init__(self, agent_id, hostname, username, os, ip, arch):
        self.id = agent_id
        self.hostname = hostname
        self.username = username
        self.os = os
        self.ip = ip
        self.arch = arch
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.tasks = []
        self.results = []

    def to_dict(self):
        return {
            "id": self.id,
            "hostname": self.hostname,
            "username": self.username,
            "os": self.os,
            "ip": self.ip,
            "arch": self.arch,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }

    def add_task(self, task):
        self.tasks.append(task)

    def get_pending_tasks(self):
        pending = [t for t in self.tasks if t["status"] == "pending"]
        for t in pending:
            t["status"] = "sent"
        return pending

    def add_result(self, result):
        self.results.append(result)
        self.last_seen = time.time()


class AgentManager:
    def __init__(self):
        self.agents = {}
        self.lock = threading.Lock()

    def register(self, hostname, username, os, ip, arch):
        with self.lock:
            agent_id = str(uuid.uuid4())[:8]
            agent = Agent(agent_id, hostname, username, os, ip, arch)
            self.agents[agent_id] = agent
            return agent_id

    def get(self, agent_id):
        return self.agents.get(agent_id)

    def list(self):
        with self.lock:
            return {aid: a.to_dict() for aid, a in self.agents.items()}

    def remove(self, agent_id):
        with self.lock:
            return self.agents.pop(agent_id, None)

    def send_task(self, agent_id, command, params=None):
        with self.lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return False
            task = {
                "task_id": str(uuid.uuid4())[:8],
                "command": command,
                "params": params or {},
                "status": "pending",
                "timestamp": time.time(),
            }
            agent.add_task(task)
            return task["task_id"]

    def get_pending_tasks(self, agent_id):
        with self.lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return []
            return agent.get_pending_tasks()

    def submit_result(self, agent_id, task_id, output, status):
        with self.lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return False
            result = {
                "task_id": task_id,
                "output": output,
                "status": status,
                "timestamp": time.time(),
            }
            agent.add_result(result)
            return True

    def get_results(self, agent_id):
        with self.lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return []
            results = list(agent.results)
            return results

    def update_last_seen(self, agent_id):
        with self.lock:
            agent = self.agents.get(agent_id)
            if agent:
                agent.last_seen = time.time()
