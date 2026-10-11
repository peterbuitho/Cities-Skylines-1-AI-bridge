"""Place real power plants, water works, wastewater plants and waste sites.

Reads OpenStreetMap infrastructure (see cities/*.infrastructure.overpassql) and puts the nearest
thing the game has at each real position inside the given bounds, beside the closest street and
facing it. Without --live it only lists what it found and what it would place.

Use (from the repo root): py tools\\infrastructure.py <infrastructure.osm.json> <city.toml> <minX,minZ,maxX,maxZ> [--live]

The game has no biomass or gas plants, so solid fuel plants become coal plants and gas plants oil
plants. A wastewater plant needs open water beside it and is skipped when the real site has none.
"""
import json, math, sys, tomllib

from zones import call, projector

# (OpenStreetMap kind, energy source) -> (game building, depth in metres, needs open water)
POWER = {"coal": "Coal Power Plant", "biomass": "Coal Power Plant", "wood": "Coal Power Plant", "waste": "Combustion Plant",
         "biogas": "Combustion Plant", "gas": "Oil Power Plant", "oil": "Oil Power Plant", "diesel": "Oil Power Plant",
         "wind": "Wind Turbine", "solar": "Solar Power Plant"}
OTHER = {"water_works": "Water Tower", "water_tower": "Water Tower", "wastewater_plant": "Water Treatment Plant",
         "landfill": "Landfill Site", "recycling": "Recycling Center", "waste_transfer_station": "Recycling Center"}


def choose(tags):
    kind = tags.get("power") or tags.get("man_made") or tags.get("amenity") or tags.get("landuse")
    if kind in ("plant", "generator"):
        source = (tags.get("plant:source") or tags.get("generator:source") or "").split(";")[0]
        return kind, source, POWER.get(source)
    return kind, "", OTHER.get(kind)


def main():
    live = "--live" in sys.argv
    project = projector(tomllib.load(open(sys.argv[2], "rb")))
    min_x, min_z, max_x, max_z = (float(v) for v in sys.argv[3].split(","))
    found = []
    for e in json.load(open(sys.argv[1], encoding="utf-8"))["elements"]:
        tags = e.get("tags", {})
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if lat is None:
            continue
        x, z = project(lat, lon)
        kind, source, prefab = choose(tags)
        found.append((kind, source, tags.get("name", ""), x, z, prefab))

    inside = [f for f in found if min_x <= f[3] <= max_x and min_z <= f[4] <= max_z]
    print(f"{len(found)} real sites in the data, {len(inside)} inside the bounds")
    for kind, source, name, x, z, prefab in sorted(found, key=lambda f: (f[0], f[1], f[2])):
        if kind in ("plant", "wastewater_plant", "water_works", "landfill") or (kind, source, name, x, z, prefab) in inside:
            where = "inside" if min_x <= x <= max_x and min_z <= z <= max_z else "outside"
            print(f"  {where:7s} {kind:18s} {source:8s} {name[:38]:38s} {x:7.0f},{z:7.0f} -> {prefab or 'nothing in the game'}")
    if not live:
        print("DRY RUN: nothing was placed")
        return

    sizes = {b["name"]: (b["width"] * 8, b["length"] * 8) for b in call("/prefabs/buildings?limit=65536")["buildings"]}
    roads = [s for s in call("/state/networks?service=Road&limit=65536")["segments"] if s["prefab"] in ("Basic Road", "Medium Road")]
    growables = call("/state/growables?limit=65536")["growables"]
    placed = []
    for kind, source, name, x, z, prefab in inside:
        if prefab not in sizes:
            continue
        width, depth = sizes[prefab]
        if prefab == "Water Treatment Plant":
            row = call(f"/state/terrain?minX={round(x) - 200}&maxX={round(x) + 200}&minZ={round(z)}&maxZ={round(z)}&step=20")["rows"][0]
            if "~" not in row:
                print(f"  skipped {name or kind}: no open water at the real site")
                continue
        if any(math.hypot(x - p[2], z - p[3]) < 60 for p in placed):
            continue  # one site, mapped twice
        done = False
        for s in sorted(roads, key=lambda s: (s["middle"]["x"] - x) ** 2 + (s["middle"]["z"] - z) ** 2)[:30]:
            dx, dz = s["end"]["x"] - s["start"]["x"], s["end"]["z"] - s["start"]["z"]
            length = math.hypot(dx, dz)
            if length < 30:
                continue
            nx, nz = -dz / length, dx / length
            side = 1 if (x - s["middle"]["x"]) * nx + (z - s["middle"]["z"]) * nz >= 0 else -1
            px, pz = s["middle"]["x"] + side * nx * (10 + depth / 2), s["middle"]["z"] + side * nz * (10 + depth / 2)
            if any(o is not s and math.hypot(o["middle"]["x"] - px, o["middle"]["z"] - pz) < depth / 2 + 8 for o in roads):
                continue
            if any(math.hypot(p[0] - px, p[1] - pz) < max(width, depth) for p in placed):
                continue
            for g in growables:
                if math.hypot(g["position"]["x"] - px, g["position"]["z"] - pz) < max(width, depth) / 2 + 8:
                    call("/commands/bulldoze", {"entityType": "building", "id": g["id"]})
            # the front (-sin a, cos a) points back at the street
            angle = math.degrees(math.atan2(side * nx, -side * nz)) % 360
            r = call("/commands/place-building", {"dryRun": False, "buildingPrefab": prefab, "position": {"x": round(px, 1), "z": round(pz, 1)}, "angleDegrees": round(angle, 1)})
            if r.get("ok"):
                placed.append((px, pz, x, z))
                print(f"  placed {prefab} for {name or kind} at {px:.0f},{pz:.0f} on {s['name']}")
                done = True
                break
        if not done:
            print(f"  no room beside a street for {name or kind}")
    print("placed:", len(placed))


if __name__ == "__main__":
    main()
