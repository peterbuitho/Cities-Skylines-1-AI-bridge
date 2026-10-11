"""Real shop chains as game buildings, placed where the real shops are.

One simple building per chain: a flat-roofed box with the chain's name in its colours over a
glazed front. Positions come from OpenStreetMap shops (cities/*.shops.overpassql). Each shop is
put beside the nearest street, facing it. The buildings are copied from one of the game's unique
buildings, so they look like the shop but do not trade as commercial zone buildings do.

Use (from the repo root, a city loaded for the last two steps):
  py tools\\landmarks\\shops.py generate
  py tools\\landmarks\\shops.py create                       then restart the game
  py tools\\landmarks\\shops.py place <shops.osm.json> <city.toml> <minX,minZ,maxX,maxZ>
"""
import json, math, os, sys, tomllib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import kit
from zones import projector

WHITE, BLACK = (255, 255, 255), (20, 20, 20)
# chain: (name on the sign, wall, sign band, lettering, size class)
SIZES = {"kiosk": (16, 12, 4.5), "market": (40, 28, 6.5), "hall": (64, 40, 9.0)}   # width, depth, height in metres
CHAINS = {
    "Netto": ("Netto", (236, 236, 232), (250, 206, 20), BLACK, "market"),
    "Rema 1000": ("REMA 1000", (238, 238, 236), (20, 52, 120), WHITE, "market"),
    "Føtex": ("føtex", (232, 232, 230), (16, 42, 96), WHITE, "market"),
    "365discount": ("365 discount", (236, 236, 232), (0, 132, 72), WHITE, "market"),
    "Lidl": ("Lidl", (234, 234, 232), (0, 80, 170), (255, 222, 0), "market"),
    "SuperBrugsen": ("SuperBrugsen", (236, 232, 228), (200, 24, 34), WHITE, "market"),
    "Kvickly": ("Kvickly", (236, 232, 228), (206, 22, 40), WHITE, "market"),
    "Løvbjerg": ("Løvbjerg", (236, 236, 230), (22, 110, 60), WHITE, "market"),
    "7-Eleven": ("7-ELEVEN", (244, 244, 240), (0, 120, 70), (255, 130, 20), "kiosk"),
    "Circle K": ("Circle K", (240, 240, 238), (218, 40, 40), WHITE, "kiosk"),
    "Silvan": ("SILVAN", (226, 228, 230), (0, 74, 150), (255, 210, 0), "hall"),
    "Bauhaus": ("BAUHAUS", (230, 230, 228), (214, 30, 36), WHITE, "hall"),
    "Harald Nyborg": ("Harald Nyborg", (232, 232, 228), (240, 120, 0), (10, 40, 110), "hall"),
    "jem & fix": ("jem & fix", (240, 222, 40), (0, 66, 150), (250, 220, 30), "hall"),
    "thansen": ("thansen", (228, 228, 226), (20, 20, 20), (255, 200, 0), "hall"),
    "JYSK": ("JYSK", (232, 234, 238), (0, 60, 150), WHITE, "hall"),
    "Elgiganten": ("Elgiganten", (234, 236, 234), (30, 150, 60), WHITE, "hall"),
    "Stark": ("STARK", (228, 230, 234), (0, 54, 120), WHITE, "hall"),
}
# how OpenStreetMap spells them
ALIASES = {"thansen.dk": "thansen", "T. Hansen": "thansen", "Silvan Lille Torv": "Silvan", "Føtex Go!": "Føtex", "Fakta": "365discount",
           "REMA 1000": "Rema 1000", "Jem & Fix": "jem & fix"}


def asset_name(chain):
    # the mod's JSON reader and the asset file name are happier without Danish letters and signs
    return "Butik " + chain.replace("ø", "o").replace("Ø", "O").replace("&", "og").replace("-", " ")


def build(chain):
    sign, wall, band, text, size = CHAINS[chain]
    width, depth, height = SIZES[size]
    m = kit.Mesh()
    m.block(-width / 2, width / 2, -depth / 2, depth / 2, height, sign_every=20 if size != "kiosk" else 16)
    return m, kit.shop_texture(sign, wall, band, text), (width, depth)


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "generate"
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if step in ("generate", "create"):
        for chain in CHAINS:
            name = asset_name(chain)
            folder = os.path.join(root, "out", "assets", name.lower().replace(" ", "_")).replace("\\", "/")
            mesh, image, (width, depth) = build(chain)
            if step == "generate":
                kit.save(folder, mesh, image, "tools/landmarks/shops.py", texture_size=512)
                print(f"{name}: {width:.0f} x {depth:.0f} m")
            else:
                r = kit.call("/commands/create-asset", {"name": name, "folder": folder, "template": "Statue of Shopping",
                                                        "cellWidth": math.ceil(width / 8), "cellLength": math.ceil(depth / 8),
                                                        "description": chain + " shop."})
                print(f"{name}:", "ok" if r.get("ok") else r.get("error"))
        return

    project = projector(tomllib.load(open(sys.argv[3], "rb")))
    min_x, min_z, max_x, max_z = (float(v) for v in sys.argv[4].split(","))
    shops = []
    for e in json.load(open(sys.argv[2], encoding="utf-8"))["elements"]:
        tags = e.get("tags", {})
        chain = tags.get("brand") or tags.get("name") or ""
        chain = ALIASES.get(chain, chain)
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if chain in CHAINS and lat is not None:
            x, z = project(lat, lon)
            if min_x <= x <= max_x and min_z <= z <= max_z:
                shops.append((chain, x, z))
    print(f"{len(shops)} shops of {len({s[0] for s in shops})} chains inside the bounds")

    roads = [s for s in kit.call("/state/networks?service=Road&limit=65536")["segments"] if "Highway" not in s["prefab"]]
    growables = kit.call("/state/growables?limit=65536")["growables"]
    fixed = kit.call("/state/facilities?limit=65536")["facilities"] + kit.call("/state/facilities?limit=65536&service=Monument")["facilities"]
    taken = [(f["position"]["x"], f["position"]["z"], 30.0) for f in fixed]
    placed = skipped = 0
    for chain, x, z in shops:
        width, depth, _ = SIZES[CHAINS[chain][4]]
        name = asset_name(chain)
        done = kit.beside_road(f"{name}.{name}_Data", x, z, width, depth, roads, growables, taken)
        placed += done
        skipped += not done
    print(f"placed {placed}, no room for {skipped}")


if __name__ == "__main__":
    main()
