"""Zone and name a city the way it is used in reality.

Reads either Danish municipal plan frames (kommuneplanrammer from plandata.dk, GeoJSON) or
OpenStreetMap land use areas and place names (see cities/*.landuse.overpassql). Inside the given
bounds every piece of land gets the zone of the area it lies in, and is unzoned where the source
has no built-up use (parks, woods, fields, water, public purposes). From OpenStreetMap, suburbs,
quarters and neighbourhoods become named districts. Occupied cells are left alone. Needs the mod
build in mod/.

Use: zones.py <plandata.json | landuse.osm.json> <city.toml> <minX,minZ,maxX,maxZ> <centreX,centreZ> [--live] [--no-districts]

Density: plan frames carry it (floor area ratio of 70 % or more is high density); for
OpenStreetMap, housing and shops within 1500 m of the centre are high density.
"""
import collections, json, math, sys, tomllib, urllib.error, urllib.request

B = "http://127.0.0.1:32123"
STEP, RADIUS, DENSE = 48.0, 36.0, 1500.0
A, E2 = 6378137.0, 0.00669437999014
# most specific first: a shop street inside a housing area is a shop street
ORDER = ["retail", "commercial", "industrial", "residential"]
PLACE_RADIUS = {"suburb": 520.0, "quarter": 360.0, "neighbourhood": 240.0}


def call(path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(B + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))


def projector(city):
    """Same projection as src/geo.rs."""
    lat0 = math.radians(city["center_lat"])
    rot = math.radians(city.get("rotation_deg", 0.0))
    scale = city.get("scale", 1.0)
    w = lambda p: 1 - E2 * math.sin(p) ** 2

    def project(lat, lon):
        phi = math.radians(lat)
        normal = A / math.sqrt(w(phi))
        east = normal * math.cos(phi) * math.radians(lon - city["center_lon"])
        north = A * (1 - E2) / w(lat0) ** 1.5 * (phi - lat0) + east * east * math.tan(lat0) / (2 * normal)
        return scale * (east * math.cos(rot) - north * math.sin(rot)), scale * (east * math.sin(rot) + north * math.cos(rot))
    return project


def inside(point, ring):
    x, z = point
    hit = False
    for (x1, z1), (x2, z2) in zip(ring, ring[1:] + ring[:1]):
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            hit = not hit
    return hit


def osm_areas(osm, project, centre):
    """[(ring, rule)] from OpenStreetMap land use ways and relations; rule(x, z) gives the zone."""
    areas = []
    for kind in ORDER:  # most specific first
        for e in osm:
            if e.get("tags", {}).get("landuse") != kind or e["type"] == "node":
                continue
            parts = [e["geometry"]] if e["type"] == "way" else [m["geometry"] for m in e.get("members", []) if m.get("role") == "outer" and "geometry" in m]

            def rule(x, z, kind=kind):
                dense = math.hypot(x - centre[0], z - centre[1]) < DENSE
                return {"retail": "CommercialHigh" if dense else "CommercialLow", "commercial": "Office", "industrial": "Industrial",
                        "residential": "ResidentialHigh" if dense else "ResidentialLow"}[kind]
            areas += [([project(q["lat"], q["lon"]) for q in part], rule) for part in parts]
    return areas


def plandata_areas(features, project):
    """[(ring, rule)] from Danish municipal plan frames (kommuneplanrammer, plandata.dk).

    anvgen is the general use; bebygpct is the allowed floor area as a percentage of the plot,
    which decides low or high density. Mixed areas are split cell by cell.
    """
    areas = []
    for f in features:
        p = f["properties"]
        use, ratio, special = p.get("anvgen"), p.get("bebygpct") or 0, p.get("anvspec1") or 0
        high = ratio >= 70
        home = "ResidentialHigh" if high else "ResidentialLow"
        shop = "CommercialHigh" if high else "CommercialLow"
        if use == 11:                       # housing
            mix = [home]
        elif use == 21:                     # mixed housing and business
            mix = [home, shop, home, "Office"]
        elif use == 31:                     # business: 3110 is offices and services, the rest industry
            mix = ["Office"] if special == 3110 else ["Industrial"]
        elif use == 41:                     # town or district centre
            mix = [shop, "Office", shop, home]
        else:                               # recreation, public purposes, technical plant, countryside
            continue

        def rule(x, z, mix=mix):
            return mix[(int(x // STEP) + 2 * int(z // STEP)) % len(mix)]
        g = f["geometry"]
        polygons = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        areas += [([project(lat, lon) for lon, lat in polygon[0]], rule) for polygon in polygons]
    return areas


def plan(data, project, bounds, centre):
    """Returns ({(x, z): zone}, [(place kind, name, x, z)])."""
    min_x, min_z, max_x, max_z = bounds
    places = []
    if "features" in data:
        areas = plandata_areas(data["features"], project)
    else:
        areas = osm_areas(data["elements"], project, centre)
        for e in data["elements"]:
            tags = e.get("tags", {})
            if e["type"] == "node" and tags.get("place") in PLACE_RADIUS and tags.get("name"):
                x, z = project(e["lat"], e["lon"])
                if min_x <= x <= max_x and min_z <= z <= max_z:
                    places.append((tags["place"], tags["name"], x, z))

    boxed = []
    for ring, rule in areas:
        xs, zs = [q[0] for q in ring], [q[1] for q in ring]
        if len(ring) >= 3 and max(xs) >= min_x and min(xs) <= max_x and max(zs) >= min_z and min(zs) <= max_z:
            boxed.append((min(xs), min(zs), max(xs), max(zs), ring, rule))

    cells = {}
    z = min_z + STEP / 2
    while z < max_z:
        x = min_x + STEP / 2
        while x < max_x:
            cells[(x, z)] = next((rule(x, z) for a, b, c, d, ring, rule in boxed if a <= x <= c and b <= z <= d and inside((x, z), ring)), "Unzoned")
            x += STEP
        z += STEP
    return cells, places


def main():
    live = "--live" in sys.argv
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    project = projector(tomllib.load(open(sys.argv[2], "rb")))
    bounds = [float(v) for v in sys.argv[3].split(",")]
    centre = [float(v) for v in sys.argv[4].split(",")]
    cells, places = plan(data, project, bounds, centre)
    print("land:", dict(collections.Counter(cells.values()).most_common()))
    print("named places:", dict(collections.Counter(p[0] for p in places)))
    if not live:
        print("DRY RUN: nothing was changed")
        return

    # unzone first, so a zoned circle that overlaps open land wins at the edge
    ordered = sorted(cells.items(), key=lambda kv: kv[1] != "Unzoned")
    changed = failed = 0
    for i in range(0, len(ordered), 32):
        commands = [{"type": "set-zone", "zone": zone, "center": {"x": round(x, 1), "z": round(z, 1)}, "radius": RADIUS}
                    for (x, z), zone in ordered[i:i + 32]]
        r = call("/commands/batch", {"dryRun": False, "stopOnError": False, "commands": commands})
        results = [c.get("result", {}) for c in r.get("results", [])]
        failed += len(commands) - sum(1 for c in results if c.get("ok"))
        changed += sum(int(c.get("changedCells", 0)) for c in results)
        if (i // 32) % 60 == 59:
            print(f"  {i + 32} of {len(ordered)} circles, {changed} cells changed", flush=True)
    print(f"zone cells changed: {changed}, circles failed: {failed}")

    if "--no-districts" in sys.argv:
        return
    made = 0
    for kind in PLACE_RADIUS:  # large first, so a neighbourhood shows inside its suburb
        for place, name, x, z in places:
            if place == kind:
                r = call("/commands/create-district", {"name": name.replace('"', "").replace("\\", ""), "x": round(x, 1), "z": round(z, 1), "radius": PLACE_RADIUS[kind]})
                made += bool(r.get("ok"))
                if not r.get("ok"):
                    print("  district failed:", name, r.get("error"))
    print("districts named:", made)


if __name__ == "__main__":
    main()
