"""Aarhus churches as generated game models.

Each church is described by a few real measures: footprint position and direction from
OpenStreetMap, heights and form from what is known of the building. The models are simple
(flat walls with the windows painted on) and are meant to be recognisable, not exact.

Use (from the repo root, with a city loaded for the last two steps):
  py tools\\landmarks\\churches.py generate   writes out/assets/<key>/model.obj, diffuse.png, lod.png
  py tools\\landmarks\\churches.py create     packs each into a game asset (then restart the game)
  py tools\\landmarks\\churches.py place      puts each at its real position

Placing: the mod turns a building so that its front, model +z, faces (-sin a, cos a); model +x then
points along (cos a, sin a). `tower_towards` is the compass direction the tower end, model -x,
points in, as an angle from east through north.
"""
import json, math, os, sys, urllib.error, urllib.request

import kit

B = "http://127.0.0.1:32123"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def domkirken():
    m = kit.Mesh()
    m.hall(-32, 28, -11, 11, 18, 30)              # nave and aisles
    m.hall(2, 16, -20, 20, 18, 30, along_x=False)  # transept
    m.hall(28, 44, -8, 8, 18, 27)                 # choir
    m.tower(-46, -32, -7, 7, 50, 96)              # west tower, spire to 96 m
    return m, kit.texture(1201)


def aabyhoj():
    m = kit.Mesh()
    m.hall(-9, 16, -6.5, 6.5, 8, 15)              # nave
    m.hall(16, 22, -4.5, 4.5, 7, 12)              # choir
    m.tower(-17, -9, -4, 4, 20, 27)               # west tower with a pointed tile roof
    return m, kit.texture(1945, brick_colour=(166, 74, 52), roof=kit.TILE, spire=kit.TILE, pointed=False, tall_windows=False)


def sankt_pauls():
    m = kit.Mesh()
    m.hall(-20, 22, -10, 10, 13, 22)              # nave
    m.hall(22, 28, -6, 6, 11, 17)                 # choir
    m.tower(-27, -20, -11, -4, 30, 46)            # twin towers flank the front
    m.tower(-27, -20, 4, 11, 30, 46)
    m.hall(-24, -20, -4, 4, 16, 22)               # entrance bay between them
    return m, kit.texture(1887, brick_colour=(170, 82, 58), roof=kit.SLATE, spire=kit.COPPER, pointed=False)


def sankt_lukas():
    m = kit.Mesh()
    m.hall(-16, 20, -11, 11, 14, 22)              # nave
    m.hall(20, 25, -7, 7, 12, 18)                 # choir
    m.tower(-25, -16, -4.5, 4.5, 34, 48)          # tower at the front, copper cap
    return m, kit.texture(1926, brick_colour=(150, 80, 60), roof=kit.TILE, spire=kit.COPPER, pointed=False)


def vor_frue():
    m = kit.Mesh()
    m.hall(-14, 18, -7, 7, 12, 20)                # nave of the old priory church
    m.hall(18, 24, -5, 5, 10, 16)                 # choir
    m.tower(-21, -14, -3.5, 3.5, 28, 45)          # west tower with a slender copper spire
    return m, kit.texture(1250, brick_colour=(158, 76, 54), roof=kit.TILE, spire=kit.COPPER, clock=False)


# key: (asset name, builder, description, footprint centre x, z, tower_towards in degrees)
CHURCHES = {
    "aarhus_domkirke": ("Aarhus Domkirke", domkirken, "Aarhus Cathedral. Brick Gothic, 93 m long, spire to 96 m.", -1187, 90, 180),
    "aabyhoj_kirke": ("Aabyhoj Kirke", aabyhoj, "Aabyhoj Church, 1945. Red brick with a tile roof.", -4468, -110, 204),
    "sankt_pauls_kirke": ("Sankt Pauls Kirke", sankt_pauls, "St Paul's Church, 1887. Red brick with twin towers.", -1597, -1109, 95),
    "vor_frue_kirke": ("Vor Frue Kirke", vor_frue, "Church of Our Lady, the old Dominican priory church. Brick Gothic.", -1537, 225, 175),
    "sankt_lukas_kirke": ("Sankt Lukas Kirke", sankt_lukas, "St Luke's Church, 1926. Brick with a copper-capped tower.", -2214, -1245, 9),
}


def call(path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(B + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))


def cells(mesh):
    low, high = mesh.extent()
    width = math.ceil(max(abs(low[0]), abs(high[0])) * 2 / 8)
    length = math.ceil(max(abs(low[2]), abs(high[2])) * 2 / 8)
    return max(1, width), max(1, length)


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "generate"
    wanted = sys.argv[2:] or list(CHURCHES)
    for key in wanted:
        name, build, description, x, z, tower_towards = CHURCHES[key]
        folder = os.path.join(ROOT, "out", "assets", key).replace("\\", "/")
        mesh, image = build()
        width, length = cells(mesh)
        prefab = f"{name}.{name}_Data"
        if step == "generate":
            kit.save(folder, mesh, image, "tools/landmarks/churches.py")
            low, high = mesh.extent()
            print(f"{name}: {len(mesh.faces)} faces, {high[0] - low[0]:.0f} x {high[2] - low[2]:.0f} m, {high[1]:.0f} m high, lot {width} x {length} cells")
        elif step == "create":
            r = call("/commands/create-asset", {"name": name, "folder": folder, "template": "Statue of Shopping",
                                                "cellWidth": width, "cellLength": length, "description": description})
            print(f"{name}:", r.get("file") or r.get("error"))
        elif step == "place":
            angle = (tower_towards + 180) % 360
            for f in call("/state/facilities?limit=65536&service=Monument")["facilities"]:
                if f["prefab"] == prefab:
                    call("/commands/bulldoze", {"entityType": "building", "id": f["id"]})
            for g in call("/state/growables?limit=65536")["growables"]:
                if math.hypot(g["position"]["x"] - x, g["position"]["z"] - z) < max(width, length) * 4 + 6:
                    call("/commands/bulldoze", {"entityType": "building", "id": g["id"]})
            r = call("/commands/place-building", {"dryRun": False, "buildingPrefab": prefab, "position": {"x": x, "z": z}, "angleDegrees": angle})
            print(f"{name} at {x},{z} turned {angle}:", r.get("ok"), r.get("error", ""))
        else:
            sys.exit("step must be generate, create or place")


if __name__ == "__main__":
    main()
