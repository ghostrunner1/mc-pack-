import json, os, sys, time, hashlib, urllib.request, urllib.parse, urllib.error

API = "https://api.exaroton.com/v1"
TOKEN = os.environ["EXAROTON_TOKEN"]
SERVER_RAW = os.environ["EXAROTON_SERVER"].strip().rstrip("/").split("/")[-1]
SERVER_ADDR = SERVER_RAW.lower()
LOCAL = os.environ.get("SERVER_FILES", "server-files")
WAIT_MIN = int(os.environ.get("WAIT_MINUTES", "15"))
MANIFEST = ".mc-pack-managed.json"
# directories fully owned by the pack: anything else inside them is removed
OWNED_DIRS = ["mods"]
# files the pack uploads elsewhere are tracked in MANIFEST and only those are removed later
UPLOAD_ROOTS = ["mods", "world/datapacks"]

STATUS = {0: "offline", 1: "online", 2: "starting", 3: "stopping", 4: "restarting",
          5: "saving", 6: "loading", 7: "crashed", 8: "pending", 10: "preparing"}


def req(method, path, data=None, ctype=None, raw=False):
    url = API + path
    headers = {"Authorization": f"Bearer {TOKEN}", "User-Agent": "mc-pack-deploy"}
    if data is not None and ctype:
        headers["Content-Type"] = ctype
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(r, timeout=300) as resp:
                body = resp.read()
                if raw:
                    return body
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            if e.code == 404 and raw:
                return None
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(3 * (attempt + 1))
                continue
            print(f"HTTP {e.code} {method} {path}: {e.read()[:300]!r}")
            raise


def q(path):
    return urllib.parse.quote(path)


def find_server():
    for s in req("GET", "/servers/")["data"]:
        if s["address"].lower() == SERVER_ADDR or s["id"] == SERVER_RAW or s["name"].lower() == SERVER_ADDR:
            return s["id"]
    sys.exit(f"server {SERVER_ADDR} not found in this exaroton account")


def server(sid):
    return req("GET", f"/servers/{sid}/")["data"]


def say(sid, text):
    req("POST", f"/servers/{sid}/command/", json.dumps({"command": f"say {text}"}).encode(), "application/json")


def wait_status(sid, want, timeout=900):
    t = time.time()
    while time.time() - t < timeout:
        st = server(sid)["status"]
        if st in want:
            return st
        time.sleep(10)
    sys.exit(f"timeout waiting for status {want}")


def list_dir(sid, path):
    info = req("GET", f"/servers/{sid}/files/info/{q(path)}/", raw=True)
    if info is None:
        return None
    info = json.loads(info)["data"]
    return info.get("children") or []


SIZES = {}


def walk(sid, path):
    out = []
    kids = list_dir(sid, path)
    if kids is None:
        return out
    for k in kids:
        p = f"{path}/{k['name']}"
        if k.get("isDirectory"):
            out += walk(sid, p)
        else:
            SIZES[p] = k.get("size")
            out.append(p)
    return out


# exaroton's file API rejects bodies over ~100 MB (HTTP 413). A dedicated server never reads a mod's
# assets/ (textures, sounds, models - client only), so big mod jars are uploaded without them.
UPLOAD_LIMIT = 90 * 1024 * 1024


def strip_assets(data):
    import io, zipfile
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename.startswith("assets/"):
                continue
            dst.writestr(info, src.read(info.filename))
    return out.getvalue()


def upload(sid, rel, full):
    with open(full, "rb") as f:
        data = f.read()
    if len(data) > UPLOAD_LIMIT and rel.startswith("mods/") and rel.endswith(".jar"):
        before = len(data)
        data = strip_assets(data)
        print(f"  {rel}: {before // 2**20} MB > limit, uploading without assets/ ({len(data) // 2**20} MB)")
    if len(data) > UPLOAD_LIMIT:
        sys.exit(f"{rel} is {len(data) // 2**20} MB, exaroton file API limit is ~100 MB")
    req("PUT", f"/servers/{sid}/files/data/{q(rel)}", data, "application/octet-stream")


def delete(sid, rel):
    req("DELETE", f"/servers/{sid}/files/data/{q(rel)}")


def main():
    sid = find_server()
    s = server(sid)
    print("server", s["name"], s["address"], STATUS.get(s["status"], s["status"]))

    # start the server after the update only if we took it down from under players
    # (or someone started it while the update was running)
    restart_after = False

    if s["status"] in (1, 2, 6, 10):
        if s["status"] != 1:
            wait_status(sid, {1})
        say(sid, f"Вышло обновление сборки. Сервер выключится через {WAIT_MIN} мин для установки, обновление займёт до 15 минут. После него перезапустите игру — моды обновятся сами.")
        deadline = time.time() + WAIT_MIN * 60
        warned = set()
        while time.time() < deadline:
            players = server(sid).get("players", {}).get("count", 0)
            if players > 0:
                restart_after = True
            if players == 0:
                print("no players online, updating now")
                break
            left = int((deadline - time.time()) // 60) + 1
            if left in (5, 1) and left not in warned:
                warned.add(left)
                say(sid, f"Сервер выключится через {left} мин для обновления сборки.")
            time.sleep(30)
        req("GET", f"/servers/{sid}/stop/")
        wait_status(sid, {0, 7})
    elif s["status"] not in (0, 7):
        wait_status(sid, {0, 7})

    target = {}
    for root, _, files in os.walk(LOCAL):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, LOCAL).replace(os.sep, "/")
            if rel.split("/")[0] in ("mods", "tacz") or rel.startswith("world/datapacks/"):
                target[rel] = full

    old_manifest = {}
    raw = req("GET", f"/servers/{sid}/files/data/{q(MANIFEST)}", raw=True)
    if raw:
        old_manifest = json.loads(raw)
    sums = {rel: hashlib.sha1(open(full, "rb").read()).hexdigest() for rel, full in target.items()}

    remote = set()
    for d in UPLOAD_ROOTS:
        remote |= set(walk(sid, d))
    # tacz/ also holds TaCZ's own extracted default gun pack: only look at top-level files
    for k in list_dir(sid, "tacz") or []:
        if not k.get("isDirectory"):
            SIZES["tacz/" + k["name"]] = k.get("size")
            remote.add("tacz/" + k["name"])

    to_delete = set()
    for p in remote:
        top = p.split("/")[0]
        if top in OWNED_DIRS and p not in target:
            to_delete.add(p)
        elif p in old_manifest and p not in target:
            to_delete.add(p)
    for p in sorted(to_delete):
        print("delete", p)
        delete(sid, p)

    uploaded = 0
    last_check = 0
    for rel, full in sorted(target.items()):
        if time.time() - last_check > 60:
            last_check = time.time()
            st = server(sid)["status"]
            if st not in (0, 7):
                print("server was started during the update (status", STATUS.get(st, st), ") - stopping it again")
                restart_after = True
                if st != 3:
                    wait_status(sid, {1})
                    say(sid, "Сервер обновляется, он выключится. Подождите окончания обновления.")
                    req("GET", f"/servers/{sid}/stop/")
                wait_status(sid, {0, 7})
        if rel in remote and old_manifest.get(rel) == sums[rel]:
            continue
        if rel in remote and rel not in old_manifest and SIZES.get(rel) == os.path.getsize(full):
            continue  # same name and size, uploaded by an interrupted run
        print("upload", rel)
        upload(sid, rel, full)
        uploaded += 1

    req("PUT", f"/servers/{sid}/files/data/{q(MANIFEST)}", json.dumps(sums, indent=1).encode(), "application/octet-stream")
    print(f"uploaded {uploaded} files, deleted {len(to_delete)}, unchanged {len(target) - uploaded}")

    if restart_after:
        req("GET", f"/servers/{sid}/start/")
        print("server start requested")
    else:
        print("server was not in use before the update - leaving it offline")


if __name__ == "__main__":
    main()
