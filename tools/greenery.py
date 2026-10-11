"""Plant the real forests and parks.

Reads OpenStreetMap woods, forests and parks (cities/*.green.overpassql). Forest outlines are filled
with trees about 14 m apart, parks with scattered trees about 45 m apart, never on a street, a track
or a building. Trees go on the whole map, owned or not. Named parks on owned land over 2 hectares get their name on a short footpath,
in capitals like the landmarks. Run it once: it does not look for trees that are already there.

The game holds 262,144 trees; the script says how many it would plant before doing it.

Use (from the repo root, a city loaded): py tools\\greenery.py <green.osm.json> <city.toml> [--live] [--forest 14] [--park 45]
"""
import json, math, os, random, sys, tomllib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "landmarks"))

import kit
from zones import inside, projector

# Danish woods are mostly beech; kinds that are not loaded are left out
FOREST = ["Beech01low", "Beech01low", "Beech01low", "Green Tree 01", "Silver Birch", "Alder01", "Norway Spruce"]
PARK = ["mp9-HorseChestnutvnl", "mp9-YoungLinden", "Beech01low", "Green Tree 01", "CherryTree01"]


def option(name, default):
    return float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def main():
    live = "--live" in sys.argv
    project = projector(tomllib.load(open(sys.argv[2], "rb")))
    rng = random.Random(7)
    loaded = kit.call("/commands/plant-trees", {})["prefabs"].split(";")
    forest_kinds = [k for k in FOREST if k in loaded] or loaded[:3]
    park_kinds = [k for k in PARK if k in loaded] or loaded[:2]

    owned = [(t["minX"], t["minZ"], t["maxX"], t["maxZ"]) for t in kit.call("/state/owned-tiles")["tiles"]]
    cell = 16.0
    blocked = set()             # 16 m squares with a street, a track or a building in them
    for service in ("Road", "PublicTransport"):
        for s in kit.call(f"/state/networks?service={service}&limit=65536")["segments"]:
            n = max(1, int(math.dist((s["start"]["x"], s["start"]["z"]), (s["end"]["x"], s["end"]["z"])) / 8))
            for k in range(n + 1):
                x = s["start"]["x"] + (s["end"]["x"] - s["start"]["x"]) * k / n
                z = s["start"]["z"] + (s["end"]["z"] - s["start"]["z"]) * k / n
                blocked.update((int(x // cell) + dx, int(z // cell) + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1))
    buildings = kit.call("/state/growables?limit=65536")["growables"]
    for service in ("", "&service=Monument", "&service=Electricity", "&service=Water", "&service=PublicTransport", "&service=Beautification"):
        buildings += kit.call("/state/facilities?limit=65536" + service)["facilities"]
    for b in buildings:
        reach = int(max(b["width"], b["length"]) * 4 // cell) + 1
        bx, bz = int(b["position"]["x"] // cell), int(b["position"]["z"] // cell)
        blocked.update((bx + dx, bz + dz) for dx in range(-reach, reach + 1) for dz in range(-reach, reach + 1))

    plant, signs = {k: [] for k in forest_kinds + park_kinds}, []
    for e in json.load(open(sys.argv[1], encoding="utf-8"))["elements"]:
        tags = e.get("tags", {})
        park = tags.get("leisure") == "park"
        step = option("--park", 45) if park else option("--forest", 14)
        rings = [e["geometry"]] if e["type"] == "way" else [m["geometry"] for m in e.get("members", []) if m.get("role") == "outer" and "geometry" in m]
        area, centre = 0.0, None
        for ring in rings:
            pts = [project(q["lat"], q["lon"]) for q in ring]
            if len(pts) < 3:
                continue
            xs, zs = [p[0] for p in pts], [p[1] for p in pts]
            area += abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2
            centre = centre or (sum(xs) / len(xs), sum(zs) / len(zs))
            z = min(zs) + step / 2
            while z < max(zs):
                x = min(xs) + step / 2
                while x < max(xs):
                    p = (x + rng.uniform(-step, step) * 0.35, z + rng.uniform(-step, step) * 0.35)
                    if (int(p[0] // cell), int(p[1] // cell)) not in blocked and inside(p, pts) and abs(p[0]) < 8600 and abs(p[1]) < 8600:
                        plant[rng.choice(park_kinds if park else forest_kinds)].append(p)
                    x += step
                z += step
        if park and tags.get("name") and area > 20000 and centre and any(a <= centre[0] <= c and b <= centre[1] <= d for a, b, c, d in owned):
            signs.append((tags["name"], centre))

    total = sum(len(v) for v in plant.values())
    print(f"trees to plant: {total} ({', '.join(f'{len(v)} {k}' for k, v in plant.items() if v)}); park name signs: {len(signs)}")
    if not live:
        print("DRY RUN: nothing was planted")
        return
    planted = 0
    for kind, points in plant.items():
        for i in range(0, len(points), 400):
            r = kit.call("/commands/plant-trees", {"prefab": kind, "points": ";".join(f"{x:.1f},{z:.1f}" for x, z in points[i:i + 400])})
            planted += r.get("planted", 0)
    named = sum(kit.label(name.replace('"', ""), x, z, 0, 60, 0, gap=0) for name, (x, z) in signs)
    print(f"trees planted: {planted}; park names: {named}")


if __name__ == "__main__":
    main()
