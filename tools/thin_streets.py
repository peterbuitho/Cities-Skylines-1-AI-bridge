"""Keep small streets only within R metres of the centre; main roads stay everywhere.
Use: thin_streets.py <plan.json> <R> [--live]"""
import json, math, sys, urllib.request, urllib.error
R = float(sys.argv[2]); LIVE = "--live" in sys.argv
B = "http://127.0.0.1:32123"
def call(path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(B + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r: return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e: return json.loads(e.read().decode("utf-8"))
plan = json.load(open(sys.argv[1], encoding="utf-8"))
N = plan["nodes"]; CX, CZ = -1600, 400
MINOR = {"residential", "unclassified", "living_street"}
def key(a, b):
    a, b = (round(a[0] * 100), round(a[1] * 100)), (round(b[0] * 100), round(b[1] * 100))
    return (min(a, b), max(a, b))
minor = set()
for s in plan["segments"]:
    a, b = N[s["a"]], N[s["b"]]
    if s["class"] in MINOR and math.hypot((a[0] + b[0]) / 2 - CX, (a[1] + b[1]) / 2 - CZ) > R: minor.add(key(a, b))
roads = call("/state/networks?service=Road&limit=65536"); assert roads["total"] == len(roads["segments"])
hits = [r["id"] for r in roads["segments"] if key((r["start"]["x"], r["start"]["z"]), (r["end"]["x"], r["end"]["z"])) in minor]
print(f"roads in game: {roads['total']}; small streets beyond {R:.0f} m to remove: {len(hits)}; left: {roads['total'] - len(hits)}")
if LIVE:
    ok = 0
    for i, sid in enumerate(hits):
        ok += bool(call("/commands/bulldoze", {"entityType": "netSegment", "id": sid}).get("ok"))
        if i % 2000 == 1999: print("  removed", ok, "of", i + 1, flush=True)
    print("removed:", ok, "failed:", len(hits) - ok)
