"""Put the planned streets of one neighbourhood back into a thinned city.

Builds every plan segment whose middle lies within <radius> metres of <x,z> and is not in the game
yet. The game's path finder gives out at roughly 13,000-17,000 road segments (see PLAN.md), so add
one neighbourhood at a time and check that newcomers still arrive.

Use: add_streets.py <plan.json> <x,z> <radius> [--live]
     add_streets.py <plan.json> work <plandata.json> <city.toml> <minX,minZ,maxX,maxZ> [--live]

The second form builds the streets inside business and centre areas of the municipal plan (plandata
anvgen 31 and 41). Without them that land cannot be zoned, the city runs out of jobs, and then the
game sends no more residents however much housing land is free.
"""
import json, math, sys, urllib.error, urllib.request

B = "http://127.0.0.1:32123"


def call(path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(B + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))


def key(a, b):
    a, b = (round(a[0] * 100), round(a[1] * 100)), (round(b[0] * 100), round(b[1] * 100))
    return (min(a, b), max(a, b))


def main():
    live = "--live" in sys.argv
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    nodes = plan["nodes"]
    if sys.argv[2] == "work":
        import tomllib
        from zones import inside, plandata_areas, projector
        features = [f for f in json.load(open(sys.argv[3], encoding="utf-8"))["features"] if f["properties"].get("anvgen") in (31, 41)]
        min_x, min_z, max_x, max_z = (float(v) for v in sys.argv[5].split(","))
        rings = [ring for ring, _ in plandata_areas(features, projector(tomllib.load(open(sys.argv[4], "rb"))))]
        boxes = [(min(q[0] for q in r), min(q[1] for q in r), max(q[0] for q in r), max(q[1] for q in r), r) for r in rings if len(r) >= 3]

        def chosen(x, z):
            return min_x <= x <= max_x and min_z <= z <= max_z and any(a <= x <= c and b <= z <= d and inside((x, z), r) for a, b, c, d, r in boxes)
    else:
        cx, cz = (float(v) for v in sys.argv[2].split(","))
        radius = float(sys.argv[3])

        def chosen(x, z):
            return math.hypot(x - cx, z - cz) <= radius

    roads = call("/state/networks?service=Road&limit=65536")
    assert roads["total"] == len(roads["segments"]), "the bridge cut the road list short"
    have = {key((r["start"]["x"], r["start"]["z"]), (r["end"]["x"], r["end"]["z"])) for r in roads["segments"]}

    wanted = []
    for s in plan["segments"]:
        a, b = nodes[s["a"]], nodes[s["b"]]
        if key(a, b) not in have and chosen((a[0] + b[0]) / 2, (a[1] + b[1]) / 2):
            wanted.append((s, a, b))
    names = sorted({s["name"] for s, _, _ in wanted if s.get("name")})
    print(f"roads in game: {roads['total']}; to add: {len(wanted)} segments on {len(names)} named streets")
    print("streets:", ", ".join(names[:40]) + (" ..." if len(names) > 40 else ""))
    if not live:
        print("DRY RUN: nothing was built")
        return

    built = 0
    for s, a, b in wanted:
        r = call("/commands/build-network", {"dryRun": False, "roadPrefab": s["prefab"], "name": s.get("name", ""),
                 "start": {"x": a[0], "z": a[1]}, "end": {"x": b[0], "z": b[1]}})
        built += bool(r.get("ok"))
    print(f"built: {built}, failed: {len(wanted) - built}")


if __name__ == "__main__":
    main()
