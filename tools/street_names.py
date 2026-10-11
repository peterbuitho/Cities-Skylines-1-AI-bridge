"""Replace the game's invented street names.

OpenStreetMap has no name for some road pieces (service roads, stubs, parking aisles, ramps). The
game fills a blank with a random English name such as "Ward Street". This gives each such piece the
name of the nearest real street it is joined to, walking along the road network. A piece that
reaches no named street keeps what it has.

A name counts as real when the import plan has it, or when it is one this project made up
("Motorvejstilslutning").

Use (from the repo root, a city loaded): py tools\\street_names.py <plan.json> [--live]
"""
import collections, json, sys

from zones import call

OURS = {"Motorvejstilslutning"}


def main():
    live = "--live" in sys.argv
    real = {s["name"] for s in json.load(open(sys.argv[1], encoding="utf-8"))["segments"] if s.get("name")} | OURS
    roads = call("/state/networks?service=Road&limit=65536")["segments"]
    at_node = collections.defaultdict(list)
    for s in roads:
        at_node[s["startNodeId"]].append(s)
        at_node[s["endNodeId"]].append(s)

    # spread the real names outwards over the invented ones, nearest first
    name = {s["id"]: s["name"] for s in roads if s["name"] in real}
    queue = collections.deque(s for s in roads if s["id"] in name)
    while queue:
        s = queue.popleft()
        for node in (s["startNodeId"], s["endNodeId"]):
            for other in at_node[node]:
                if other["id"] not in name:
                    name[other["id"]] = name[s["id"]]
                    queue.append(other)
    invented = [s for s in roads if s["name"] not in real]
    fix = collections.defaultdict(list)
    for s in invented:
        if s["id"] in name:
            fix[name[s["id"]]].append(s["id"])
    print(f"road pieces: {len(roads)}; with an invented or no name: {len(invented)}; can take a real street's name: {sum(len(v) for v in fix.values())}")
    print("invented names, e.g.:", ", ".join(sorted({s["name"] for s in invented if s["name"]})[:12]))
    if not live:
        print("DRY RUN: nothing was renamed")
        return
    done = 0
    for street, ids in fix.items():
        for i in range(0, len(ids), 200):
            done += call("/commands/name-segments", {"name": street, "ids": ";".join(str(k) for k in ids[i:i + 200])}).get("named", 0)
    print(f"renamed: {done}")


if __name__ == "__main__":
    main()
