"""Aarhus landmarks that are not churches, as generated game models.

Positions and footprint directions are from OpenStreetMap where the building is mapped; shapes,
heights and colours are from what is known of each building. Simple models: flat walls with the
windows painted on. Meant to be recognisable, not exact.

Use (from the repo root): py tools\\landmarks\\buildings.py generate | create | place [key ...]
"""
import kit


def toldboden():
    """The old custom house on the harbour front, 1898: red brick, a central tower and two corner towers."""
    m = kit.Mesh()
    m.hall(-22, 22, -8, 6, 12, 19)                # main wing along the quay
    m.hall(-22, -12, -22, -8, 10, 16, along_x=False)   # two wings to the back
    m.hall(12, 22, -22, -8, 10, 16, along_x=False)
    m.tower(-5, 5, 4, 14, 26, 40)                 # central tower over the entrance
    m.tower(-25, -18, 3, 10, 18, 29)              # corner towers
    m.tower(18, 25, 3, 10, 18, 29)
    return m, kit.texture(1898, brick_colour=(164, 78, 56), roof=kit.TILE, spire=kit.COPPER, pointed=False, tall_windows=False)


def salling():
    """The department store on Søndergade: a five-storey block with a roof terrace."""
    m = kit.Mesh()
    m.block(-41, 41, -24, 24, 24)
    m.block(-20, 16, -10, 10, 29)                 # the roof pavilion
    return m, kit.block_texture(1906, wall=(206, 196, 176), glass=(48, 58, 72), floors=5)


def magasin():
    """The Magasin department store on Immervad: a five-storey block."""
    m = kit.Mesh()
    m.block(-28, 28, -30, 30, 24)
    return m, kit.block_texture(1871, wall=(184, 176, 164), glass=(44, 56, 70), floors=5)


def navitas():
    """Navitas on the harbour, 2014: a large star-shaped block in white bands and dark glass."""
    m = kit.Mesh()
    # the game allows a lot of at most 12 x 13 cells, so this is about four fifths of the real size
    m.block(-48, 48, -16, 16, 30)
    m.block(-18, 18, -44, 44, 30)
    return m, kit.block_texture(2014, wall=(232, 232, 228), glass=(36, 52, 70), floors=7, shopfront=False)


def paustian():
    """Paustian, the furniture house by the north harbour: a low white hall behind rows of columns."""
    m = kit.Mesh()
    m.block(-24, 24, -13, 13, 9)
    return m, kit.block_texture(1987, wall=(240, 238, 232), glass=(60, 74, 88), floors=2, columns=True)


# key: (asset name, builder, description, x, z, angle)
BUILDINGS = {
    "toldboden": ("Toldboden", toldboden, "The old custom house, 1898. Red brick with three towers.", -1035, -49, 233),
    "salling": ("Salling", salling, "Department store on Sondergade.", -1397, -183, 61),
    "magasin": ("Magasin", magasin, "Department store on Immervad.", -1435, 119, 71),
    "navitas": ("Navitas", navitas, "Engineering school and innovation centre on the harbour, 2014.", -950, 320, 15),
    "paustian": ("Paustian", paustian, "Furniture house by the north harbour.", -793, 969, 0),
}

if __name__ == "__main__":
    kit.run(BUILDINGS, "tools/landmarks/buildings.py")
