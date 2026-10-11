# citybridge

Puts real street networks into Cities: Skylines 1. It reads OpenStreetMap data, turns it into a build plan, and builds the plan in a running game through the Skylines Agent Bridge mod. Use the build of the mod in `mod/` (see `mod/README.md`): it is thread-safe and lists whole cities, which the stock mod does not. See `PLAN.md` for the design and what is still to come.

## Use

The game must be running with a city loaded, on a map made from the city's heightmap.

```powershell
# 1. Street data from OpenStreetMap (Overpass API)
curl.exe -o data\aarhus.osm.json --data-urlencode "data@cities\aarhus.overpassql" https://overpass-api.de/api/interpreter

# 2. Plan and preview
cargo run --release -- import data\aarhus.osm.json cities\aarhus.toml out

# 3. Check the bridge, validate, build, save
cargo run --release -- smoke
cargo run --release -- build out\aarhus.plan.json --dry-run
cargo run --release -- build out\aarhus.plan.json
cargo run --release -- check
cargo run --release -- save Aarhus-2026
```

`build` skips roads that are already in the game, so an interrupted build can be run again. `clear --yes` bulldozes the loaded city and keeps only highways and rail; save first.

## Making the city playable

A full import is too dense for the game (see Limits). Two scripts fix a freshly built city; both print what they would do and change the game only with `--live`:

```powershell
py tools\highway_links.py --live                          # join the map's highways to the streets
py tools\thin_streets.py out\aarhus.plan.json 2500 --live  # small streets only within 2.5 km of the centre
```

## A new city

Copy `cities/aarhus.toml` and `cities/aarhus.overpassql`. The `.toml` says which real-world point is at the centre of the game map, the scale and the rotation. For Aarhus these were found by matching the OpenStreetMap coastline to the game's shoreline.

## Limits

- Roads are built at ground level. Bridges and tunnels are flattened, and a road that would cross open water is left out and listed in `<plan>.problems.txt`.
- Curves become straight pieces of 12 to 96 m.
- The game stores about 36,000 road segments and 49,000 zoning grids, but its path finder gives up on far fewer: with every real street of Aarhus (about 28,000 segments) nobody could move in. About 13,000 segments work. Keep small streets to the area you build out.

Map data (c) OpenStreetMap contributors, ODbL.
