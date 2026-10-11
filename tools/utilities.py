"""Water and power for everything zones.py zoned.

Lays a 96 m grid of water pipe under the zoned land, joins it to the pipes already in the game,
and seeds power and water supply: zoned land only develops near a powered building, so a wind
turbine goes in every 384 m, and a water tower with every eighth turbine.

Use (from the repo root): py tools\\utilities.py <landuse.osm.json> <city.toml> <minX,minZ,maxX,maxZ> <centreX,centreZ> [--live]
"""
import json, math, sys, tomllib

from zones import call, plan, projector

GRID, REACH, SEED_EVERY = 96, 70.0, 4


def pipe(a, b):
    r = call("/commands/build-network", {"dryRun": False, "roadPrefab": "Water Pipe", "name": "Vandforsyning",
             "start": {"x": a[0], "z": a[1]}, "end": {"x": b[0], "z": b[1]}})
    return bool(r.get("ok"))


def straight(a, b):
    """Pieces of at most 90 m from a to b."""
    n = max(1, math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / 90))
    pts = [(round(a[0] + (b[0] - a[0]) * i / n, 2), round(a[1] + (b[1] - a[1]) * i / n, 2)) for i in range(n + 1)]
    return list(zip(pts, pts[1:]))


def main():
    live = "--live" in sys.argv
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    bounds = [float(v) for v in sys.argv[3].split(",")]
    centre = [float(v) for v in sys.argv[4].split(",")]
    cells, _ = plan(data, projector(tomllib.load(open(sys.argv[2], "rb"))), bounds, centre)
    zoned = [p for p, zone in cells.items() if zone != "Unzoned"]

    # grid nodes with zoned land in reach
    near = set()
    for x, z in zoned:
        for j in (math.floor(x / GRID), math.ceil(x / GRID)):
            for k in (math.floor(z / GRID), math.ceil(z / GRID)):
                if math.hypot(j * GRID - x, k * GRID - z) <= REACH:
                    near.add((j, k))
    edges = [((j, k), (j + 1, k)) for j, k in near if (j + 1, k) in near]
    edges += [((j, k), (j, k + 1)) for j, k in near if (j, k + 1) in near and j % 3 == 0]

    # join the pieces of the grid to each other, then to the pipes already there
    parent = {n: n for n in near}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for a, b in edges:
        parent[find(a)] = find(b)
    groups = {}
    for n in near:
        groups.setdefault(find(n), []).append(n)
    world = lambda n: (n[0] * GRID, n[1] * GRID)
    ordered = sorted(groups.values(), key=len, reverse=True)
    links = []
    main_group = list(ordered[0]) if ordered else []
    for group in ordered[1:]:
        a, b = min(((p, q) for p in group for q in main_group[::7] or main_group),
                   key=lambda pq: (pq[0][0] - pq[1][0]) ** 2 + (pq[0][1] - pq[1][1]) ** 2)
        links += straight(world(a), world(b))
        main_group += group

    seeds = sorted(n for n in near if n[0] % SEED_EVERY == 0 and n[1] % SEED_EVERY == 0)
    print(f"zoned points: {len(zoned)}; pipe grid nodes: {len(near)}; pipe pieces: {len(edges) + len(links)}; "
          f"separate pipe areas joined: {max(0, len(ordered) - 1)}; wind turbines: {len(seeds)}; water towers: {len(seeds[::8])}")
    if not live:
        print("DRY RUN: nothing was built")
        return

    built = sum(pipe(world(a), world(b)) for a, b in edges) + sum(pipe(a, b) for a, b in links)
    existing = [(s[k]["x"], s[k]["z"]) for s in call("/state/networks?service=Water&limit=65536")["segments"]
                if s["name"] != "Vandforsyning" for k in ("start", "end")]
    if existing and main_group:
        a, b = min(((p, world(q)) for p in existing for q in main_group[::5]),
                   key=lambda pq: (pq[0][0] - pq[1][0]) ** 2 + (pq[0][1] - pq[1][1]) ** 2)
        built += sum(pipe(p, q) for p, q in straight((round(a[0], 2), round(a[1], 2)), b))
    print("pipe pieces built:", built)

    turbines = towers = 0
    for i, n in enumerate(seeds):
        x, z = world(n)
        turbines += bool(call("/commands/place-building", {"dryRun": False, "buildingPrefab": "Wind Turbine",
                                                           "position": {"x": x + 24, "z": z + 24}, "angleDegrees": 0}).get("ok"))
        if i % 8 == 0:
            towers += bool(call("/commands/place-building", {"dryRun": False, "buildingPrefab": "Water Tower",
                                                             "position": {"x": x - 24, "z": z - 24}, "angleDegrees": 0}).get("ok"))
    print(f"wind turbines placed: {turbines}, water towers placed: {towers}")


if __name__ == "__main__":
    main()
