# Tools

Python scripts that work on a running game through the mod in `mod/` (HTTP on `127.0.0.1:32123`). Run them from the repository root with a city loaded, for example `py -X utf8 tools\zones.py ...`. Every script that changes the city does nothing without `--live`: it first prints what it would do. Each file starts with its full usage.

Data files come from OpenStreetMap (queries in `cities/*.overpassql`) and from the Danish municipal plan register plandata.dk; put them in `data/`.

## Streets

| Script | What it does |
|---|---|
| `georef.py` | Works out a city's scale and rotation from points known both on the map and in the game. |
| `highway_links.py` | Joins the map's raised highways to the nearest streets, so that traffic and newcomers can enter. |
| `thin_streets.py` | Removes small streets beyond a radius. The game's path finder gives out on too many road pieces. |
| `add_streets.py` | Puts one neighbourhood's planned streets back, or the streets inside business areas. |
| `street_names.py` | Replaces the game's invented street names with the name of the real street each piece joins. |

## Land, services and utilities

| Script | What it does |
|---|---|
| `zones.py` | Zones land by the municipal plan (or OpenStreetMap land use) and names districts. |
| `utilities.py` | Lays water pipes under zoned land and seeds power and water for a new area. |
| `repipe.py` | Rebuilds all water pipes so every tower and treatment plant counts (the game has a limit of 1,024). |
| `infrastructure.py` | Places real power plants, water works, wastewater plants and waste sites. |
| `civic.py` | Places real schools, clinics, fire and police stations, libraries and cemeteries, with their names. |
| `greenery.py` | Plants the real forests and parks from OpenStreetMap, with park name signs. |
| `turbines.py` | Removes seeded wind turbines once the land round them is built up. |
| `metro.py` | Builds the light rail as a metro line with stations at the real stops. |
| `workshop_homes.py` | Makes subscribed Workshop houses the ones that grow, as a district style. |

## Landmarks (`landmarks/`)

| Script | What it does |
|---|---|
| `kit.py` | Shared parts: simple meshes, painted facades, packing into game assets, roadside placing, name signs. |
| `churches.py` | Aarhus churches as generated models: generate, pack, place, name. |
| `buildings.py` | Other Aarhus landmarks the same way (Dokk1, Navitas, Lighthouse, ...). |
| `shops.py` | One building per real shop chain, placed where OpenStreetMap has that shop. |

## Pictures and video

| Script | What it does |
|---|---|
| `screenshot.py` | Saves a picture of a spot from a chosen direction and height, without bringing the game to the front. |
| `flyby.py` | Records a smooth fly-by video along a route of camera keys (`cities/*.flyby.json`). |
| `jitter.py` | Measures frame-to-frame shake in a recorded video. |
| `follow.py` | Keeps the game camera on where new buildings appear. |
