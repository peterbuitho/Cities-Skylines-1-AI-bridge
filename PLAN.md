# City Bridge: recreate real cities in Cities: Skylines

Goal: build real cities (starting with Aarhus, Denmark) in Cities: Skylines by importing real map data, then control the game from outside to run traffic experiments.

Target game: Cities: Skylines 1 (installed at `D:\Steam\steamapps\common\Cities_Skylines`).

## Status (2026-10-11)

Done: steps 1 to 3 of the build order. `citybridge` imports, validates, builds, checks and saves. Aarhus is built twice:
- `Aarhus-2026`: every real street, about 27,900 road segments from OpenStreetMap, 26,945 of them named. Nobody can move in (see the path-finder limit below).
- `Aarhus-2026-playable`: main roads everywhere, small streets (residential, unclassified, living street) only within 2.5 km of the centre at (-1600, 400). About 13,400 segments. People move in: 743 residents after four game-months.

Found on the way:
- **The game's path finder holds at most 65,536 lane entries per search** (`PathFind.AddBufferItem`: 1,024 buckets of 64). A citizen's "drive, then walk" search starts at the home and spreads over every car and pedestrian lane cheaper than the route. With 168,800 lanes on the map it overflowed before reaching the map edge, so every household assigned to a home was dropped. Car-only searches still worked, which hid it. Budget: about 13,000 road segments, not the 36,864 the game can store.
- **Three of the four incoming highway connections had no road to the city.** Five link roads named "Motorvejstilslutning" join the map's raised highways to the nearest streets. The outgoing connection at (-8646, 6159) is still unlinked (548 m gap).
- **One-way roads run from start node to end node.** Checked in `RoadBaseAI.UpdateOutsideFlags`. A map-edge building flagged `Outgoing` is where traffic enters the map.
- **Diagnostics in `mod/`:** `GET /state/move-in` (outside connections, homes, who is moving in, route probes from each entrance) and `GET /state/route?fx&fz&tx&tz&drive&max` (one route search between two points; `fz=-1` or `tz=-1` means the x value is a segment id).
- **Zoned land only develops inside owned map tiles.** The city owns one tile: x -2880..-960, z -960..960. Zone cells outside it are never valid, so the industrial area at (-3400, -600) stayed empty, residents had no jobs, and housing demand fell to zero (`ZoneManager.CalculateResidentialDemand` subtracts unemployment). `GET /state/growth` shows it: free rows per zone, the demand the game really uses, and its good-place counter. `POST /commands/unlock-area` buys a tile; the game's population milestone per tile is bypassed through 81 Tiles' "ignore unlocking" switch. The city now owns the 3x3 block around the centre: x -4800..960, z -2880..2880, zoned from the municipal plan (plandata.dk kommuneplanrammer: official use and floor area ratio per area) by `tools/zones.py`, with 28 districts named from OpenStreetMap places, and piped and powered by `tools/utilities.py`. `/state/areas` uses the 5x5 grid and is off by two tiles when 81 Tiles is installed.
- **A water or sewage building only joins pipes that are already there when it is placed.** Lay the pipe first, then place the building on it. Eight outlets placed first and piped afterwards stayed "not connected" until they were removed and placed again.
- **Inside owned tiles, land develops only near a powered building.** `ZoneBlock.IsGoodPlace` wants a building that carries electricity within about 40 m. Seed each new zone with a wind turbine.
- **A transport line's reported length is travel time, not metres**, when its route mixes walking and riding (`PathFind` stores duration in `m_length`). Probably why the 6.5 km metro line reads 38.9 km; not verified.
- **A train station brings its own track and the game adds intercity lines to it.** The mod now joins rail to rail of the same kind, so `build-network` with `Train Track` can connect a station's track to the main line.
- **The stock bridge is not thread-safe.** It runs commands from `ThreadingExtensionBase.OnUpdate` (main thread) while the simulation thread reads the same data. Bulk work raised 22 "Array index is out of range" / "HashSet modified" simulation errors. Fixed in `mod/`: changing commands run on the simulation thread.
- **The stock bridge lists at most 5000 entries.** Clearing or resuming from such a list goes wrong quietly. Fixed in `mod/` (65536), and `citybridge` now refuses a cut-off list.
- **The terrain route reads whole numbers only and samples no finer than 20 m.** `citybridge` sent fractional coordinates and asked for 16 m, so the bridge answered with its default area and the water test of the first Aarhus build was wrong. Fixed in the client (whole 20 m steps, reply checked). Repaired in the game: 188 wrongly skipped segments built, 55 segments that sit in water removed.
- **The DLL that was installed was not upstream.** It had `/state/terrain`, `/state/areas`, `/commands/set-camera` and money in the summary. These were recovered by decompiling it and are in `mod/`.
- **Upkeep.** 1,358 km of road costs about 78,500 a week. A new city cannot pay that: play with the built-in Unlimited Money mod.
- **Zoning grids ran out** at the game limit of 49,152. Segments are built centre first, so the outskirts are the part without zoning.
- **`/state/road-anomalies` times out** on a network this size.
- 55 segments sit in open water (harbour piers) and were left out; 140 bridge and tunnel segments are flat.
- Buildings face `(-sin a, cos a)` for `angleDegrees = a`. Pipes and power lines only join at shared end points.
- Coordinates are world metres, origin at the map centre, +x east, +z north. `name` works, Danish letters included. The JSON reader in the bridge does not understand escapes, so names must not contain `"` or `\`.

## Goal: a real Aarhus simulator

Zones, plants, housing, buildings, landmarks and transport facilities should be as close to reality as the game allows. Where things stand, and the source to use for each:

| What | Source | State |
|---|---|---|
| Streets and names | OpenStreetMap | Main roads everywhere; small streets within 2.5 km of the centre and in Åbyhøj. Limited by the path finder to roughly 13,000-17,000 segments. |
| Zones and density | plandata.dk municipal plan frames | Done for the 9 owned tiles (`tools/zones.py`). |
| District names | OpenStreetMap places | 28 districts as circles. Real boundaries: plandata `distrikt`, or DAGI sogne/postnumre. |
| Rail | the map's own line, OpenStreetMap | Aarhus H placed and joined. Other stations not placed. |
| Letbanen | OpenStreetMap light rail | Metro stand-in, 12 stations (`tools/metro.py`). Outer stops and branches missing. |
| Power, water, sewage, waste | OpenStreetMap `power=plant`, `man_made=water_works/wastewater_plant`; Energistyrelsen's plant register for capacity | `tools/infrastructure.py` written; data not yet fetched (Overpass busy). Today the city runs on seeded wind turbines, water towers and shore outlets. Note: the real plants are mostly outside the map (Studstrupværket) or outside the owned tiles (Lisbjerg). |
| Harbour, bus station, ferry, airport | OpenStreetMap | Not started. The game has Harbor, Cargo Harbor, Ferry Harbor, Bus Station; the airport is outside the map. |
| Schools, hospitals, fire, police | OpenStreetMap `amenity=*` | Not started; today's service buildings are placed where complaints came from. |
| Landmarks | hand-picked list with coordinates | Cathedral placed (game model). ARoS, Rådhuset, Dokk1, Musikhuset, Den Gamle By, stadium: need custom assets or stand-ins. |
| Real building shapes | GeoDanmark/OSM footprints, Danish height model | Not started. Needs custom assets: either Steam Workshop items that already exist, or generated block models loaded by a mod. Open question which. |
| Bridges, tunnels, curves | OpenStreetMap `bridge`/`tunnel`/`layer` | Roads are still flat straight pieces; the mod can now build curves. |

## Architecture

- **In-game mod: Skylines Agent Bridge**, our fork in `mod/` (see `mod/README.md`), installed to `Addons\Mods\SkylinesAgentBridge`. HTTP/JSON API on `http://127.0.0.1:32123`. Upstream: `Sunwood-ai-labs/cities-skylines1-agent-skill` (MIT, reference in `docs/api.md`).
  - Read: `/health`, `/state/{summary,demand,areas,terrain,zones,growables,networks,facilities,problems,economy,chirps,saves,road-anomalies,building-anomalies,zone-anomalies,external-connections}`, `/prefabs/{roads,networks,buildings}`.
  - Write: `/commands/{build-network,build-road,bulldoze,set-zone,place-building,move-building,set-building-active,set-simulation-speed,set-camera,set-tax-rate,save,batch,repair-zones-to-growables,repair-zone-clusters,disable-blocked-assets}`.
  - `build-network` body: `{dryRun, roadPrefab, start{x,z}, end{x,z}, name}`. One straight ground-level segment; nearby nodes are reused.
  - `batch`: at most 32 commands, only `build-road` and `set-zone`, with `dryRun` and `stopOnError`.
- **Rust crate (`citybridge`)**: library plus CLI, game-agnostic outside the `api` module.
  1. `api`: serde types for the bridge's requests and replies, shared by client and mock.
  2. `client`: sync HTTP client (`ureq`) with timeouts and retries. Dry-run first, then live. Chunks work into batches of 32. Helper that waits for `/health`.
  3. `importer`: read `.osm.pbf`, filter highways, simplify graph, project lat/lon to game coordinates. Resample each way into straight pieces (about 24 to 96 m) and split at every junction. Map road types to prefab names actually returned by `/prefabs/roads`. Handle one-ways (segment ordered in travel direction) and lane counts. Carry OSM street names. Record bridges/tunnels in the plan even though v1 builds them at grade.
  4. `terrain`: convert elevation data to a 1081x1081 16-bit grayscale heightmap PNG for the map editor. Includes a check that compares `/state/terrain` samples with the source elevation to confirm the projection lines up.
  5. `runner`: experiment loop (baseline, apply change, rerun, write CSV). Blocked on the traffic endpoint.
- **Mock server** in Rust: small HTTP mock of the same routes, for tests without the game.

## Gaps in the bridge

| Need | Bridge today | Handling |
|---|---|---|
| Traffic stats for experiments | None | Add an endpoint in a fork of the mod |
| Bridges, tunnels, elevation | Ground level only | v1 builds at grade and records a warning; fork adds `elevation` to `build-network` |
| Curved roads | Straight segments only | Importer resamples into straight pieces |
| One-way direction | Prefab choice only | One-way prefab with start to end in travel direction; verify in game |
| Street names | `name` accepted on build | Verify it shows in game; otherwise fix in the fork |
| Clear roads | `bulldoze` by id | List `/state/networks`, bulldoze segments by id |
| Bulk build | 32 per batch | Chunk the plan, `stopOnError`, save between chunks |

## Outputs of the importer

1. `<city>.plan.json`: nodes (id, x, y, z in game metres), segments (node ids, CS1 road prefab, one-way, name, bridge/tunnel), metadata (scale, bbox, warnings).
2. `<city>.heightmap.png`: terrain for the map editor.
3. Live mode: post the plan to the bridge as batches of build commands.
4. Preview mode: render the plan as SVG before touching the game.

Flow: run importer, create map in editor from heightmap, load map, client builds plan in-game, then validate: `/state/road-anomalies` and `/state/external-connections` must come back clean, otherwise report what is wrong.

## City-agnostic design

Each city is a TOML config: name, center or bbox, scale, `max_tiles` (25 or 81), elevation source, region rules file (road classes, speed limits, driving side).
- OSM covers the world; only the extract differs (Geofabrik regional files).
- Elevation: Danish national data for Denmark (Dataforsyningen), Copernicus GLO-30 as the global default.
- Importer warns if a city does not fit the map.

## Size limits

- Vanilla CS1: 25 of 81 tiles, 5x5 block, ~9.6 km.
- With 81 Tiles 2 (installed): full 17.28 km. Large cities get heavy (pathfinding, simulation).
- Large cities: crop to an area or compress scale.

## Street names

OSM `name` tags go into the plan and are sent as `name` on each build command (to be confirmed in game). Unnamed OSM roads keep random names. No addresses/house numbers in CS1. Credit OpenStreetMap (ODbL) if sharing maps.

## Build order

1. `api`, `client`, HTTP mock. Smoke test against the live game: `/health`, `/state/summary`, `/prefabs/roads`, one dry-run road.
2. Importer on a small area (one junction, e.g. around Ringgaden, Aarhus). SVG preview, dry-run, then live build on a throwaway save, then anomaly check.
3. Scale up to central Aarhus in 32-command batches with periodic `/commands/save`.
4. Fork the bridge (started: `mod/` is thread-safe and lists whole cities). Still to add: traffic stats per segment, optional `elevation` on `build-network`, naming fix if needed. Build locally with `dotnet` against `Cities_Data\Managed`.
5. Experiment runner.
6. Heightmap tool for other cities (Aarhus heightmap maps already exist: `Aarhus Heightmap.crp`, `Aarhus Playable.crp`).

## Recommended mods (CS1)

Required: Skylines Agent Bridge. Recommended: TM:PE, Move It, Network Anarchy, Node Controller Renewal, Intersection Marking Tool, 81 Tiles 2, Skyve. Check each mod's Workshop status before relying on it.

## Caveats

- The bridge is experimental and mutates the live simulation. Work on throwaway saves, dry-run first, make small changes and re-read state after each.
- The bridge did not answer on `/health` while the game sat outside a loaded city, so the server probably starts only when a city is loaded. Not yet confirmed.
- CS1 traffic AI is unrealistic: treat experiment results as relative comparisons between junction designs, not predictions for the real city. Real traffic counts would be needed to calibrate.
- Start small (central Aarhus), get one full import-to-experiment loop working, then expand.

## Open questions

- How many small streets can come back before the path finder overflows again? 13,400 segments work; the edge has not been measured.
- Do newcomers use the train station at the Aarhus H site? It is placed and joined to the line; arrivals by rail are not yet confirmed.
- Letbanen runs as a metro stand-in (no tram pieces in this install): `tools/metro.py` built 12 stations from Aarhus H to Universitetshospitalet along the OpenStreetMap light-rail track and one line through them. Still to do: the stops further out (Lisbjerg, Lystrup, Odder and Grenaa branches).- Roads are still built as straight pieces. `build-network` now takes tangents, so the importer could build real curves with far fewer segments.
- `tools/add_streets.py` puts a neighbourhood's small streets back (Åbyhøj: 382 segments within 1100 m). Each addition needs the arrival routes re-checked with `/state/route`; the far south of the owned area is already out of reach from the north-west entrance.

## Decisions

- Traffic stats and elevation go into a fork of the bridge, not a separate companion mod. The bridge already has the game-thread queue and HTTP plumbing.
