"""Build a metro line along a real light-rail route (a stand-in where the game has no trams).

Places a metro station at each named stop, lays ground metro track between them along the
OpenStreetMap track, and creates the line. Needs the mod build in mod/.

Use: metro.py <light_rail.osm.json> <city.toml> "Stop A;Stop B;Stop C" [--live]
"""
import collections, heapq, json, math, sys, tomllib, urllib.error, urllib.request

B = "http://127.0.0.1:32123"
STATION, STATION_TRACK, TRACK = "Overground Metro Station 01", "Metro Station Track Ground 01", "Metro Track Ground 01"
A, E2 = 6378137.0, 0.00669437999014


def call(path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(B + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
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


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def simplify(points, tolerance):
    """Douglas-Peucker."""
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    length = dist(a, b) or 1e-9
    far, index = 0.0, 0
    for i in range(1, len(points) - 1):
        p = points[i]
        d = abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / length
        if d > far:
            far, index = d, i
    if far <= tolerance:
        return [a, b]
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def pieces(points, longest=90.0):
    """Straight pieces no longer than `longest`."""
    out = [points[0]]
    for p in points[1:]:
        n = max(1, math.ceil(dist(out[-1], p) / longest))
        start = out[-1]
        out += [(start[0] + (p[0] - start[0]) * i / n, start[1] + (p[1] - start[1]) * i / n) for i in range(1, n + 1)]
    return out


def main():
    live = "--live" in sys.argv
    osm = json.load(open(sys.argv[1], encoding="utf-8"))["elements"]
    project = projector(tomllib.load(open(sys.argv[2], "rb")))
    wanted = [s.strip() for s in sys.argv[3].split(";") if s.strip()]

    pos = {e["id"]: project(e["lat"], e["lon"]) for e in osm if e["type"] == "node"}
    graph = collections.defaultdict(list)
    for e in osm:
        if e["type"] == "way" and e["tags"].get("service") not in ("yard", "siding"):
            for a, b in zip(e["nodes"], e["nodes"][1:]):
                graph[a].append(b)
                graph[b].append(a)
    named = collections.defaultdict(list)
    for e in osm:
        if e["type"] == "node" and e.get("tags", {}).get("railway") in ("tram_stop", "halt", "station"):
            named[e["tags"].get("name", "")].append(pos[e["id"]])

    def track_node(point):
        return min(graph, key=lambda n: dist(pos[n], point))

    def route(a, b):
        """Shortest way along the track between two track nodes."""
        best, prev, heap = {a: 0.0}, {}, [(0.0, a)]
        while heap:
            d, n = heapq.heappop(heap)
            if n == b:
                break
            if d > best[n]:
                continue
            for m in graph[n]:
                nd = d + dist(pos[n], pos[m])
                if nd < best.get(m, 1e18):
                    best[m], prev[m] = nd, n
                    heapq.heappush(heap, (nd, m))
        if b not in best:
            sys.exit(f"no track between two stops")
        path = [b]
        while path[-1] != a:
            path.append(prev[path[-1]])
        return [pos[n] for n in reversed(path)]

    stops = []
    for name in wanted:
        if name not in named:
            sys.exit(f"stop not found in the data: {name}")
        pts = named[name]
        centre = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        stops.append((name, track_node(centre)))
    legs = [route(a[1], b[1]) for a, b in zip(stops, stops[1:])]

    def rail_segments():
        return {s["id"]: s for s in call("/state/networks?service=PublicTransport&limit=65536")["segments"]}

    growables = call("/state/growables?limit=65536")["growables"] if live else []
    station_tracks = []
    for i, (name, node) in enumerate(stops):
        here = pos[node]
        ahead = legs[i][min(3, len(legs[i]) - 1)] if i < len(legs) else legs[i - 1][-min(4, len(legs[i - 1]))]
        along = (ahead[0] - here[0], ahead[1] - here[1]) if i < len(legs) else (here[0] - ahead[0], here[1] - ahead[1])
        angle = round(math.degrees(math.atan2(along[1], along[0])) % 360, 1)
        print(f"station {name}: {here[0]:.0f},{here[1]:.0f} angle {angle}")
        if not live:
            continue
        for g in growables:
            if dist((g["position"]["x"], g["position"]["z"]), here) < 70:
                call("/commands/bulldoze", {"entityType": "building", "id": g["id"]})
        before = rail_segments()
        r = call("/commands/place-building", {"dryRun": False, "buildingPrefab": STATION, "position": {"x": round(here[0], 1), "z": round(here[1], 1)}, "angleDegrees": angle})
        if not r.get("ok"):
            sys.exit(f"could not place {name}: {r}")
        new = [s for k, s in rail_segments().items() if k not in before and s["prefab"] == STATION_TRACK]
        if len(new) != 1:
            sys.exit(f"{name}: expected one station track, got {[s['prefab'] for s in new]}")
        station_tracks.append(new[0])

    if not live:
        for (a, _), (b, _), leg in zip(stops, stops[1:], legs):
            print(f"track {a} -> {b}: {sum(dist(p, q) for p, q in zip(leg, leg[1:])):.0f} m")
        print("DRY RUN: nothing was built")
        return

    built = failed = 0
    for i, leg in enumerate(legs):
        a, b = station_tracks[i], station_tracks[i + 1]
        ends = lambda s: [(s["start"]["x"], s["start"]["z"]), (s["end"]["x"], s["end"]["z"])]
        mid_b = (b["middle"]["x"], b["middle"]["z"])
        mid_a = (a["middle"]["x"], a["middle"]["z"])
        start = min(ends(a), key=lambda p: dist(p, mid_b))
        end = min(ends(b), key=lambda p: dist(p, mid_a))
        # keep the real alignment only where it is clear of both stations
        between = [p for p in leg if dist(p, mid_a) > 110 and dist(p, mid_b) > 110]
        line = pieces([start] + simplify(between, 1.5) + [end], 60.0)
        line = [line[0]] + [p for p, q in zip(line[1:-1], line[2:]) if dist(p, q) >= 10] + [line[-1]]
        # Trains refuse a kink, so every piece is a curve whose ends follow the line's tangent;
        # at the stations the tangent is the station track itself.
        unit = lambda p, q: ((q[0] - p[0]) / (dist(p, q) or 1), (q[1] - p[1]) / (dist(p, q) or 1))
        far_a = max(ends(a), key=lambda p: dist(p, mid_b))
        far_b = max(ends(b), key=lambda p: dist(p, mid_a))
        tangent = [unit(far_a, start)] + [unit(line[k - 1], line[k + 1]) for k in range(1, len(line) - 1)] + [unit(end, far_b)]
        for k, (p, q) in enumerate(zip(line, line[1:])):
            r = call("/commands/build-network", {"dryRun": False, "roadPrefab": TRACK, "name": "Letbanen",
                     "start": {"x": round(p[0], 2), "z": round(p[1], 2)}, "end": {"x": round(q[0], 2), "z": round(q[1], 2)},
                     "startDirection": {"x": round(tangent[k][0], 4), "z": round(tangent[k][1], 4)},
                     "endDirection": {"x": round(tangent[k + 1][0], 4), "z": round(tangent[k + 1][1], 4)}})
            if r.get("ok"):
                built += 1
            else:
                failed += 1
                print("  track piece failed:", r.get("error"))
    print(f"track pieces built: {built}, failed: {failed}")

    r = call("/commands/create-line", {"transport": "Metro", "segments": ",".join(str(s["id"]) for s in station_tracks)})
    print("line:", r)


if __name__ == "__main__":
    main()
