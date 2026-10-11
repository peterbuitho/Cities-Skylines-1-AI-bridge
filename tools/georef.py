"""Fit where the game map sits on the globe by matching the OSM coastline to the game's shoreline.

Usage: py tools/georef.py terrain.json data/<city>.osm.json
Prints center_lat, center_lon, scale and rotation_deg for cities/<city>.toml.

terrain.json is {"step": 40, "minX": -8640, "minZ": -8640, "rows": [...]}: the rows of the
bridge's /state/terrain, fetched in 1920 m tiles (it allows 120 samples per axis) and
joined so that row 0 is the southern edge. '~' marks water.
Change LAT0/LON0 below to a rough guess of the map centre for another city.
"""
import json, math, sys
from collections import deque

terrain_path, osm_path = sys.argv[1], sys.argv[2]
t = json.load(open(terrain_path, encoding="utf-8-sig"))
rows, step, min_x, min_z = t["rows"], t["step"], t["minX"], t["minZ"]
H, W = len(rows), len(rows[0])
water = [[c == "~" for c in r] for r in rows]

# distance (in cells) from every cell to the nearest shore cell
INF = 10**9
dist = [[INF] * W for _ in range(H)]
q = deque()
for z in range(H):
    for x in range(W):
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            zz, xx = z + dz, x + dx
            if 0 <= zz < H and 0 <= xx < W and water[zz][xx] != water[z][x]:
                dist[z][x] = 0
                q.append((z, x))
                break
while q:
    z, x = q.popleft()
    for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        zz, xx = z + dz, x + dx
        if 0 <= zz < H and 0 <= xx < W and dist[zz][xx] > dist[z][x] + 1:
            dist[zz][xx] = dist[z][x] + 1
            q.append((zz, xx))

osm = json.load(open(osm_path, encoding="utf-8"))
nodes = {e["id"]: (e["lat"], e["lon"]) for e in osm["elements"] if e["type"] == "node"}
ways = [e for e in osm["elements"] if e["type"] == "way"]
coast = [w for w in ways if w.get("tags", {}).get("natural") == "coastline"]
print(f"nodes={len(nodes)} ways={len(ways)} coastline ways={len(coast)}")

LAT0, LON0 = 56.153, 10.21
A, E2 = 6378137.0, 0.00669437999014
def enu(lat, lon):
    p0, p = math.radians(LAT0), math.radians(lat)
    w = lambda a: 1 - E2 * math.sin(a) ** 2
    m = A * (1 - E2) / w(p0) ** 1.5
    n = A / math.sqrt(w(p))
    e = n * math.cos(p) * math.radians(lon - LON0)
    return e, m * (p - p0) + e * e * math.tan(p0) / (2 * n)

# coastline sampled every ~40 m
pts = []
for w in coast:
    ll = [enu(*nodes[i]) for i in w["nodes"] if i in nodes]
    for a, b in zip(ll, ll[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        k = max(1, int(d / 40))
        for j in range(k):
            pts.append((a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k))
print("coast sample points", len(pts))

def score(dx, dz, s, rot, sample):
    c, sn = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    total, n = 0.0, 0
    for e, nn in sample:
        x = s * (e * c - nn * sn) + dx
        z = s * (e * sn + nn * c) + dz
        ix, iz = int((x - min_x) / step + 0.5), int((z - min_z) / step + 0.5)
        if 2 <= ix < W - 2 and 2 <= iz < H - 2:
            total += min(dist[iz][ix], 8)
            n += 1
    if n < len(sample) * 0.25:
        return 99.0, n
    return total / n, n

coarse = pts[::8]
best = (99.0, 0, 0, 1.0, 0.0)
for s in (0.90, 0.95, 1.0, 1.05):
    for dx in range(-5000, 5001, 200):
        for dz in range(-5000, 5001, 200):
            sc, n = score(dx, dz, s, 0.0, coarse)
            if sc < best[0]:
                best = (sc, dx, dz, s, 0.0)
    print("coarse scale", s, "best so far", best)

sc, dx, dz, s, rot = best
for stepm, steps, stepr in ((80, 0.02, 1.0), (40, 0.01, 0.5), (20, 0.005, 0.25), (10, 0.002, 0.1), (5, 0.001, 0.05)):
    improved = True
    while improved:
        improved = False
        for ddx, ddz, ds, dr in ((stepm,0,0,0),(-stepm,0,0,0),(0,stepm,0,0),(0,-stepm,0,0),(0,0,steps,0),(0,0,-steps,0),(0,0,0,stepr),(0,0,0,-stepr)):
            c2, n = score(dx + ddx, dz + ddz, s + ds, rot + dr, pts)
            if c2 < sc - 1e-6:
                sc, dx, dz, s, rot = c2, dx + ddx, dz + ddz, s + ds, rot + dr
                improved = True
    print(f"refine step {stepm} m: score={sc:.4f} cells dx={dx} dz={dz} scale={s:.4f} rot={rot:.3f}")

final, n = score(dx, dz, s, rot, pts)
print(f"FINAL mean distance to shore = {final * step:.1f} m over {n} points")
# the real-world point that lands on game (0,0): invert x = s*R*(e,n) + d
c, sn = math.cos(math.radians(rot)), math.sin(math.radians(rot))
e0 = (-dx * c - dz * sn) / s
n0 = (dx * sn - dz * c) / s
p0 = math.radians(LAT0)
m = A * (1 - E2) / (1 - E2 * math.sin(p0) ** 2) ** 1.5
nn = A / math.sqrt(1 - E2 * math.sin(p0) ** 2)
lat = LAT0 + math.degrees((n0 - e0 * e0 * math.tan(p0) / (2 * nn)) / m)
lon = LON0 + math.degrees(e0 / (nn * math.cos(math.radians(lat))))
print(f"center_lat = {lat:.6f}\ncenter_lon = {lon:.6f}\nscale = {s:.4f}\nrotation_deg = {rot:.3f}")

# picture: game water (~/.) with projected coastline (#)
grid = [["~" if water[z][x] else "." for x in range(0, W, 4)] for z in range(0, H, 8)]
for e, nn2 in pts:
    x = s * (e * c - nn2 * sn) + dx
    z = s * (e * sn + nn2 * c) + dz
    ix, iz = int((x - min_x) / step) // 4, int((z - min_z) / step) // 8
    if 0 <= iz < len(grid) and 0 <= ix < len(grid[0]):
        grid[iz][ix] = "#"
print("\n".join("".join(r) for r in reversed(grid)))
