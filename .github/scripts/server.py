import os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from deploy import req, find_server, server, STATUS  # noqa: E402

ACTION = os.environ.get("ACTION", "status")
WAIT = int(os.environ.get("WAIT_MINUTES", "15"))

KEEP = re.compile(r"(ERROR|FATAL|Exception|Caused by|\bat [\w.$]+\(|Crash|crash-report|Failed|failed to|Mod loading|Done \(|"
                  r"Starting minecraft server|Stopping server|Loading \d+ mods|safezone|creativecrafts|datapack|"
                  r"Missing|Invalid|Couldn't)", re.I)
DROP = re.compile(r"(joined the game|left the game|lost connection|logged in with|<[^>]+>|\[Server\]|issued server command|UUID of player)", re.I)
IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b|\[?[0-9a-f]{1,4}(?::[0-9a-f]{0,4}){3,7}\]?", re.I)


def status_line(s):
    p = s.get("players", {})
    return f"status={STATUS.get(s['status'], s['status'])} players={p.get('count', 0)}/{p.get('max', '?')} software={s.get('software', {}).get('version', '?')}"


def print_log(sid):
    body = req("GET", f"/servers/{sid}/logs/")
    text = (body.get("data") or {}).get("content") or ""
    lines = [l for l in text.splitlines() if KEEP.search(l) and not DROP.search(l)]
    print(f"--- log: {len(text.splitlines())} lines total, {len(lines)} shown (filtered, IPs redacted) ---")
    for l in lines[-250:]:
        print(IP.sub("<ip>", l)[:400])


sid = find_server()
s = server(sid)
print("before:", status_line(s))

if ACTION == "start":
    if s["status"] in (0, 7):
        req("GET", f"/servers/{sid}/start/")
        print("start requested")
    t = time.time()
    while time.time() - t < WAIT * 60:
        time.sleep(15)
        s = server(sid)
        if s["status"] in (1, 0, 7):
            break
    print("after:", status_line(s), f"({int(time.time() - t)}s)")

if ACTION in ("start", "logs") or s["status"] == 7:
    print_log(sid)

if ACTION == "start" and s["status"] != 1:
    sys.exit(f"server did not come online: {STATUS.get(s['status'], s['status'])}")
