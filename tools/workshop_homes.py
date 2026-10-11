"""Put subscribed Steam Workshop houses into use.

Growable houses from the Workshop only appear when a new home happens to grow and the game happens
to pick them. This script makes them the rule:

  style   saves a district style "Aarhus" holding every Workshop house that is loaded
          (restart the game afterwards: styles are read when a city loads)
  apply   makes every district grow from that style
  swap    replaces existing houses of the game's own with a Workshop house of the same density,
          lot size and level, in the same place, facing the same way, and steps a Workshop house
          that complains of low land value down to the lowest level. [--limit N] stops after N.
          Note: once the style is applied the game itself removes houses that are not in it.

Use (from the repo root, a city loaded): py tools\\workshop_homes.py style | apply | swap [--limit N]
Needs the mod build in mod/.
"""
import collections, random, re, sys

from zones import call

STYLE = "Aarhus"
WORKSHOP = re.compile(r"^\d+\.")   # Workshop assets are named <workshop id>.<asset>_Data


def workshop_homes():
    prefabs = call("/prefabs/buildings?limit=65536")["buildings"]
    return [p for p in prefabs if p["service"] == "Residential" and WORKSHOP.match(p["name"])]


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    homes = workshop_homes()
    if step == "style":
        r = call("/commands/create-style", {"name": STYLE, "prefabs": ";".join(p["name"] for p in homes)})
        print(r)
        kinds = collections.Counter((p["subService"], p["level"], f"{p['width']}x{p['length']}") for p in homes)
        for (sub, level, size), n in sorted(kinds.items()):
            print(f"  {n:2d} {sub} {level} {size}")
    elif step == "apply":
        print(call("/commands/apply-style", {"name": STYLE}))
    elif step == "swap":
        limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
        by_lot = collections.defaultdict(list)
        for p in homes:
            by_lot[(p["subService"], p["width"], p["length"])].append(p)
        rng = random.Random(1)
        swapped = no_match = failed = 0
        struggling = {p["id"] for p in call("/state/problems?limit=20000")["problems"] if "LandValueLow" in p["problems"]}
        for g in call("/state/growables?limit=65536")["growables"]:
            if g["service"] != "Residential" or g.get("abandoned"):
                continue
            ours = bool(WORKSHOP.match(g["prefab"]))
            if ours and g["id"] not in struggling:
                continue
            lot = by_lot.get((g["subService"], g["width"], g["length"]))
            if not lot:
                no_match += 1
                continue
            # A house of a higher level than the land is worth complains and is abandoned: take the
            # house's own level or the nearest below it, and the lowest there is for one that complains.
            levels = sorted({p["level"] for p in lot})
            wanted = levels[0] if ours else max([l for l in levels if l <= g["level"]], default=levels[0])
            choices = [p["name"] for p in lot if p["level"] == wanted]
            if ours and g["prefab"] in choices:
                continue
            if limit is not None and swapped >= limit:
                break
            call("/commands/bulldoze", {"entityType": "building", "id": g["id"]})
            r = call("/commands/place-building", {"dryRun": False, "buildingPrefab": rng.choice(choices),
                                                  "position": {"x": g["position"]["x"], "z": g["position"]["z"]}, "angleDegrees": g["angleDegrees"] % 360})
            if r.get("ok"):
                swapped += 1
            else:
                failed += 1
        print(f"swapped {swapped}, no Workshop house for that lot size {no_match}, failed {failed}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
