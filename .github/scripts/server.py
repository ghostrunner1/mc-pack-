import json, os, re, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from deploy import req, q, find_server, server, list_dir, STATUS  # noqa: E402

ACTION = os.environ.get("ACTION", "status")
WAIT = int(os.environ.get("WAIT_MINUTES", "15"))

KEEP = re.compile(r"(ERROR|FATAL|Exception|Caused by|\bat [\w.$]+\(|Crash|crash-report|Failed|failed to|Mod loading|Done \(|"
                  r"Starting minecraft server|Stopping server|Loading \d+ mods|safezone|creativecrafts|datapack|"
                  r"Missing|Invalid|Couldn't|configuration file for Lithium)", re.I)
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
    def live():
        return (req("GET", f"/servers/{sid}/logs/").get("data") or {}).get("content") or ""
    before = len(live().splitlines())
    for c in CHECK_CMDS:
        req("POST", f"/servers/{sid}/command/", json.dumps({"command": c}).encode(), "application/json")
        time.sleep(2)
    text = ""
    for _ in range(12):  # /logs/ is cached by exaroton, wait until the command output shows up
        time.sleep(20)
        text = live()
        if any(k in text[-20000:] for k in ("data pack", "Mean tick", "players online")):
            break
    print("--- check output ---")
    for l in text.splitlines()[max(0, before - 5):]:
        if CHECK_KEEP.search(l) and not re.search(r"joined|left|<", l):
            print(UUID.sub("<uuid>", IP.sub("<ip>", l))[:3000])


def set_config(sid):
    path = os.environ.get("CONFIG_PATH", "").strip()
    key = os.environ.get("CONFIG_KEY", "").strip()
    value = os.environ.get("CONFIG_VALUE", "").strip()
    props = (path.endswith(".properties") and path.startswith("config/") and path.count("/") == 1) or path == "server.properties"
    if not ((path.endswith(".toml") and (path.startswith("world/serverconfig/") or path.startswith("config/"))) or props) or ".." in path:
        sys.exit(f"refusing path {path!r}: only *.toml under world/serverconfig/ or config/, or config/*.properties, or server.properties")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", key) or not re.fullmatch(r"[A-Za-z0-9_.\-\"]+", value):
        sys.exit("bad key/value")
    text = (req("GET", f"/servers/{sid}/files/data/{q(path)}", raw=True) or b"").decode()
    if not text and not props:
        sys.exit(f"{path} not found")
    pat = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)([^\s#]+)(.*)$", re.M)
    hits = pat.findall(text)
    if props and not hits:
        print(f"{path}: {key} not set -> adding {key}={value}")
        new = text + ("" if not text or text.endswith("\n") else "\n") + f"{key}={value}\n"
    else:
        if len(hits) != 1:
            sys.exit(f"key {key!r} found {len(hits)} times in {path}")
        print(f"{path}: {key} = {hits[0][1]} -> {value}")
        new = pat.sub(lambda m: m.group(1) + value + m.group(3), text)
    req("PUT", f"/servers/{sid}/files/data/{q(path)}", new.encode(), "application/octet-stream")
    check = (req("GET", f"/servers/{sid}/files/data/{q(path)}", raw=True) or b"").decode()
    print("verify:", [l.strip() for l in check.splitlines() if re.match(rf"\s*{re.escape(key)}\s*=", l)])


sid = find_server()
s = server(sid)
print("before:", status_line(s))

if ACTION == "stop":
    if s["status"] != 1:
        print("server is not online, nothing to stop")
    elif s.get("players", {}).get("count", 0) > 0:
        sys.exit("players online - not stopping")
    else:
        req("GET", f"/servers/{sid}/stop/")
        t = time.time()
        while time.time() - t < 300:
            time.sleep(10)
            s = server(sid)
            if s["status"] in (0, 7):
                break
        print("after:", status_line(s))

if ACTION == "ls":
    path = os.environ.get("CONFIG_PATH", "").strip().strip("/")
    if path.split("/")[0] not in ("world", "config") or ".." in path:
        sys.exit("ls only under world/ or config/")
    print(path, "->", list_dir(sid, path))

if ACTION == "setconfig":
    if s["status"] not in (0, 7):
        print("warning: server is not offline; the change applies after the next restart")
    set_config(sid)

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

if ACTION == "crash":
    files = [c for c in (list_dir(sid, "crash-reports") or []) if c.get("name", "").endswith(".txt")]
    files.sort(key=lambda c: c["name"])
    print("crash-reports:", [c["name"] for c in files[-5:]])
    if files:
        name = files[-1]["name"]
        text = (req("GET", f"/servers/{sid}/files/data/{q('crash-reports/' + name)}", raw=True) or b"").decode(errors="replace")
        print(f"--- {name} ({len(text.splitlines())} lines, IPs/UUIDs redacted) ---")
        for l in text.splitlines()[:400]:
            print(UUID.sub("<uuid>", IP.sub("<ip>", l))[:400])

if ACTION in ("start", "logs") or s["status"] == 7:
    print_log(sid)

if ACTION == "check" or (ACTION == "start" and s["status"] == 1):
    if s["status"] == 1:
        run_check(sid)
    else:
        print("check skipped: server is not online")

if ACTION == "start" and s["status"] != 1:
    sys.exit(f"server did not come online: {STATUS.get(s['status'], s['status'])}")
