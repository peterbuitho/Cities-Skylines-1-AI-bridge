"""Real schools, hospitals, fire and police stations, libraries, cemeteries and recycling centres.

Positions come from OpenStreetMap (cities/*.civic.overpassql). Each becomes the game's own building
of that kind, beside the nearest street and facing it. A site is skipped when a building of the
same kind already stands within its spacing, so the script can be run again after the city grows.

Use (from the repo root, a city loaded): py tools\\civic.py <civic.osm.json> <city.toml> <minX,minZ,maxX,maxZ> [--live]
"""
import collections, json, math, os, sys, tomllib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "landmarks"))

import kit
from zones import projector

# kind in OpenStreetMap: (game building, width, depth in metres, least distance to the next of its kind)
KINDS = {
    "school": ("Elementary School", 48, 32, 350),
    "college": ("High School", 48, 40, 700),
    "university": ("University", 112, 64, 1200),
    "hospital": ("Hospital", 80, 64, 1200),
    "clinic": ("Medical Clinic", 32, 32, 500),
    "fire_station": ("Fire Station", 48, 32, 600),
    "police": ("Police Headquarters", 48, 32, 600),
    "library": ("Library 01", 80, 64, 900),
    "cemetery": ("Cemetery", 80, 64, 700),
    "crematorium": ("Crematory", 24, 24, 500),
    "recycling": ("Recycling Center", 56, 32, 700),
}


def main():
    live = "--live" in sys.argv
    project = projector(tomllib.load(open(sys.argv[2], "rb")))
    min_x, min_z, max_x, max_z = (float(v) for v in sys.argv[3].split(","))
    sites = []
    for e in json.load(open(sys.argv[1], encoding="utf-8"))["elements"]:
        tags = e.get("tags", {})
        kind = tags.get("amenity") or tags.get("landuse")
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if kind in KINDS and lat is not None:
            x, z = project(lat, lon)
            if min_x <= x <= max_x and min_z <= z <= max_z:
                sites.append((kind, x, z))

    roads = [s for s in kit.call("/state/networks?service=Road&limit=65536")["segments"] if "Highway" not in s["prefab"]]
    growables = kit.call("/state/growables?limit=65536")["growables"]
    fixed = kit.call("/state/facilities?limit=65536")["facilities"] + kit.call("/state/facilities?limit=65536&service=Monument")["facilities"]
    taken = [(f["position"]["x"], f["position"]["z"], 30.0) for f in fixed]
    standing = collections.defaultdict(list)
    for f in fixed:
        standing[f["prefab"]].append((f["position"]["x"], f["position"]["z"]))

    counts = collections.Counter()
    for kind, x, z in sites:
        prefab, width, depth, spacing = KINDS[kind]
        if any(math.hypot(x - sx, z - sz) < spacing for sx, sz in standing[prefab]):
            counts[kind, "there already"] += 1
        elif not live:
            standing[prefab].append((x, z))
            counts[kind, "to place"] += 1
        elif kit.beside_road(prefab, x, z, width, depth, roads, growables, taken):
            standing[prefab].append((x, z))
            counts[kind, "placed"] += 1
        else:
            counts[kind, "no room"] += 1
    for (kind, what), n in sorted(counts.items()):
        print(f"{n:3d} {kind}: {what}")
    if not live:
        print("DRY RUN: nothing was built")


if __name__ == "__main__":
    main()
