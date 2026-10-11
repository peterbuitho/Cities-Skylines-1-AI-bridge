"""Rebuild the city's water pipes so that every water tower and treatment plant counts.

How the game serves water and sewage (WaterManager.SimulationStepImpl):
- ground is served within 100 m of a pipe junction (node), not along the pipe, so junctions must
  stand about 150 m apart at most;
- each cycle it makes one "pulse group" per junction that has a source on it or users near it,
  going through the junctions in id order, and stops at 1,024 groups. A source on a junction past
  that number adds nothing: a treatment plant there has no capacity, a tower gives no water.
  Users on such junctions are still served, as long as the sources got their groups.

A city this wide has far more than 1,024 junctions with users, so the sources must hold the lowest
junction ids. The game hands out ids last-freed-first, so this script removes every source and pipe
(pipes with the lowest ids last), then builds the sources' own pipes and the sources first, and the
rest of a 150 m lattice after them. It also adds spare towers and treatment plants now, because a
source added later gets a high id and may not count; run the script again when more are needed.

Use (from the repo root, a city loaded and paused): py tools\\repipe.py [--live] [--towers 120] [--plants 45]
"""
import collections, math, sys

from zones import call

GRID = 150.0


def pipe(a, b):
    r = call("/commands/build-network", {"dryRun": False, "roadPrefab": "Water Pipe", "name": "Vandforsyning",
                                         "start": {"x": round(a[0], 1), "z": round(a[1], 1)}, "end": {"x": round(b[0], 1), "z": round(b[1], 1)}})
    return bool(r.get("ok"))


def chain(a, b):
    """Pipe from a to b in pieces of at most GRID."""
    n = max(1, math.ceil(math.dist(a, b) / GRID))
    pts = [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]
    return sum(pipe(p, q) for p, q in zip(pts, pts[1:]))


def option(name, default):
    return int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def main():
    live = "--live" in sys.argv
    buildings = [(g["position"]["x"], g["position"]["z"]) for g in call("/state/growables?limit=65536")["growables"]]
    water = call("/state/facilities?limit=65536&service=Water")["facilities"]
    for service in ("", "&service=Monument", "&service=Electricity", "&service=PublicTransport", "&service=Beautification"):
        buildings += [(f["position"]["x"], f["position"]["z"]) for f in call("/state/facilities?limit=65536" + service)["facilities"]
                      if f["prefab"] not in ("Wind Turbine", "Advanced Wind Turbine", "Electricity Pole")]
    users = buildings + [(s["middle"]["x"], s["middle"]["z"]) for s in call("/state/networks?service=Road&limit=65536")["segments"]
                         if "Highway" not in s["prefab"]]

    world = lambda n: (n[0] * GRID, n[1] * GRID)
    nodes = {(round(x / GRID), round(z / GRID)) for x, z in users}
    pieces = [(n, m) for n in nodes for m in ((n[0] + 1, n[1]), (n[0], n[1] + 1)) if m in nodes]

    # one network: join every separate part to the largest with a straight pipe
    parent = {n: n for n in nodes}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for a, b in pieces:
        parent[find(a)] = find(b)
    groups = collections.defaultdict(list)
    for n in nodes:
        groups[find(n)].append(n)
    main_group = max(groups.values(), key=len)
    far = []
    for g in groups.values():
        if g is not main_group:
            a = min(g, key=lambda n: min(abs(n[0] - m[0]) + abs(n[1] - m[1]) for m in main_group[::7]))
            far.append((a, min(main_group, key=lambda m: math.dist(m, a))))

    # sources: the ones standing now, plus spares
    towers = [(f["position"]["x"], f["position"]["z"], 0.0, "Water Tower") for f in water if f["prefab"] == "Water Tower"]
    plants = [(f["position"]["x"], f["position"]["z"], f["angleDegrees"] % 360, f["prefab"]) for f in water if "Treatment" in f["prefab"] or "Outlet" in f["prefab"]]
    taken = buildings + [(t[0], t[1]) for t in towers + plants]
    roads = [(s["middle"]["x"], s["middle"]["z"]) for s in call("/state/networks?service=Road&limit=65536")["segments"] + call("/state/networks?service=PublicTransport&limit=65536")["segments"]]
    built_up = sorted(collections.Counter((round(x / GRID), round(z / GRID)) for x, z in buildings).items(), key=lambda kv: -kv[1])
    for n, _ in built_up:                                   # spare towers where the buildings are, well apart
        if len(towers) >= option("--towers", 120):
            break
        p = (world(n)[0] + 40, world(n)[1] + 40)
        if all(math.dist(p, (t[0], t[1])) > 500 for t in towers) and all(math.dist(p, q) > 30 for q in taken) and all(math.dist(p, q) > 30 for q in roads):
            towers.append((p[0], p[1], 0.0, "Water Tower"))
    for x, z, angle, prefab in list(plants):                # spare plants along the same shore
        for dz in (90, -90):
            p = (x, z + dz)
            if len(plants) < option("--plants", 45) and all(math.dist(p, (q[0], q[1])) > 85 for q in plants):
                plants.append((p[0], p[1], angle, prefab))
    sources = plants + towers

    old = call("/state/networks?service=Water&limit=65536")["segments"]
    print(f"old pipes: {len(old)} pieces; new lattice: {len(pieces)} pieces on {len(nodes)} junctions, {len(far)} far links; "
          f"sources: {len(plants)} treatment plants, {len(towers)} towers")
    if not live:
        print("DRY RUN: nothing was changed")
        return

    for f in water:
        call("/commands/bulldoze", {"entityType": "building", "id": f["id"]})
    for s in sorted(old, key=lambda s: -min(s["startNodeId"], s["endNodeId"])):     # lowest junction ids freed last, so reused first
        call("/commands/bulldoze", {"entityType": "netSegment", "id": s["id"]})

    # sources first: a pipe from the nearest lattice point to each, then the building on its end
    stood = 0
    for x, z, angle, prefab in sources:
        n = (round(x / GRID), round(z / GRID))
        if n not in nodes:
            n = min(nodes, key=lambda m: math.dist(world(m), (x, z)))
        chain(world(n), (x, z))
        if prefab != "Water Tower":     # a plant joins a pipe that runs across it, and that pipe needs its own way to the lattice
            pipe((x - 60, z), (x + 30, z))
            for end in ((x - 60, z), (x + 30, z)):
                chain(end, world(min(nodes, key=lambda m: math.dist(world(m), end))))
        stood += bool(call("/commands/place-building", {"dryRun": False, "buildingPrefab": prefab, "position": {"x": x, "z": z}, "angleDegrees": angle}).get("ok"))
    print(f"sources placed: {stood} of {len(sources)}")
    built = sum(pipe(world(a), world(b)) for a, b in pieces) + sum(chain(world(a), world(b)) for a, b in far)
    print(f"lattice pieces built: {built}")
    print("served ground recomputed:", call("/commands/refresh-water-grid", {}).get("ok"))

    ids = sorted({i for s in call("/state/networks?service=Water&limit=65536")["segments"] for i in (s["startNodeId"], s["endNodeId"])})
    print(f"pipe junctions: {len(ids)}; the 1,024th lowest id is {ids[min(1023, len(ids) - 1)]}")


if __name__ == "__main__":
    main()
