mod client;
mod geo;
mod osm;
mod plan;

use client::{Client, Result};
use serde_json::{json, Value};
use std::fs;

const USAGE: &str = "\
citybridge: put real street networks into Cities: Skylines through the Skylines Agent Bridge mod

  citybridge import <overpass.json> <city.toml> [out-dir]   write <city>.plan.json and <city>.svg
  citybridge smoke                                          check the bridge answers and can validate a road
  citybridge clear --yes                                    bulldoze the loaded city, keep the map's highways and rail
  citybridge build <plan.json> [--dry-run]                  build the plan in the loaded city; safe to run again
  citybridge check                                          report road problems and outside connections
  citybridge save <name>                                    save the loaded city
  citybridge speed <0-3>                                    0 pauses the simulation

The bridge is expected at http://127.0.0.1:32123; set CITYBRIDGE_URL to change it.";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let args: Vec<&str> = args.iter().map(String::as_str).collect();
    if let Err(e) = run(&args) {
        eprintln!("error: {e}");
        std::process::exit(1);
    }
}

fn run(args: &[&str]) -> Result<()> {
    let url = std::env::var("CITYBRIDGE_URL").unwrap_or_else(|_| "http://127.0.0.1:32123".to_string());
    let bridge = Client::new(&url);
    match args {
        ["import", osm, city] => import(osm, city, "out"),
        ["import", osm, city, out] => import(osm, city, out),
        ["smoke"] => smoke(&bridge),
        ["clear", "--yes"] => clear(&bridge),
        ["build", plan] => build(&bridge, plan, false),
        ["build", plan, "--dry-run"] => build(&bridge, plan, true),
        ["check"] => check(&bridge),
        ["save", name] => save(&bridge, name),
        ["speed", n] => {
            let speed: u8 = n.parse().ok().filter(|n| *n <= 3).ok_or("speed must be 0, 1, 2 or 3")?;
            let body = if speed == 0 { json!({ "paused": true }) } else { json!({ "paused": false, "speed": speed }) };
            bridge.command("/commands/set-simulation-speed", &body).map(|_| ())
        }
        _ => Err(USAGE.to_string()),
    }
}

fn read(path: &str) -> Result<String> {
    fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))
}

fn write(path: &str, text: &str) -> Result<()> {
    fs::write(path, text).map_err(|e| format!("{path}: {e}"))
}

fn import(osm_path: &str, city_path: &str, out: &str) -> Result<()> {
    let city: plan::City = toml::from_str(&read(city_path)?).map_err(|e| format!("{city_path}: {e}"))?;
    let osm: osm::Osm = serde_json::from_str(&read(osm_path)?).map_err(|e| format!("{osm_path}: {e}"))?;
    let plan = plan::build(&osm, &city);

    fs::create_dir_all(out).map_err(|e| format!("{out}: {e}"))?;
    let stem = format!("{out}/{}", city.name.to_lowercase());
    write(&format!("{stem}.plan.json"), &serde_json::to_string(&plan).map_err(|e| e.to_string())?)?;
    write(&format!("{stem}.svg"), &plan::svg(&plan, city.half_extent))?;

    println!("{}: {} segments, {} nodes -> {stem}.plan.json, {stem}.svg", city.name, plan.segments.len(), plan.nodes.len());
    let named = plan.segments.iter().filter(|s| !s.name.is_empty()).count();
    println!("{named} segments carry a street name");
    for w in &plan.warnings {
        println!("warning: {w}");
    }
    Ok(())
}

fn smoke(bridge: &Client) -> Result<()> {
    let health = bridge.get("/health")?;
    println!("health: {health}");
    if health["levelLoaded"].as_bool() != Some(true) {
        return Err("no city is loaded".to_string());
    }
    let summary = bridge.get("/state/summary")?;
    println!("network: {}  paused: {}", summary["network"], summary["simulation"]["paused"]);
    println!("road prefabs loaded: {}", bridge.road_prefabs()?.len());
    let reply = bridge.command(
        "/commands/build-network",
        &json!({ "dryRun": true, "roadPrefab": "Basic Road", "start": { "x": 0, "z": 0 }, "end": { "x": 80, "z": 0 } }),
    )?;
    println!("dry-run road: {reply}");
    Ok(())
}

fn ids(list: &[Value], keep: impl Fn(&Value) -> bool) -> Vec<u64> {
    list.iter().filter(|v| keep(v)).filter_map(|v| v["id"].as_u64()).collect()
}

fn clear(bridge: &Client) -> Result<()> {
    let bulldoze = |kind: &str, ids: Vec<u64>| -> Result<()> {
        let mut failed = 0;
        for id in &ids {
            // An entity can vanish on its own when its road goes, so one failure is not fatal.
            failed += usize::from(bridge.command("/commands/bulldoze", &json!({ "entityType": kind, "id": id })).is_err());
        }
        println!("bulldozed {} {kind}s ({failed} already gone or refused)", ids.len() - failed);
        Ok(())
    };

    let growables = bridge.list("/state/growables", "growables")?;
    let facilities = bridge.list("/state/facilities", "facilities")?;
    // Untouchable buildings belong to a network (power poles, for one) and go with it.
    let touchable = |v: &Value| !v["flags"].as_str().unwrap_or("").contains("Untouchable");
    let mut buildings = ids(&growables, |_| true);
    buildings.extend(ids(&facilities, touchable));
    bulldoze("building", buildings)?;

    let networks = bridge.list("/state/networks", "segments")?;
    bulldoze("netSegment", ids(&networks, city_built))
}

/// Highways and rail come with the map and carry its outside connections;
/// everything else was built in the city and goes when it is cleared.
fn city_built(segment: &Value) -> bool {
    let prefab = segment["prefab"].as_str().unwrap_or("");
    segment["service"] != "PublicTransport" && !prefab.contains("Highway")
}

fn build(bridge: &Client, plan_path: &str, dry_run: bool) -> Result<()> {
    let plan: plan::Plan = serde_json::from_str(&read(plan_path)?).map_err(|e| format!("{plan_path}: {e}"))?;

    let loaded = bridge.road_prefabs()?;
    let mut missing: Vec<&str> = plan.segments.iter().map(|s| s.prefab.as_str()).filter(|p| !loaded.iter().any(|l| l == p)).collect();
    missing.sort();
    missing.dedup();
    if !missing.is_empty() {
        return Err(format!("the game has no road prefab named: {}", missing.join(", ")));
    }

    let half_extent = plan.nodes.iter().flatten().fold(0.0f64, |m, v| m.max(v.abs()));
    eprintln!("reading the water map");
    // 20 m is the finest grid the bridge samples.
    let water = bridge.water(half_extent, 20.0)?;
    eprintln!("{} {} segments", if dry_run { "validating" } else { "building" }, plan.segments.len());
    let problems = bridge.build(&plan, &bridge.roads()?, &water, dry_run)?;

    let log = format!("{plan_path}.problems.txt");
    write(&log, &problems.join("\n"))?;
    println!("{} segments not built, listed in {log}", problems.len());
    Ok(())
}

fn check(bridge: &Client) -> Result<()> {
    let summary = bridge.get("/state/summary")?;
    println!("network: {}", summary["network"]);
    // The bridge compares every road with every other; on a whole city it gives up.
    match bridge.get("/state/road-anomalies?limit=1")? {
        v if v["ok"] == true => println!("road problems: {} {}", v["total"], v["counts"]),
        v => println!("road problems: not available ({})", v["error"].as_str().unwrap_or("no answer")),
    }
    let outside = bridge.get("/state/external-connections?limit=10")?;
    println!(
        "road networks: {}, city connected to outside: {}, cut-off local networks: {}",
        outside["roadComponents"], outside["cityConnectedToOutside"], outside["disconnectedLocalRoadComponents"]
    );
    Ok(())
}

fn save(bridge: &Client, name: &str) -> Result<()> {
    let written = |bridge: &Client| -> Result<Option<Value>> {
        let saves = bridge.get("/state/saves")?;
        Ok(saves["saves"].as_array().into_iter().flatten().find(|s| s["name"] == name).cloned())
    };
    // An older save with this name may exist; only a new write time proves this save.
    let before = written(bridge)?.map(|s| s["lastWriteTimeUtc"].clone());
    bridge.command("/commands/save", &json!({ "name": name }))?;
    // Saving runs in the background.
    for _ in 0..90 {
        std::thread::sleep(std::time::Duration::from_secs(2));
        if let Some(s) = written(bridge)?.filter(|s| Some(&s["lastWriteTimeUtc"]) != before.as_ref()) {
            println!("saved {} ({} bytes, {})", s["path"], s["length"], s["lastWriteTimeUtc"]);
            return Ok(());
        }
    }
    Err(format!("save '{name}' was not written within three minutes"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clear_keeps_the_maps_highways_and_rail() {
        let built = |service: &str, prefab: &str| city_built(&json!({ "service": service, "prefab": prefab }));
        assert!(built("Road", "Basic Road"));
        assert!(built("Water", "Water Pipe"));
        assert!(built("Electricity", "Power Line"));
        assert!(!built("Road", "Two Lane Highway Elevated"));
        assert!(!built("Road", "HighwayRamp"));
        assert!(!built("PublicTransport", "Train Track"));
    }
}
