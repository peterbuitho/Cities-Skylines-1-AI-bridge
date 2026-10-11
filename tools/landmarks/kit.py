"""Building blocks for generated landmark models: a mesh of flat faces and a facade texture.

Model space is the game's: x along the lot, y up, z towards the street. Metres.
The texture is cut into bands that each run the full width, so a band can repeat along a wall.
"""
import json, math, os, sys, urllib.error, urllib.request

import numpy as np
from PIL import Image, ImageDraw

SIZE = 1024
# (v low, v high) of each band in UV space
WALL, TOWER, ROOF, SPIRE, PLAIN = (0.55, 1.0), (0.22, 0.55), (0.12, 0.22), (0.06, 0.12), (0.0, 0.06)
BAY = 6.0            # metres per window bay; the wall band holds four bays across
TOWER_FACE = 14.0    # metres per tower face; the tower band holds two faces across

COPPER, TILE, SLATE = (104, 160, 142), (158, 72, 52), (74, 78, 88)


class Mesh:
    def __init__(self):
        self.faces = []  # (points, uvs)

    def poly(self, points, uvs, inside):
        """A flat polygon facing away from the point `inside`, wound clockwise seen from outside."""
        p = [np.array(q, dtype=float) for q in points]
        normal = np.cross(p[1] - p[0], p[2] - p[0])
        if np.dot(normal, sum(p) / len(p) - np.array(inside, dtype=float)) < 0:
            p.reverse()
            uvs = list(reversed(uvs))
        self.faces.append((p, list(uvs)))

    def wall(self, a, b, y0, y1, band, metres_per_u, inside):
        """A vertical wall from (x, z) a to b; the band's height is stretched over the wall."""
        u = math.dist(a, b) / metres_per_u
        self.poly([(a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1])],
                  [(0, band[0]), (u, band[0]), (u, band[1]), (0, band[1])], inside)

    def hall(self, x0, x1, z0, z1, wall_h, ridge_h, along_x=True):
        """A hall with a pitched roof; the ridge runs along x or along z, with a gable at each end."""
        inside = ((x0 + x1) / 2, wall_h / 2, (z0 + z1) / 2)
        corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            self.wall(a, b, 0, wall_h, WALL, BAY * 4, inside)
        mid_z, mid_x = (z0 + z1) / 2, (x0 + x1) / 2
        if along_x:
            ridge = [(x0, ridge_h, mid_z), (x1, ridge_h, mid_z)]
            u = (x1 - x0) / 8.0
            for z in (z0, z1):
                self.poly([(x0, wall_h, z), (x1, wall_h, z), ridge[1], ridge[0]], [(0, ROOF[0]), (u, ROOF[0]), (u, ROOF[1]), (0, ROOF[1])], inside)
            for x, r in ((x0, ridge[0]), (x1, ridge[1])):
                self.poly([(x, wall_h, z0), (x, wall_h, z1), r], [(0, PLAIN[0]), ((z1 - z0) / 8, PLAIN[0]), ((z1 - z0) / 16, PLAIN[1])], inside)
        else:
            ridge = [(mid_x, ridge_h, z0), (mid_x, ridge_h, z1)]
            u = (z1 - z0) / 8.0
            for x in (x0, x1):
                self.poly([(x, wall_h, z0), (x, wall_h, z1), ridge[1], ridge[0]], [(0, ROOF[0]), (u, ROOF[0]), (u, ROOF[1]), (0, ROOF[1])], inside)
            for z, r in ((z0, ridge[0]), (z1, ridge[1])):
                self.poly([(x0, wall_h, z), (x1, wall_h, z), r], [(0, PLAIN[0]), ((x1 - x0) / 8, PLAIN[0]), ((x1 - x0) / 16, PLAIN[1])], inside)

    def tower(self, x0, x1, z0, z1, top, apex):
        """A square tower to `top` with a pointed roof or spire to `apex`."""
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            self.wall(a, b, 0, top, TOWER, TOWER_FACE * 2, (cx, top / 2, cz))
        for a, b in zip(corners, corners[1:] + corners[:1]):
            self.poly([(a[0], top, a[1]), (b[0], top, b[1]), (cx, apex, cz)], [(0, SPIRE[0]), (1.75, SPIRE[0]), (0.875, SPIRE[1])], (cx, top + 1, cz))

    def block(self, x0, x1, z0, z1, height, bay=BAY, sign_every=None, base=0.0, band=WALL):
        """A flat-roofed block: four walls in the wall band and a roof in the plain band.

        base lifts it off the ground (an upper part that hangs over); band picks another wall look.

        With sign_every, each wall shows the wall band a whole number of times, about once every
        that many metres, so a shop sign is never cut off at a corner.
        """
        inside = ((x0 + x1) / 2, height / 2, (z0 + z1) / 2)
        corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            per_u = math.dist(a, b) / max(1, round(math.dist(a, b) / sign_every)) if sign_every else bay * 4
            self.wall(a, b, base, height, band, per_u, inside)
        if base > 0:    # the underside of a part that hangs over
            self.poly([(x0, base, z0), (x1, base, z0), (x1, base, z1), (x0, base, z1)],
                      [(0, PLAIN[0]), (1, PLAIN[0]), (1, PLAIN[1]), (0, PLAIN[1])], ((x0 + x1) / 2, (base + height) / 2, (z0 + z1) / 2))
        self.poly([(x0, height, z0), (x1, height, z0), (x1, height, z1), (x0, height, z1)],
                  [(0, ROOF[0]), ((x1 - x0) / 16, ROOF[0]), ((x1 - x0) / 16, ROOF[1]), (0, ROOF[1])], inside)

    def frustum(self, cx, cz, half_base, half_top, y0, y1, band=TOWER, sides=8):
        """A tapering round tower, as a many-sided body: a mill, a chimney."""
        ring = lambda r, y: [(cx + r * math.cos(2 * math.pi * k / sides), y, cz + r * math.sin(2 * math.pi * k / sides)) for k in range(sides)]
        low, high = ring(half_base, y0), ring(half_top, y1)
        for k in range(sides):
            j = (k + 1) % sides
            self.poly([low[k], low[j], high[j], high[k]], [(k / sides, band[0]), ((k + 1) / sides, band[0]), ((k + 1) / sides, band[1]), (k / sides, band[1])],
                      (cx, (y0 + y1) / 2, cz))
        self.poly(high, [(0.5 + 0.4 * math.cos(2 * math.pi * k / sides), ROOF[0] + (ROOF[1] - ROOF[0]) * (0.5 + 0.4 * math.sin(2 * math.pi * k / sides))) for k in range(sides)],
                  (cx, y0, cz))

    def dome(self, cx, cz, rx, rz, height, band=WALL, rings=5, sides=16):
        """Half an egg standing on the ground: a glasshouse dome."""
        point = lambda i, k: (cx + rx * math.cos(math.pi / 2 * i / rings) * math.cos(2 * math.pi * k / sides),
                              height * math.sin(math.pi / 2 * i / rings),
                              cz + rz * math.cos(math.pi / 2 * i / rings) * math.sin(2 * math.pi * k / sides))
        v = lambda i: band[0] + (band[1] - band[0]) * i / rings
        for i in range(rings):
            for k in range(sides):
                corners = [point(i, k), point(i, k + 1), point(i + 1, k + 1), point(i + 1, k)]
                uvs = [(k * 4 / sides, v(i)), ((k + 1) * 4 / sides, v(i)), ((k + 1) * 4 / sides, v(i + 1)), (k * 4 / sides, v(i + 1))]
                if i == rings - 1:   # the top ring closes to a point
                    corners, uvs = corners[:3], uvs[:3]
                self.poly(corners, uvs, (cx, 0, cz))

    def sheet(self, points, uvs):
        """A thin flat part seen from both sides: a mill sail, a sign."""
        centre = sum(np.array(p, dtype=float) for p in points) / len(points)
        normal = np.cross(np.array(points[1], dtype=float) - points[0], np.array(points[2], dtype=float) - points[0])
        normal = normal / (np.linalg.norm(normal) or 1.0)
        self.poly(points, uvs, centre - normal)
        self.poly(points, uvs, centre + normal)

    def write(self, path, source):
        with open(path, "w", encoding="ascii") as f:
            f.write(f"# generated by {source}\n")
            n = 1
            for points, uvs in self.faces:
                normal = np.cross(points[1] - points[0], points[2] - points[0])
                normal = normal / (np.linalg.norm(normal) or 1.0)
                for p, uv in zip(points, uvs):
                    f.write(f"v {p[0]:.3f} {p[1]:.3f} {p[2]:.3f}\nvt {uv[0]:.4f} {uv[1]:.4f}\nvn {normal[0]:.4f} {normal[1]:.4f} {normal[2]:.4f}\n")
                for k in range(1, len(points) - 1):  # fan
                    f.write("f " + " ".join(f"{i}/{i}/{i}" for i in (n, n + k, n + k + 1)) + "\n")
                n += len(points)

    def extent(self):
        points = np.array([p for face in self.faces for p in face[0]])
        return points.min(axis=0), points.max(axis=0)


def rows(band):
    """Pixel rows of a band; row 0 is the top of the image, v = 1."""
    return int(round((1 - band[1]) * SIZE)), int(round((1 - band[0]) * SIZE))


def brick(draw, box, rng, base):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=base)
    for row, y in enumerate(range(y0, y1, 5)):
        for x in range(x0 - (row % 2) * 8, x1, 16):
            shade = int(rng.integers(-14, 15))
            draw.rectangle([max(x, x0), y, min(x + 14, x1 - 1), min(y + 3, y1 - 1)], fill=tuple(int(np.clip(c + shade, 0, 255)) for c in base))


def window(draw, cx, bottom, top, half, pointed, glass=(38, 44, 60), stone=(196, 186, 168)):
    """An arched window with a stone surround: pointed (Gothic) or round (Romanesque)."""
    rise = half * 1.5 if pointed else half
    spring = top + int(rise)
    arch = [(cx - half, spring)] + [(cx - half + int(half * (1 - math.cos(t))), spring - int(rise * math.sin(t))) for t in np.linspace(0, math.pi / 2, 9)]
    arch += [(cx + half - int(half * (1 - math.cos(t))), spring - int(rise * math.sin(t))) for t in np.linspace(math.pi / 2, 0, 9)] + [(cx + half, spring)]
    outline = [(cx - half, bottom)] + arch + [(cx + half, bottom)]
    draw.polygon(outline, fill=glass)
    draw.line(outline + [outline[0]], fill=stone, width=3)
    draw.line([(cx, bottom), (cx, spring - half // 2)], fill=stone, width=2)
    for y in range(bottom - 24, spring, -28):
        draw.line([(cx - half, y), (cx + half, y)], fill=(70, 76, 92), width=1)


def roofing(draw, band, colour):
    top, bottom = rows(band)
    draw.rectangle([0, top, SIZE, bottom], fill=colour)
    dark = tuple(int(c * 0.8) for c in colour)
    light = tuple(min(255, int(c * 1.12)) for c in colour)
    if colour == TILE:                       # rows of pantiles
        for y in range(top, bottom, 10):
            draw.line([(0, y), (SIZE, y)], fill=dark, width=2)
        for x in range(0, SIZE, 12):
            draw.line([(x, top), (x, bottom)], fill=light, width=1)
    else:                                    # sheet metal or slate: standing seams
        for x in range(0, SIZE, 32):
            draw.line([(x, top), (x, bottom)], fill=dark, width=2)
        for y in range(top, bottom, 40):
            draw.line([(0, y), (SIZE, y)], fill=light, width=1)


def texture(seed, brick_colour=(152, 78, 58), roof=COPPER, spire=COPPER, pointed=True, clock=True, tall_windows=True):
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(img)
    dark = tuple(int(c * 0.78) for c in brick_colour)
    light = tuple(min(255, int(c * 1.16)) for c in brick_colour)

    top, bottom = rows(WALL)
    brick(d, (0, top, SIZE, bottom), rng, brick_colour)
    bay = SIZE // 4
    for i in range(4):
        x = i * bay
        d.rectangle([x, top + 14, x + 12, bottom], fill=dark)                                   # buttress or pilaster
        d.rectangle([x + 12, top + 14, x + 15, bottom], fill=tuple(int(c * 0.62) for c in brick_colour))
        if tall_windows:
            window(d, x + bay // 2 + 6, bottom - 70, top + 60, 34, pointed)
        else:
            window(d, x + bay // 2 + 6, bottom - 150, top + 110, 30, pointed)
    d.rectangle([0, bottom - 22, SIZE, bottom], fill=(128, 124, 118))                           # granite plinth
    d.rectangle([0, top, SIZE, top + 14], fill=light)                                           # cornice

    top, bottom = rows(TOWER)
    brick(d, (0, top, SIZE, bottom), rng, tuple(int(c * 0.96) for c in brick_colour))
    face = SIZE // 2
    for i in range(2):
        cx = i * face + face // 2
        for dx in (-70, 70):                                                                    # belfry louvres
            window(d, cx + dx, top + 120, top + 24, 26, pointed, glass=(52, 44, 40))
        if clock:
            d.ellipse([cx - 34, top + 140, cx + 34, top + 208], fill=(232, 224, 196), outline=(60, 50, 40), width=4)
            d.line([(cx, top + 174), (cx, top + 150)], fill=(40, 34, 30), width=3)
            d.line([(cx, top + 174), (cx + 16, top + 180)], fill=(40, 34, 30), width=3)
        for y in (top + 232, top + 272):                                                        # stair slits
            d.rectangle([cx - 5, y, cx + 5, y + 26], fill=(40, 38, 44))
        window(d, cx, bottom - 6, bottom - 58, 26, pointed, glass=(64, 46, 34))                 # portal
        d.rectangle([i * face, top, i * face + 10, bottom], fill=dark)                          # corner pier
    d.rectangle([0, top, SIZE, top + 8], fill=light)

    roofing(d, ROOF, roof)
    roofing(d, SPIRE, spire)
    top, bottom = rows(PLAIN)
    brick(d, (0, top, SIZE, bottom), rng, brick_colour)
    return img


def block_texture(seed, wall=(196, 190, 178), glass=(52, 66, 84), floors=5, roof=(92, 94, 98), shopfront=True, columns=False):
    """The facade of a flat-roofed block: rows of windows, optionally a glazed ground floor or a colonnade."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(img)
    top, bottom = rows(WALL)
    d.rectangle([0, top, SIZE, bottom], fill=wall)
    for _ in range(1400):                                   # a little grain, so walls are not flat colour
        x, y = int(rng.integers(0, SIZE)), int(rng.integers(top, bottom))
        shade = int(rng.integers(-8, 9))
        d.point((x, y), fill=tuple(int(np.clip(c + shade, 0, 255)) for c in wall))
    floor_h = (bottom - top) / floors
    bay = SIZE // 4
    for f in range(floors):
        y0 = top + int(f * floor_h)
        ground = f == floors - 1
        for i in range(4):
            for k in range(3):                              # three windows a bay
                x0 = i * bay + 14 + k * (bay - 20) // 3
                x1 = x0 + (bay - 20) // 3 - 10
                if columns:
                    d.rectangle([x0, y0 + 4, x1, y0 + int(floor_h) - 2], fill=glass)
                elif ground and shopfront:
                    d.rectangle([x0 - 4, y0 + 6, x1 + 4, bottom - 6], fill=tuple(int(c * 0.8) for c in glass), outline=(40, 40, 44))
                else:
                    d.rectangle([x0, y0 + int(floor_h * 0.22), x1, y0 + int(floor_h * 0.78)], fill=glass, outline=tuple(int(c * 0.82) for c in wall))
        d.line([(0, y0), (SIZE, y0)], fill=tuple(int(c * 0.86) for c in wall), width=2)   # floor line
    if columns:
        for x in range(0, SIZE, bay // 3):
            d.rectangle([x, top, x + 12, bottom], fill=(238, 236, 230))                    # white columns in front of the glass
    d.rectangle([0, top, SIZE, top + 10], fill=tuple(min(255, int(c * 1.08)) for c in wall))  # parapet
    for band in (TOWER, ROOF, SPIRE, PLAIN):
        t, b = rows(band)
        d.rectangle([0, t, SIZE, b], fill=roof if band in (ROOF, PLAIN) else wall)
    return img


def shop_texture(name, wall, sign, text, glass=(60, 76, 92), roof=(96, 98, 102)):
    """A shop front: the chain's name in its colours on a band over glazing and a door."""
    from PIL import ImageFont
    img = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(img)
    top, bottom = rows(WALL)
    height = bottom - top
    d.rectangle([0, top, SIZE, bottom], fill=wall)
    band = int(height * 0.42)
    d.rectangle([0, top, SIZE, top + band], fill=sign)
    size = int(band * 0.72)
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
    while d.textlength(name, font=font) > SIZE * 0.86 and size > 20:      # long names shrink to fit
        size -= 6
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
    d.text((SIZE / 2, top + band / 2), name, font=font, fill=text, anchor="mm")
    for x in range(40, SIZE - 40, 164):                                     # shop windows
        d.rectangle([x, top + band + 26, x + 132, bottom - 30], fill=glass, outline=(40, 44, 50), width=3)
    d.rectangle([SIZE // 2 - 70, top + band + 14, SIZE // 2 + 70, bottom - 8], fill=(34, 40, 48), outline=(210, 210, 210), width=4)   # doors
    d.line([(SIZE // 2, top + band + 14), (SIZE // 2, bottom - 8)], fill=(210, 210, 210), width=3)
    d.rectangle([0, bottom - 8, SIZE, bottom], fill=(110, 110, 112))
    for b in (TOWER, ROOF, SPIRE, PLAIN):
        t, bb = rows(b)
        d.rectangle([0, t, SIZE, bb], fill=roof)
    return img


def timber_texture(seed, roof=TILE):
    """Half-timbered walls: plastered panels in white, ochre and red between dark posts and rails."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(img)
    plaster = [(238, 232, 214), (214, 170, 96), (172, 78, 60), (232, 214, 170)]
    timber = (58, 44, 34)
    for band in (WALL, TOWER, PLAIN):
        top, bottom = rows(band)
        for x in range(0, SIZE, 128):                                  # one house front every 128 px
            d.rectangle([x, top, x + 128, bottom], fill=plaster[int(rng.integers(0, len(plaster)))])
        for x in range(0, SIZE, 32):
            d.rectangle([x, top, x + 5, bottom], fill=timber)          # posts
        rails = 4 if band != PLAIN else 1
        for k in range(rails + 1):
            y = top + (bottom - top) * k // rails
            d.rectangle([0, y - 3, SIZE, y + 3], fill=timber)          # rails
        if band != PLAIN:
            step = (bottom - top) // rails
            for x in range(48, SIZE, 64):
                for k in range(rails - 1):
                    y = top + k * step + step // 4
                    d.rectangle([x - 11, y, x + 11, y + step // 2], fill=(44, 52, 62), outline=(240, 236, 226), width=2)   # small windows
            for x in range(16, SIZE, 128):
                d.rectangle([x - 2, bottom - step + 8, x + 18, bottom - 3], fill=(70, 96, 70))                               # doors
    roofing(d, ROOF, roof)
    roofing(d, SPIRE, roof)
    return img


def call(path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:32123" + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))


def beside_road(prefab, x, z, width, depth, roads, growables, taken):
    """Places a building beside the street nearest to x,z, facing it. taken is a list of (x, z, radius)
    already used and gains the new one. Houses in the way are removed. False when there is no room."""
    reach = math.hypot(width, depth) / 2
    for s in sorted(roads, key=lambda s: (s["middle"]["x"] - x) ** 2 + (s["middle"]["z"] - z) ** 2)[:25]:
        dx, dz = s["end"]["x"] - s["start"]["x"], s["end"]["z"] - s["start"]["z"]
        length = math.hypot(dx, dz)
        if length < 12:
            continue
        nx, nz = -dz / length, dx / length
        side = 1 if (x - s["middle"]["x"]) * nx + (z - s["middle"]["z"]) * nz >= 0 else -1
        px, pz = s["middle"]["x"] + side * nx * (9 + depth / 2), s["middle"]["z"] + side * nz * (9 + depth / 2)
        if any(o is not s and math.hypot(o["middle"]["x"] - px, o["middle"]["z"] - pz) < reach * 0.8 for o in roads):
            continue
        if any(math.hypot(tx - px, tz - pz) < reach + r for tx, tz, r in taken):
            continue
        for g in growables:
            if math.hypot(g["position"]["x"] - px, g["position"]["z"] - pz) < reach + 6:
                call("/commands/bulldoze", {"entityType": "building", "id": g["id"]})
        # the front (-sin a, cos a) points back at the street
        angle = math.degrees(math.atan2(side * nx, -side * nz)) % 360
        r = call("/commands/place-building", {"dryRun": False, "buildingPrefab": prefab,
                                              "position": {"x": round(px, 1), "z": round(pz, 1)}, "angleDegrees": round(angle, 1)})
        if r.get("ok"):
            taken.append((px, pz, reach))
            return True
    return False


# what the name sign says, where the asset name had to do without Danish letters
LABELS = {"Aabyhoj Kirke": "Åbyhøj Kirke", "Gammel Vindmolle": "Tuesbøl Mølle", "Vaeksthusene": "Væksthusene",
          "Aarhus Universitet Aulaen": "Aarhus Universitet", "Ceres Park": "Ceres Park Stadion"}


def label(name, x, z, angle, width, depth, replace=False, capitals=True):
    """Shows a landmark's name the way street names are shown, in capitals: a short named footpath along its front.
    Does nothing when a path of that name is there already, unless replace is set (the building moved)."""
    name = LABELS.get(name, name)
    if capitals:                             # capitals set a landmark apart from the street names
        name = name.upper()
    for s in call("/state/networks?service=Beautification&limit=65536")["segments"]:
        if s["name"] == name and not replace:
            return True
        if s["name"].upper() == name.upper():   # an earlier sign: in small letters, or where the building stood
            call("/commands/bulldoze", {"entityType": "netSegment", "id": s["id"]})
    a = math.radians(angle)
    front, along = (-math.sin(a), math.cos(a)), (math.cos(a), math.sin(a))
    cx, cz = x + front[0] * (depth / 2 + 6), z + front[1] * (depth / 2 + 6)
    half = min(max(width / 2, 24), 45)
    r = call("/commands/build-network", {"dryRun": False, "roadPrefab": "Pedestrian Pavement", "name": name,
                                         "start": {"x": round(cx - along[0] * half, 1), "z": round(cz - along[1] * half, 1)},
                                         "end": {"x": round(cx + along[0] * half, 1), "z": round(cz + along[1] * half, 1)}})
    return bool(r.get("ok"))


def run(registry, source):
    """generate | create | place | label, for every key or the keys named on the command line.

    registry: key -> (asset name, builder, description, x, z, angle). The mod turns a building so
    that its front, model +z, faces (-sin angle, cos angle); model +x points along (cos, sin).
    """
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    step = sys.argv[1] if len(sys.argv) > 1 else "generate"
    for key in sys.argv[2:] or list(registry):
        name, build, description, x, z, angle = registry[key]
        folder = os.path.join(root, "out", "assets", key).replace("\\", "/")
        mesh, image = build()
        low, high = mesh.extent()
        width = max(1, math.ceil(max(abs(low[0]), abs(high[0])) * 2 / 8))
        length = max(1, math.ceil(max(abs(low[2]), abs(high[2])) * 2 / 8))
        prefab = f"{name}.{name}_Data"
        if step == "generate":
            save(folder, mesh, image, source)
            print(f"{name}: {len(mesh.faces)} faces, {high[0] - low[0]:.0f} x {high[2] - low[2]:.0f} m, {high[1]:.0f} m high, lot {width} x {length} cells")
        elif step == "create":
            r = call("/commands/create-asset", {"name": name, "folder": folder, "template": "Statue of Shopping",
                                                "cellWidth": width, "cellLength": length, "description": description})
            print(f"{name}:", r.get("file") or r.get("error"))
        elif step == "place":
            for f in call("/state/facilities?limit=65536&service=Monument")["facilities"]:
                if f["prefab"] == prefab:
                    call("/commands/bulldoze", {"entityType": "building", "id": f["id"]})
            for g in call("/state/growables?limit=65536")["growables"]:
                if math.hypot(g["position"]["x"] - x, g["position"]["z"] - z) < max(width, length) * 4 + 6:
                    call("/commands/bulldoze", {"entityType": "building", "id": g["id"]})
            r = call("/commands/place-building", {"dryRun": False, "buildingPrefab": prefab, "position": {"x": x, "z": z}, "angleDegrees": angle % 360})
            print(f"{name} at {x},{z} turned {angle % 360}:", r.get("ok"), r.get("error", ""))
            label(name, x, z, angle, width * 8, length * 8, replace=True)
        elif step == "label":
            print(f"{name}: name sign", "ok" if label(name, x, z, angle, width * 8, length * 8) else "failed")
        else:
            sys.exit("step must be generate, create, place or label")


def save(out, mesh, image, source, texture_size=SIZE):
    """texture_size below 1024 makes a much smaller asset file; fine for plain buildings."""
    os.makedirs(out, exist_ok=True)
    mesh.write(os.path.join(out, "model.obj"), source)
    if texture_size != SIZE:
        image = image.resize((texture_size, texture_size), Image.LANCZOS)
    image.save(os.path.join(out, "diffuse.png"))
    image.resize((128, 128), Image.LANCZOS).save(os.path.join(out, "lod.png"))
