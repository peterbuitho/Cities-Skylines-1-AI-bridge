"""Aarhus landmarks that are not churches, as generated game models.

Positions and footprint directions are from OpenStreetMap where the building is mapped; shapes,
heights and colours are from what is known of each building. Simple models: flat walls with the
windows painted on. Meant to be recognisable, not exact.

Use (from the repo root): py tools\\landmarks\\buildings.py generate | create | place | label [key ...]
"""
import math

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


def dokk1():
    """Dokk1, 2015: a glazed base under a wide metal-clad slab that hangs over it on all sides."""
    m = kit.Mesh()
    m.block(-34, 34, -34, 34, 9)                                    # glass ground floors
    m.block(-48, 48, -48, 48, 21, base=9, band=kit.TOWER)           # the slab
    m.block(-16, 16, -16, 16, 26, base=21, band=kit.TOWER)          # roof plant
    return m, kit.block_texture(2015, wall=(150, 154, 158), glass=(52, 70, 88), floors=2, columns=True, roof=(120, 122, 126))


def isbjerget():
    """Isbjerget on Aarhus Ø, 2013: white housing blocks with steep peaks, like drifting ice."""
    m = kit.Mesh()
    heights = [(18, 30), (27, 40), (14, 24), (24, 36), (12, 22), (30, 44), (20, 31), (16, 27), (28, 41), (13, 23), (22, 33), (17, 28)]
    k = 0
    for z in (-36, -12, 12, 36):                                    # four rows of blocks
        for x0, x1 in ((-46, -17), (-15, 14), (16, 46)):
            wall, peak = heights[k % len(heights)]
            m.hall(x0, x1, z - 7, z + 7, wall, peak, along_x=False)
            k += 1
    return m, kit.block_texture(2013, wall=(244, 246, 250), glass=(70, 132, 196), floors=8, roof=(236, 239, 244), shopfront=False)


def musikhuset():
    """Musikhuset, 1982: a long glass foyer in front of the yellow brick concert halls."""
    m = kit.Mesh()
    m.block(-46, 46, 18, 38, 18)                                    # the glass foyer, towards the park
    m.block(-48, 48, -40, 18, 24, band=kit.TOWER)                   # the halls
    m.block(-18, 14, -34, -4, 36, band=kit.TOWER)                   # stage tower
    return m, kit.block_texture(1982, wall=(202, 172, 116), glass=(46, 62, 78), floors=2, columns=True, roof=(108, 108, 110))


def lighthouse():
    """Lighthouse on Aarhus O, 2022: a 142 m housing tower, the tallest in Denmark, on a low base."""
    m = kit.Mesh()
    m.block(-24, 24, -20, 20, 12)                                   # the base with shops
    m.block(-13, 13, -15, 15, 132, base=12)                         # the shaft
    m.block(-10, 10, -12, 12, 142, base=132)                        # the set-back top with the viewing floor
    return m, kit.block_texture(2022, wall=(236, 236, 232), glass=(74, 104, 130), floors=40, shopfront=False)


def aarhus_big():
    """AARhus on Aarhus O (Bjarke Ingels Group): a white block round a courtyard whose roof line climbs like a hill."""
    m = kit.Mesh()
    steps = [12, 20, 30, 42]                                         # each wing climbs from a low corner to a high one
    side = 44
    piece = 2 * side / len(steps)
    for k, h in enumerate(steps):
        a, b = -side + k * piece, -side + (k + 1) * piece
        down = steps[-1] - (steps[k] - steps[0])
        m.block(a, b, -side, -side + 16, h)                         # south wing, rising east
        m.block(side - 16, side, a, b, down)                        # east wing, falling north
        m.block(-b, -a, side - 16, side, h)                         # north wing, rising west
        m.block(-side, -side + 16, -b, -a, down)                    # west wing, falling south
    return m, kit.block_texture(2019, wall=(242, 242, 238), glass=(66, 92, 116), floors=10, shopfront=False)


def windmill():
    """An old Dutch-type windmill: a tapering shingled body, a cap, four sails."""
    m = kit.Mesh()
    m.frustum(0, 0, 5.5, 3.2, 0, 13, band=kit.TOWER)                # the body
    m.frustum(0, 0, 3.6, 1.2, 13, 16.5, band=kit.SPIRE)             # the cap
    hub = (0, 14.2, 3.9)
    for turn in range(4):                                            # sails in a plane just in front of the cap
        a = math.radians(45 + 90 * turn)
        along, across = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        corner = lambda r, w: (hub[0] + along[0] * r + across[0] * w, hub[1] + along[1] * r + across[1] * w, hub[2])
        m.sheet([corner(1, -0.9), corner(11, -0.9), corner(11, 0.9), corner(1, 0.9)],
                [(0, kit.PLAIN[0]), (1, kit.PLAIN[0]), (1, kit.PLAIN[1]), (0, kit.PLAIN[1])])
    return m, kit.texture(1800, brick_colour=(96, 74, 56), roof=(70, 54, 42), spire=(64, 50, 40), pointed=False, clock=False, tall_windows=False)


def den_gamle_by():
    """Den Gamle By, the open-air museum: a huddle of half-timbered town houses round a square."""
    m = kit.Mesh()
    houses = [(-38, -18, -38, -24, 6, 12, True), (-16, 6, -38, -26, 7, 14, True), (8, 24, -38, -24, 5, 11, True), (26, 38, -38, -10, 6, 12, False),
              (26, 38, -6, 22, 8, 15, False), (-38, -26, -20, 6, 6, 12, False), (-38, -26, 10, 38, 7, 13, False), (-22, 0, 26, 38, 6, 12, True),
              (4, 38, 26, 38, 8, 15, True), (-10, 8, -8, 8, 5, 10, True)]
    for x0, x1, z0, z1, wall, ridge, along_x in houses:
        m.hall(x0, x1, z0, z1, wall, ridge, along_x=along_x)
    return m, kit.timber_texture(1909)


def vaeksthusene():
    """The tropical house in the Botanical Garden: a glass dome shaped like a snail shell, beside the older glasshouses."""
    m = kit.Mesh()
    m.dome(8, 0, 30, 22, 18)                                         # the tropical dome
    m.hall(-44, -22, -9, 9, 5, 9)                                    # the long palm house of 1969
    return m, kit.block_texture(2013, wall=(238, 242, 240), glass=(142, 196, 200), floors=6, shopfront=False, roof=(170, 206, 208))


def prismet():
    """Prismet beside Den Gamle By, 2001: an 18-storey glass office tower on a three-sided plan with a sloping top."""
    m = kit.Mesh()
    corners = [(-16, -12), (18, -12), (-2, 20)]                     # the three-sided plan
    tops = [63, 52, 57]                                             # the roof slopes across the plan
    centre = (0, 30, -1)
    for k in range(3):
        a, b = corners[k], corners[(k + 1) % 3]
        u = math.dist(a, b) / (kit.BAY * 4)
        m.poly([(a[0], 0, a[1]), (b[0], 0, b[1]), (b[0], tops[(k + 1) % 3], b[1]), (a[0], tops[k], a[1])],
               [(0, kit.WALL[0]), (u, kit.WALL[0]), (u, kit.WALL[1]), (0, kit.WALL[1])], centre)
    m.poly([(c[0], t, c[1]) for c, t in zip(corners, tops)], [(0, kit.ROOF[0]), (1, kit.ROOF[0]), (0.5, kit.ROOF[1])], centre)
    return m, kit.block_texture(2001, wall=(170, 190, 200), glass=(58, 96, 124), floors=18, shopfront=False, roof=(150, 170, 182))


def marselisborg_slot():
    """Marselisborg Slot, 1902: the royal summer residence, a white house with round corner towers."""
    m = kit.Mesh()
    m.hall(-19, 19, -8, 8, 11, 17)
    for x in (-19, 19):
        m.frustum(x, 8, 4.5, 4.5, 0, 15, band=kit.WALL)             # the round towers on the garden side
        m.frustum(x, 8, 4.8, 0.3, 15, 21, band=kit.SPIRE)
    return m, kit.texture(1902, brick_colour=(240, 238, 230), roof=kit.SLATE, spire=kit.SLATE, pointed=False, clock=False, tall_windows=False)


YELLOW_BRICK = (204, 176, 122)   # the university's brick


def aarhus_teater():
    """Aarhus Teater, 1900: a pale art nouveau front with a gable, the auditorium and a higher stage house."""
    m = kit.Mesh()
    m.hall(-40, -8, -22, 22, 16, 24)                                # foyer and auditorium, gable to the square
    m.block(-8, 40, -25, 25, 20)                                    # back of house
    m.block(-4, 22, -18, 18, 30)                                    # stage tower
    return m, kit.texture(1900, brick_colour=(212, 196, 160), roof=kit.COPPER, spire=kit.COPPER, pointed=False, clock=False)


def city_tower():
    """Aarhus City Tower (Comwell), 2014: a 94 m dark glass slab beside the station."""
    m = kit.Mesh()
    m.block(-24, 24, -13, 13, 94)
    return m, kit.block_texture(2014, wall=(70, 76, 84), glass=(40, 62, 84), floors=22, shopfront=False)


def bruuns_galleri():
    """Bruuns Galleri, 2003: the shopping centre beside Aarhus H. About three fifths of its real length."""
    m = kit.Mesh()
    m.block(-56, 56, -34, 34, 14)
    m.block(-40, 40, -8, 8, 18)                                     # the glass roof over the mall street
    return m, kit.block_texture(2003, wall=(214, 208, 196), glass=(64, 92, 116), floors=3)


def ceres_panorama():
    """Ceres Panorama, 2018: a 70 m housing tower on the old brewery site."""
    m = kit.Mesh()
    m.block(-17, 17, -16, 16, 70)
    return m, kit.block_texture(2018, wall=(226, 224, 216), glass=(60, 84, 108), floors=20, shopfront=False)


def statsbiblioteket():
    """The State Library (Det Kgl. Bibliotek), 1963: low yellow brick wings and the book tower."""
    m = kit.Mesh()
    m.block(-47, 47, -25, 25, 12)
    m.block(-12, 12, -12, 12, 45, base=12, band=kit.TOWER)          # the book tower
    return m, kit.block_texture(1963, wall=YELLOW_BRICK, glass=(48, 60, 74), floors=3, shopfront=False, roof=(170, 140, 96))


def aulaen():
    """The university's main building with the Aula, 1946: yellow brick under yellow tile, a tall gable."""
    m = kit.Mesh()
    m.hall(-27, 27, -12, 12, 15, 26)
    m.hall(-27, -15, -30, -12, 10, 17, along_x=False)               # a wing to the side
    return m, kit.texture(1946, brick_colour=YELLOW_BRICK, roof=(196, 160, 98), spire=(196, 160, 98), pointed=False, clock=False)


def stadium():
    """Ceres Park, the stadium: four stands round the pitch. About two thirds of its real size."""
    m = kit.Mesh()
    m.block(-50, 50, 32, 46, 18, band=kit.TOWER)                    # the long stands
    m.block(-50, 50, -46, -32, 18, band=kit.TOWER)
    m.block(-50, -38, -32, 32, 12, band=kit.TOWER)                  # the ends
    m.block(38, 50, -32, 32, 12, band=kit.TOWER)
    return m, kit.block_texture(1920, wall=(206, 204, 198), glass=(70, 80, 92), floors=3, shopfront=False, roof=(150, 152, 156))


def storcenter_nord():
    """Storcenter Nord, the shopping centre on Finlandsgade. Under half its real length."""
    m = kit.Mesh()
    m.block(-55, 55, -32, 32, 13)
    return m, kit.block_texture(1977, wall=(198, 192, 180), glass=(58, 80, 100), floors=2)


def bestseller():
    """The Bestseller office on the harbour, 2015: dark stone blocks of uneven height round courtyards."""
    m = kit.Mesh()
    for k, h in enumerate((16, 26, 12, 22, 18)):
        m.block(-60 + k * 24, -36 + k * 24, -26, 26, h)
    return m, kit.block_texture(2015, wall=(84, 80, 76), glass=(44, 58, 72), floors=5, shopfront=False)


# Positions are OpenStreetMap footprint centres, moved by up to 96 m where the model would stand on a
# road or track: the game's roads are wider than the streets and the models are simpler than the buildings.
# key: (asset name, builder, description, x, z, angle)
BUILDINGS = {
    "toldboden": ("Toldboden", toldboden, "The old custom house, 1898. Red brick with three towers.", -1019, -77, 233),
    "salling": ("Salling", salling, "Department store on Sondergade.", -1383, -175, 61),
    "magasin": ("Magasin", magasin, "Department store on Immervad.", -1435, 119, 71),
    "navitas": ("Navitas", navitas, "Engineering school and innovation centre on the harbour, 2014.", -908, 296, 15),
    "dokk1": ("Dokk1", dokk1, "Library and citizens' service centre on the harbour front, 2015.", -944, -269, 38),
    "isbjerget": ("Isbjerget", isbjerget, "The Iceberg housing on Aarhus O, 2013.", 25, 983, 42),
    "musikhuset": ("Musikhuset", musikhuset, "The concert hall, 1982.", -1888, -333, 238),
    "lighthouse": ("Lighthouse", lighthouse, "Housing tower on Aarhus O, 142 m, 2022.", 122, 1057, 42),
    "aarhus_big": ("AARhus", aarhus_big, "Housing block on Aarhus O by Bjarke Ingels Group.", -87, 775, 42),
    "windmill": ("Gammel Vindmolle", windmill, "An old windmill.", -2239, 375, 0),
    "den_gamle_by": ("Den Gamle By", den_gamle_by, "The Old Town open-air museum: half-timbered town houses.", -2346, 320, 0),
    "vaeksthusene": ("Vaeksthusene", vaeksthusene, "The glasshouses in the Botanical Garden, with the tropical dome.", -2238, 446, 0),
    "prismet": ("Prismet", prismet, "Glass office tower beside Den Gamle By, 63 m, 2001.", -2324, 167, 0),
    # angle = the footprint's long axis; which long side is the front is not known
    "aarhus_teater": ("Aarhus Teater", aarhus_teater, "The theatre on Bispetorv, 1900.", -1186, 49, 96),
    "city_tower": ("Aarhus City Tower", city_tower, "Hotel and office tower beside the station, 94 m, 2014.", -1270, -625, 165),
    "bruuns_galleri": ("Bruuns Galleri", bruuns_galleri, "Shopping centre beside Aarhus H, 2003.", -1520, -766, 15),
    "ceres_panorama": ("Ceres Panorama", ceres_panorama, "Housing tower on the old Ceres brewery site, 70 m.", -2387, -147, 3),
    "statsbiblioteket": ("Statsbiblioteket", statsbiblioteket, "The State Library with its book tower, 1963.", -1863, 1485, 21),
    "aulaen": ("Aarhus Universitet Aulaen", aulaen, "The university's main building with the Aula, 1946.", -1797, 1609, 120),
    "stadium": ("Ceres Park", stadium, "The stadium in Marselisborg. Position within the sports park is estimated.", -2154, -2588, 177),
    "storcenter_nord": ("Storcenter Nord", storcenter_nord, "Shopping centre on Finlandsgade.", -2547, 1587, 78),
    "bestseller": ("Bestseller", bestseller, "Office on the harbour, 2015.", -828, 386, 141),
    "marselisborg_slot": ("Marselisborg Slot", marselisborg_slot, "The royal summer residence, 1902.", -1665, -3117, 123),
    "paustian": ("Paustian", paustian, "Furniture house by the north harbour.", -810, 986, 0),
}

if __name__ == "__main__":
    kit.run(BUILDINGS, "tools/landmarks/buildings.py")
