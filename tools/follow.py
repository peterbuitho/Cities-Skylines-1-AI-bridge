"""Keep the game camera on where the city is changing.

Every few seconds it looks at which buildings are new since the last look and moves the camera to
the busiest spot, so someone watching the game window sees the growth. Stop it with Ctrl+C.

Use (from the repo root, a city loaded): py tools\\follow.py [--every 20] [--minutes 60] [--size 900]
"""
import collections, sys, time

from zones import call

CELL = 400.0     # the city is looked at in squares this wide


def option(name, default):
    return float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def main():
    every, until = option("--every", 20), time.time() + option("--minutes", 60) * 60
    known, bearing = None, 0
    while time.time() < until:
        try:
            now = {g["id"]: (g["position"]["x"], g["position"]["z"]) for g in call("/state/growables?limit=65536")["growables"]}
        except OSError:
            time.sleep(every)
            continue
        if known is not None:
            fresh = [p for i, p in now.items() if i not in known]
            if fresh:
                busiest, count = collections.Counter((round(x / CELL), round(z / CELL)) for x, z in fresh).most_common(1)[0]
                spot = [p for p in fresh if (round(p[0] / CELL), round(p[1] / CELL)) == busiest]
                x, z = sum(p[0] for p in spot) / len(spot), sum(p[1] for p in spot) / len(spot)
                bearing = (bearing + 25) % 360      # a slow turn, so the view is not the same each time
                call("/commands/set-camera", {"position": {"x": round(x), "z": round(z)}, "size": option("--size", 900), "rotation": bearing, "tilt": 42})
                print(f"{count} new buildings near {x:.0f},{z:.0f}", flush=True)
        known = now
        time.sleep(every)


if __name__ == "__main__":
    main()
