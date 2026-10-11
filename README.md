# Cities Skylines 1 AI bridge

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

## Zones, names and utilities from real land use

Zoned land only develops inside map tiles the city owns, near a powered building. Buy the tiles first (the mod's `POST /commands/unlock-area {"x":..,"z":..}`, one tile per call, each touching an owned one), then zone.

`tools/zones.py` reads two kinds of source:

- **Danish municipal plan frames** (kommuneplanrammer, open data from plandata.dk). The best source for Denmark: every area has an official use and a floor area ratio, which gives the density. `751` is the municipality code for Aarhus.
- **OpenStreetMap land use**, anywhere in the world. Coarser, with very little commercial land, but it carries the place names that become districts.

```powershell
curl.exe -A citybridge -o data\aarhus.plandata.json "https://geoserver.plandata.dk/geoserver/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=pdk:theme_pdk_kommuneplanramme_vedtaget_v&outputFormat=application/json&srsName=EPSG:4326&cql_filter=komnr=751"
curl.exe -A citybridge -o data\aarhus.landuse.osm.json --data-urlencode "data@cities\aarhus.landuse.overpassql" https://overpass-api.de/api/interpreter

# arguments: source, city, bounds of the owned tiles, city centre (only used for OpenStreetMap density)
py -X utf8 tools\zones.py data\aarhus.landuse.osm.json cities\aarhus.toml "-4800,-2880,960,2880" "-1187,58" --live   # names the districts
py -X utf8 tools\zones.py data\aarhus.plandata.json cities\aarhus.toml "-4800,-2880,960,2880" "-1187,58" --live      # zones by the plan
py -X utf8 tools\utilities.py data\aarhus.plandata.json cities\aarhus.toml "-4800,-2880,960,2880" "-1187,58" --live
```

`zones.py` zones each piece of land by the area it lies in and unzones everything else; cells with a building are left alone. `utilities.py` lays a water pipe grid under the zoned land and seeds wind turbines and water towers; run it once, it does not skip what is already there.

To put a neighbourhood's small streets back into a thinned city (then run `zones.py` again to zone them):

```powershell
py -X utf8 tools\add_streets.py out\aarhus.plan.json "-3967,-85" 1100 --live   # Åbyhøj
```

## Landmarks as generated models

A landmark the Steam Workshop does not have (see `cities/aarhus.workshop.md`) can be generated: a script writes a mesh and a facade texture from the building's real measures, and the mod packs them into a game asset.

```powershell
py -X utf8 tools\landmarks\churches.py generate            # writes out/assets/<key>/model.obj and textures
py -X utf8 tools\landmarks\churches.py create              # city loaded: packs each into a game asset; then restart the game
py -X utf8 tools\landmarks\churches.py place               # puts each at its real position, with its name on a footpath in front
py -X utf8 tools\landmarks\buildings.py generate dokk1     # the same three steps for other buildings; keys are optional
py -X utf8 tools\screenshot.py -1187 90 shot.png --size 150   # look at it; --ui shows street names
```

`label` instead of `place` adds only the name. The name is a short named footpath, so it shows the way street names do.

## Services and houses

```powershell
py -X utf8 tools\civic.py data\aarhus.civic.osm.json cities\aarhus.toml "-4800,-2880,960,2880" --live   # schools, clinics, fire, police, libraries, cemeteries at real sites
py -X utf8 tools\workshop_homes.py style    # once, then restart: a district style of the subscribed Workshop houses
py -X utf8 tools\workshop_homes.py apply    # after every load: all districts grow from it
py -X utf8 tools\turbines.py --live         # remove seeded wind turbines that now stand among buildings
```

Before `turbines.py --live`: the city must have power plants that cover its use (`GET /state/growth` shows capacity and use) and a power line from them to the built-up area, or the city goes dark. Save first, run the game for a minute afterwards and look at `/state/problems`.

Growth is slow by default because the game raises demand in small steps. `POST /commands/set-simulation-speed {"paused":false,"speed":3,"fastDemand":true}` lets demand follow the game's own computed value at once.

## Light rail as metro

The game has no trams without the Snowfall expansion, so `tools/metro.py` builds a real light-rail route as a ground-level metro: a station at each named stop, track along the OpenStreetMap alignment, and one line out and back.

```powershell
# light-rail track and stops (same bounding box as the streets)
curl.exe -A citybridge -o data\aarhus.lightrail.osm.json --data-urlencode "data@cities\aarhus.lightrail.overpassql" https://overpass-api.de/api/interpreter
py -X utf8 tools\metro.py data\aarhus.lightrail.osm.json cities\aarhus.toml "Aarhus H;Dokk1;Skolebakken;Nørreport" --live
```

## A new city

Copy `cities/aarhus.toml` and `cities/aarhus.overpassql`. The `.toml` says which real-world point is at the centre of the game map, the scale and the rotation. For Aarhus these were found by matching the OpenStreetMap coastline to the game's shoreline.

## Limits

- Roads are built at ground level. Bridges and tunnels are flattened, and a road that would cross open water is left out and listed in `<plan>.problems.txt`.
- Curves become straight pieces of 12 to 96 m.
- The game stores about 36,000 road segments and 49,000 zoning grids, but its path finder gives up on far fewer: with every real street of Aarhus (about 28,000 segments) nobody could move in. About 13,000 segments work. Keep small streets to the area you build out.

Map data (c) OpenStreetMap contributors, ODbL.
