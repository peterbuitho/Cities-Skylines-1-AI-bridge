# Skylines Agent Bridge (our build)

The in-game half of citybridge: a Cities: Skylines 1 mod that serves an HTTP/JSON API on `http://127.0.0.1:32123`.

This is a fork of [Sunwood-ai-labs/cities-skylines1-agent-skill](https://github.com/Sunwood-ai-labs/cities-skylines1-agent-skill) (MIT, see `LICENSE`), taken from its `main` branch at commit `70a5116`. The API reference is upstream's `docs/api.md`.

## What differs from upstream

- **Commands that change the city run on the simulation thread.** Upstream runs everything on the main thread, which races with the simulation and raises "Array index is out of range" and "HashSet have been modified" simulation errors under bulk work. Build, bulldoze, zone, place, move, activate and batch now go through `SimulationManager.AddAction`, which the game also runs while paused. Reads, save, camera, speed and tax stay on the main thread. See `CommandQueue.RunOnSimulationThread` and `ApiServer.Run`.
- **Listings hold a whole city.** `/state/networks`, `/state/facilities` and `/state/growables` return up to 65536 entries instead of 5000.
- **Diagnostics.** `GET /state/move-in` lists outside connections, homes and who is moving in, and probes a route from each road entrance to a house. `GET /state/route?fx&fz&tx&tz&drive&max` runs one route search between two points and reports earlier ones (`fz=-1` or `tz=-1`: the x value is a segment id). Both exist because the game drops newcomers silently when its path finder overflows.
- **Rail joins rail.** `build-network` reuses a nearby node of the same rail kind, so new track can meet a station's own track. Upstream only joins roads.
- **Curved segments.** `build-network` takes optional `startDirection{x,z}` and `endDirection{x,z}` tangents. Without them a segment is straight, and trains refuse the kink between two straight pieces (`PathFind` checks the prefab's maximum turn angle for everything that is not a car).
- **Transport lines.** `POST /commands/create-line {"transport":"Metro","segments":"12,34,56"}` creates a line through station track segments in travel order, out and back, and closes it. `GET /state/lines` lists lines with vehicles, passengers and, per stop, whether the leg to the next stop found a route.
- **Three routes and two summary fields** that the previously installed DLL had and upstream lacks, recovered by decompiling that DLL: `GET /state/areas`, `GET /state/terrain`, `POST /commands/set-camera`, and `population` and `money` in `/state/summary`.

## Build and install

```powershell
.\mod\build.ps1            # builds mod\bin\SkylinesAgentBridge.dll
.\mod\build.ps1 -Install   # also copies it into the game's Mods folder; game must be closed
```

The first install keeps the DLL it replaces as `SkylinesAgentBridge.dll.bak` in the same folder. To go back, close the game and rename it over the new one.
