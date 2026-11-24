import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from deploy import req, find_server, server, STATUS  # noqa: E402

ACTION = os.environ.get("ACTION", "status")
WAIT = int(os.environ.get("WAIT_MINUTES", "15"))

KEEP = re.compile(r"(ERROR|FATAL|Exception|Caused by|\bat [\w.$]+\(|Crash|crash-report|Failed|failed to|Mod loading|Done \(|"
                  r"Starting minecraft server|Stopping server|Loading \d+ mods|safezone|creativecrafts|datapack|"
                  r"Missing|Invalid|Couldn't)", re.I)
DROP = re.compile(r"(Couldn't parse element ResourceKey\[minecraft:root / minecraft:loot_table\]|Could not decode GlobalLootModifier|"
                  r"Failed to apply tag physics properties|joined the game|left the game|lost connection|logged in with|<[^>]+>|\[Server\]|issued server command|UUID of player)", re.I)
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b|\[?[0-9a-f]{1,4}(?::[0-9a-f]{0,4}){3,7}\]?", re.I)


def status_line(s):
    p = s.get("players", {})
    return f"status={STATUS.get(s['status'], s['status'])} players={p.get('count', 0)}/{p.get('max', '?')} software={s.get('software', {}).get('version', '?')}"


def print_log(sid):
    body = req("GET", f"/servers/{sid}/logs/")
    text = (body.get("data") or {}).get("content") or ""
    lines = [l for l in text.splitlines() if KEEP.search(l) and not DROP.search(l)]
    print(f"--- log: {len(text.splitlines())} lines total, {len(lines)} shown (filtered, IPs/UUIDs redacted) ---")
    for l in lines[-250:]:
        print(UUID.sub("<uuid>", IP.sub("<ip>", l))[:400])


CHECK_CMDS = ["datapack list enabled", "datapack list available", "neoforge tps", "list"]
CHECK_KEEP = re.compile(r"(data pack|datapack|TPS|Mean tick|players online|There are)", re.I)


def run_check(sid):
    body = req("GET", f"/servers/{sid}/logs/")
    before = len(((body.get("data") or {}).get("content") or "").splitlines())
    for c in CHECK_CMDS:
        req("POST", f"/servers/{sid}/command/", json.dumps({"command": c}).encode(), "application/json")
        time.sleep(2)
    time.sleep(5)
    text = (req("GET", f"/servers/{sid}/logs/").get("data") or {}).get("content") or ""
    print("--- check output ---")
    for l in text.splitlines()[max(0, before - 5):]:
        if CHECK_KEEP.search(l) and not re.search(r"joined|left|<", l):
            print(UUID.sub("<uuid>", IP.sub("<ip>", l))[:600])


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

if ACTION == "check" or (ACTION == "start" and s["status"] == 1):
    if s["status"] == 1:
        run_check(sid)
    else:
        print("check skipped: server is not online")

if ACTION == "start" and s["status"] != 1:
    sys.exit(f"server did not come online: {STATUS.get(s['status'], s['status'])}")
