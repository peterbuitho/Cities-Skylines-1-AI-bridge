"""Join every map-edge highway connection that has no driving route to the city with a short link road.
Needs the mod build in mod/ (reads /state/move-in). Use: highway_links.py [--live]"""
import json, sys, urllib.request, collections, math
LIVE = "--live" in sys.argv
B = "http://127.0.0.1:32123"
def call(path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(B + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r: return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e: return json.loads(e.read().decode("utf-8"))
r = call("/state/networks?service=Road&limit=65536"); segs = r["segments"]; assert r["total"] == len(segs)
mv = call("/state/move-in")
src = [n["id"] for n in mv["outsideNodes"] if n["service"] == "Road" and any(s["nodeIsStart"] for s in n["segments"])]
snk = [n["id"] for n in mv["outsideNodes"] if n["service"] == "Road" and not any(s["nodeIsStart"] for s in n["segments"])]
ow = lambda p: "Highway" in p or "Oneway" in p
raised = lambda p: any(w in p for w in ("Elevated", "Bridge", "Tunnel", "Slope"))
hy = {}
pos, fwd, back, pre = {}, collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(set)
for s in segs:
    a, b = s["startNodeId"], s["endNodeId"]
    pos[a] = (s["start"]["x"], s["start"]["z"]); pos[b] = (s["end"]["x"], s["end"]["z"]); hy[a] = s["start"]["y"]; hy[b] = s["end"]["y"]; pre[a].add(s["prefab"]); pre[b].add(s["prefab"])
    fwd[a].append(b); back[b].append(a)
    if not ow(s["prefab"]): fwd[b].append(a); back[a].append(b)
def reach(start, g):
    seen = set(start); q = list(start)
    while q:
        n = q.pop()
        for m in g[n]:
            if m not in seen: seen.add(m); q.append(m)
    return seen
home = min(pos, key=lambda n: (pos[n][0] + 1600) ** 2 + (pos[n][1] - 400) ** 2)
core = reach([home], fwd) & reach([home], back)
twoway = [n for n in core if pre[n] <= {"Basic Road", "Medium Road"}]
print("city core nodes:", len(core), "two-way core nodes:", len(twoway))
links = []
def nearest(cands):
    best = None
    for n in cands:
        if abs(pos[n][0]) > 8300 or abs(pos[n][1]) > 8300: continue
        for c in twoway:
            d = math.hypot(pos[n][0] - pos[c][0], pos[n][1] - pos[c][1])
            if d >= max(8, 5 * abs(hy[n] - hy[c])) and (best is None or d < best[0]): best = (d, n, c)
    return best
for kind, ids, g in (("IN ", src, fwd), ("OUT", snk, back)):
    for o in ids:
        R = reach([o], g)
        ok = bool(R & core)
        line = f"{kind} connection node {o} at {pos[o][0]:.0f},{pos[o][1]:.0f}: highway nodes {len(R)}, joined to city: {ok}"
        if not ok:
            b = nearest(R)
            if b: line += f" | nearest gap {b[0]:.0f} m (height diff {hy[b[1]] - hy[b[2]]:.0f} m): {b[1]} {pos[b[1]]} -> {b[2]} {pos[b[2]]}"; links.append(b)
            else: line += " | no ground-level highway node"
        print(line)
done = set()
for d, n, c in links:
    if (n, c) in done or d > 400: print("skip", n, c, round(d)); continue
    done.add((n, c))
    k = max(1, math.ceil(d / 90)); pts = [(pos[n][0] + (pos[c][0] - pos[n][0]) * i / k, pos[n][1] + (pos[c][1] - pos[n][1]) * i / k) for i in range(k + 1)]
    for p, q in zip(pts, pts[1:]):
        res = call("/commands/build-network", {"dryRun": not LIVE, "roadPrefab": "Basic Road", "name": "Motorvejstilslutning",
                   "start": {"x": round(p[0], 2), "z": round(p[1], 2)}, "end": {"x": round(q[0], 2), "z": round(q[1], 2)}})
        print("  link piece", "LIVE" if LIVE else "dry", res.get("ok"), res.get("error", ""))

