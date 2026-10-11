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
import kit


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


def sankt_johannes():
    m = kit.Mesh()
    m.hall(-14, 20, -9, 9, 13, 22)                # nave
    m.hall(2, 12, -13, 13, 13, 21, along_x=False)  # transept
    m.hall(20, 25, -6, 6, 11, 17)                 # choir
    m.tower(-23, -14, -4.5, 4.5, 34, 58)          # west tower with a tall spire
    return m, kit.texture(1905, brick_colour=(162, 74, 54), roof=kit.SLATE, spire=kit.COPPER)


def christianskirken():
    m = kit.Mesh()
    m.hall(-12, 21, -10, 10, 12, 20)              # the wide nave of 1958
    m.tower(-21, -14, -13, -6, 30, 36)            # the tower stands beside the front
    return m, kit.texture(1958, brick_colour=(204, 176, 122), roof=kit.TILE, spire=kit.COPPER, pointed=False, clock=False)


# key: (asset name, builder, description, footprint centre x, z, tower_towards in degrees)
CHURCHES = {
    "aarhus_domkirke": ("Aarhus Domkirke", domkirken, "Aarhus Cathedral. Brick Gothic, 93 m long, spire to 96 m.", -1187, 90, 180),
    "aabyhoj_kirke": ("Aabyhoj Kirke", aabyhoj, "Aabyhoj Church, 1945. Red brick with a tile roof.", -4468, -110, 204),
    "sankt_pauls_kirke": ("Sankt Pauls Kirke", sankt_pauls, "St Paul's Church, 1887. Red brick with twin towers.", -1597, -1109, 95),
    "vor_frue_kirke": ("Vor Frue Kirke", vor_frue, "Church of Our Lady, the old Dominican priory church. Brick Gothic.", -1537, 225, 175),
    # which end the tower is on is assumed (west), not read from the footprint
    "sankt_johannes_kirke": ("Sankt Johannes Kirke", sankt_johannes, "St John's Church, 1905. Red brick with a tall spire.", -1214, 1445, 165),
    "christianskirken": ("Christianskirken", christianskirken, "Christian's Church, 1958. Yellow brick.", -2119, 2385, 165),
    "sankt_lukas_kirke": ("Sankt Lukas Kirke", sankt_lukas, "St Luke's Church, 1926. Brick with a copper-capped tower.", -2214, -1245, 9),
}


if __name__ == "__main__":
    # the tower end, model -x, points at tower_towards, so the building is turned half a circle from it
    kit.run({key: (name, build, text, x, z, towards + 180) for key, (name, build, text, x, z, towards) in CHURCHES.items()},
            "tools/landmarks/churches.py")
