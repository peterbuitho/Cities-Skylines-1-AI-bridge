"""Take away the wind turbines that utilities.py seeded, once the land round them is built up.

Zoned land only develops near a powered building, so empty land needs a turbine to start with.
Buildings pass power on to their neighbours, so a turbine standing among buildings is no longer
needed there, as long as the city's power plants make enough. Turbines on still empty land stay.
Run it again as the city grows, then let the game run and look at /state/problems for "Electricity".

Use (from the repo root, a city loaded): py tools\\turbines.py [--live] [--buildings 8] [--radius 160]
"""
import math, sys

from zones import call


def option(name, default):
    return float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def main():
    live = "--live" in sys.argv
    need, radius = option("--buildings", 8), option("--radius", 160)
    turbines = [f for f in call("/state/facilities?limit=65536&service=Electricity")["facilities"] if f["prefab"] == "Wind Turbine"]
    houses = [(g["position"]["x"], g["position"]["z"]) for g in call("/state/growables?limit=65536")["growables"]]
    removed = 0
    for t in turbines:
        x, z = t["position"]["x"], t["position"]["z"]
        if sum(1 for hx, hz in houses if math.hypot(hx - x, hz - z) < radius) >= need:
            removed += 1
            if live:
                call("/commands/bulldoze", {"entityType": "building", "id": t["id"]})
    print(f"wind turbines: {len(turbines)}; among buildings {'and removed' if live else '(dry run, not removed)'}: {removed}; left on empty land: {len(turbines) - removed}")


if __name__ == "__main__":
    main()
