//! HTTP client for the Skylines Agent Bridge mod.

use crate::plan::Plan;
use serde_json::{json, Value};
use std::collections::HashSet;
use std::io::Read;
use std::time::Duration;

/// The bridge refuses larger batches.
pub const BATCH: usize = 32;
/// The bridge refuses terrain requests with more samples per axis.
const TERRAIN_SAMPLES: usize = 120;

pub type Result<T> = std::result::Result<T, String>;

/// A road's two ends in centimetres, smaller end first, so that the same road
/// compares equal whichever way round it was built.
type RoadKey = [(i64, i64); 2];

fn road_key(a: [f64; 2], b: [f64; 2]) -> RoadKey {
    let cm = |p: [f64; 2]| ((p[0] * 100.0).round() as i64, (p[1] * 100.0).round() as i64);
    let (a, b) = (cm(a), cm(b));
    [a.min(b), a.max(b)]
}

pub struct Client {
    base: String,
    agent: ureq::Agent,
}

impl Client {
    pub fn new(base: &str) -> Self {
        // Commands run on the game thread and a large batch can take a while.
        let agent = ureq::AgentBuilder::new().timeout(Duration::from_secs(180)).build();
        Client { base: base.trim_end_matches('/').to_string(), agent }
    }

    /// Reads never change the game, so a failed read is tried again.
    pub fn get(&self, path: &str) -> Result<Value> {
        let url = format!("{}{}", self.base, path);
        let mut last = String::new();
        for attempt in 0..3 {
            if attempt > 0 {
                std::thread::sleep(Duration::from_secs(1));
            }
            match self.agent.get(&url).call() {
                Ok(r) | Err(ureq::Error::Status(_, r)) => return parse(path, r),
                Err(e) => last = unreachable(path, e),
            }
        }
        Err(last)
    }

    /// Commands are sent once: sending a build twice would build it twice.
    pub fn post(&self, path: &str, body: &Value) -> Result<Value> {
        let url = format!("{}{}", self.base, path);
        match self.agent.post(&url).set("Content-Type", "application/json").send_string(&body.to_string()) {
            Ok(r) | Err(ureq::Error::Status(_, r)) => parse(path, r),
            Err(e) => Err(unreachable(path, e)),
        }
    }

    /// Posts a command and turns `"ok": false` into an error.
    pub fn command(&self, path: &str, body: &Value) -> Result<Value> {
        let v = self.post(path, body)?;
        if v["ok"].as_bool() == Some(true) {
            Ok(v)
        } else {
            Err(format!("{path}: {}", v["error"].as_str().unwrap_or(&v.to_string())))
        }
    }

    /// Names of the road prefabs loaded in the game.
    pub fn road_prefabs(&self) -> Result<Vec<String>> {
        let v = self.get("/prefabs/roads")?;
        let roads = v["roads"].as_array().ok_or("/prefabs/roads: no roads array")?;
        Ok(roads.iter().filter_map(|r| r["name"].as_str().map(String::from)).collect())
    }

    /// Where the game has open water, sampled every `step` metres over +-half_extent.
    pub fn water(&self, half_extent: f64, step: f64) -> Result<Water> {
        // The bridge reads these numbers as whole metres and falls back to a
        // default area when one has a fraction, so the grid sits on whole steps.
        let half_extent = (half_extent / step).ceil() * step;
        let side = (2.0 * half_extent / step).ceil() as usize + 1;
        let mut cells = vec![false; side * side];
        let tile = TERRAIN_SAMPLES;
        for tz in (0..side).step_by(tile) {
            for tx in (0..side).step_by(tile) {
                let (nx, nz) = (tile.min(side - tx), tile.min(side - tz));
                let min_x = -half_extent + tx as f64 * step;
                let min_z = -half_extent + tz as f64 * step;
                let v = self.get(&format!(
                    "/state/terrain?minX={min_x}&maxX={}&minZ={min_z}&maxZ={}&step={step}",
                    min_x + (nx - 1) as f64 * step,
                    min_z + (nz - 1) as f64 * step
                ))?;
                let rows = v["rows"].as_array().ok_or_else(|| format!("/state/terrain: {v}"))?;
                // The bridge silently raises a step below 20 m; laying those rows
                // out on our grid would put the water in the wrong place.
                if v["step"].as_f64() != Some(step) || v["minX"].as_f64() != Some(min_x) || v["minZ"].as_f64() != Some(min_z) {
                    return Err(format!("/state/terrain: asked for {min_x}, {min_z} at a {step} m step, got {}, {} at {}", v["minX"], v["minZ"], v["step"]));
                }
                for (dz, row) in rows.iter().take(nz).enumerate() {
                    for (dx, c) in row.as_str().unwrap_or("").chars().take(nx).enumerate() {
                        cells[(tz + dz) * side + tx + dx] = c == '~';
                    }
                }
            }
        }
        Ok(Water { half_extent, step, side, cells })
    }

    /// Everything of one kind in the city: `key` names the array in the reply.
    /// The stock bridge stops at 5000 entries; a cut-off list is an error,
    /// because clearing or resuming from half a list goes wrong quietly.
    pub fn list(&self, path: &str, key: &str) -> Result<Vec<Value>> {
        let v = self.get(&format!("{path}{}limit=65536", if path.contains('?') { '&' } else { '?' }))?;
        let items = v[key].as_array().ok_or_else(|| format!("{path}: {v}"))?;
        if v["total"].as_u64() != Some(items.len() as u64) {
            return Err(format!("{path}: the bridge listed {} of {}. Install the bridge from mod/, which lists them all.", items.len(), v["total"]));
        }
        Ok(items.clone())
    }

    /// The roads already in the game.
    pub fn roads(&self) -> Result<HashSet<RoadKey>> {
        let point = |p: &Value| [p["x"].as_f64().unwrap_or(0.0), p["z"].as_f64().unwrap_or(0.0)];
        let segments = self.list("/state/networks?service=Road", "segments")?;
        Ok(segments.iter().map(|s| road_key(point(&s["start"]), point(&s["end"]))).collect())
    }

    /// Builds the plan's segments, leaving out those in `existing` so that an
    /// interrupted build can simply be run again. Returns one line per segment
    /// that was not built.
    pub fn build(&self, plan: &Plan, existing: &HashSet<RoadKey>, water: &Water, dry_run: bool) -> Result<Vec<String>> {
        let point = |n: [f64; 2]| json!({ "x": n[0], "z": n[1] });
        let mut problems = Vec::new();
        let mut commands = Vec::new();
        let mut indices = Vec::new();
        let (mut built, mut present) = (0usize, 0usize);
        let total = plan.segments.len();

        for (i, s) in plan.segments.iter().enumerate() {
            let (a, b) = (plan.nodes[s.a], plan.nodes[s.b]);
            let mid = [(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0];
            if existing.contains(&road_key(a, b)) {
                present += 1;
            } else if [a, mid, b].iter().any(|p| water.at(p[0], p[1])) {
                problems.push(format!("{i} {} ({}): in water, skipped", s.name, s.class));
            } else {
                // The bridge finds numbers with a regular expression that has no
                // exponent form; f64 values rounded to 0.01 never print with one.
                let mut c = json!({ "type": "build-road", "dryRun": dry_run, "roadPrefab": s.prefab, "start": point(a), "end": point(b) });
                if !s.name.is_empty() {
                    c["name"] = json!(s.name);
                }
                commands.push(c);
                indices.push(i);
            }

            if commands.len() == BATCH || (i + 1 == total && !commands.is_empty()) {
                let body = json!({ "dryRun": dry_run, "stopOnError": false, "commands": commands });
                // A batch that timed out may still run in the game later, so stop
                // rather than guess; the user checks and resumes.
                let stopped = |why: String| {
                    format!("{why}\nStopped at segment {}. Run the build again once the game responds; it skips what exists.", indices[0])
                };
                let reply = self.post("/commands/batch", &body).map_err(&stopped)?;
                let results = reply["results"].as_array().ok_or_else(|| stopped(format!("/commands/batch: {reply}")))?;
                for (position, index) in indices.iter().enumerate() {
                    // No answer for a command counts as not built.
                    let result = results.iter().find(|r| r["index"] == position).map(|r| &r["result"]);
                    if result.is_some_and(|r| r["ok"] == true) {
                        built += 1;
                    } else {
                        let s = &plan.segments[*index];
                        let why = result.and_then(|r| r["error"].as_str()).unwrap_or("no answer from the bridge");
                        problems.push(format!("{index} {} ({}): {why}", s.name, s.class));
                    }
                }
                commands.clear();
                indices.clear();
                if (i / BATCH).is_multiple_of(50) {
                    eprintln!("  {}/{} segments, {} built, {} not built", i + 1, total, built, problems.len());
                }
            }
        }
        eprintln!("  done: {built} built, {present} already there, {} not built", problems.len());
        Ok(problems)
    }
}

pub struct Water {
    half_extent: f64,
    step: f64,
    side: usize,
    cells: Vec<bool>,
}

impl Water {
    /// True when the nearest sample is water. Points off the map count as dry.
    pub fn at(&self, x: f64, z: f64) -> bool {
        let index = |v: f64| ((v + self.half_extent) / self.step).round();
        let (ix, iz) = (index(x), index(z));
        let max = (self.side - 1) as f64;
        (0.0..=max).contains(&ix) && (0.0..=max).contains(&iz) && self.cells[iz as usize * self.side + ix as usize]
    }
}

/// The bridge answers failed commands with an HTTP error status and the same
/// JSON shape, `{"ok": false, "error": ...}`, so every status is read alike.
fn parse(path: &str, response: ureq::Response) -> Result<Value> {
    // ureq's into_string stops at 10 MB; a network listing can be larger.
    let mut text = String::new();
    response.into_reader().read_to_string(&mut text).map_err(|e| format!("{path}: {e}"))?;
    serde_json::from_str(&text).map_err(|e| format!("{path}: reply is not JSON: {e}"))
}

fn unreachable(path: &str, e: ureq::Error) -> String {
    format!("{path}: {e}. Is the game running with a city loaded?")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plan::Segment;
    use std::io::{BufRead, BufReader, Write};
    use std::net::TcpListener;
    use std::sync::mpsc;

    /// A stand-in for the bridge: answers every request with `reply(path, body)`
    /// and reports what it received.
    fn fake_bridge(reply: fn(&str, &str) -> String) -> (String, mpsc::Receiver<(String, String)>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let base = format!("http://{}", listener.local_addr().unwrap());
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                let mut stream = stream.unwrap();
                let mut reader = BufReader::new(stream.try_clone().unwrap());
                let mut line = String::new();
                reader.read_line(&mut line).unwrap();
                let path = line.split(' ').nth(1).unwrap_or("").to_string();
                let mut length = 0;
                loop {
                    line.clear();
                    reader.read_line(&mut line).unwrap();
                    if let Some(v) = line.to_ascii_lowercase().strip_prefix("content-length:") {
                        length = v.trim().parse().unwrap();
                    }
                    if line.trim().is_empty() {
                        break;
                    }
                }
                let mut body = vec![0; length];
                reader.read_exact(&mut body).unwrap();
                let body = String::from_utf8(body).unwrap();
                let answer = reply(&path, &body);
                let _ = tx.send((path, body));
                write!(stream, "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", answer.len(), answer).unwrap();
            }
        });
        (base, rx)
    }

    fn dry() -> Water {
        Water { half_extent: 100.0, step: 100.0, side: 3, cells: vec![false; 9] }
    }

    fn plan(segments: usize) -> Plan {
        Plan {
            city: "Test".into(),
            attribution: String::new(),
            warnings: vec![],
            nodes: (0..=segments).map(|i| [i as f64 * 50.0, 0.25]).collect(),
            segments: (0..segments)
                .map(|i| Segment { a: i, b: i + 1, prefab: "Basic Road".into(), name: "Åboulevarden".into(), class: "residential".into(), structure: String::new() })
                .collect(),
        }
    }

    #[test]
    fn build_sends_batches_of_32_and_reports_failures() {
        let (base, seen) = fake_bridge(|_, body| {
            let n = serde_json::from_str::<Value>(body).unwrap()["commands"].as_array().unwrap().len();
            // the second command of every batch fails
            let results: Vec<Value> = (0..n)
                .map(|i| json!({ "index": i, "result": if i == 1 { json!({"ok": false, "error": "Road is too short."}) } else { json!({"ok": true}) } }))
                .collect();
            json!({ "ok": false, "results": results }).to_string()
        });
        let problems = Client::new(&base).build(&plan(40), &HashSet::new(), &dry(), false).unwrap();

        let batches: Vec<Value> = seen.try_iter().map(|(_, body)| serde_json::from_str(&body).unwrap()).collect();
        let sizes: Vec<usize> = batches.iter().map(|b| b["commands"].as_array().unwrap().len()).collect();
        assert_eq!(sizes, [32, 8]);
        let first = &batches[0]["commands"][0];
        assert_eq!(first["dryRun"], false);
        assert_eq!(first["name"], "Åboulevarden");
        assert_eq!(first["end"], json!({ "x": 50.0, "z": 0.25 }));
        assert_eq!(problems, ["1 Åboulevarden (residential): Road is too short.", "33 Åboulevarden (residential): Road is too short."]);
    }

    #[test]
    fn build_skips_water_and_roads_already_there() {
        let (base, seen) = fake_bridge(|_, body| {
            let n = serde_json::from_str::<Value>(body).unwrap()["commands"].as_array().unwrap().len();
            let results: Vec<Value> = (0..n).map(|i| json!({ "index": i, "result": { "ok": true } })).collect();
            json!({ "ok": true, "results": results }).to_string()
        });
        // water at x = 100, which is the end of segment 1 and the start of segment 2
        let mut water = dry();
        water.cells[3 + 2] = true;
        // segment 0 exists in the game, built the other way round
        let existing = HashSet::from([road_key([50.0, 0.25], [0.0, 0.25])]);
        let problems = Client::new(&base).build(&plan(4), &existing, &water, true).unwrap();

        let (_, body) = seen.try_iter().next().unwrap();
        let body: Value = serde_json::from_str(&body).unwrap();
        assert_eq!(body["commands"].as_array().unwrap().len(), 1, "only segment 3 is sent");
        assert_eq!(body["commands"][0]["start"]["x"], 150.0);
        assert_eq!(body["dryRun"], true);
        assert_eq!(problems.len(), 2);
        assert!(problems[0].starts_with("1 ") && problems[0].ends_with("in water, skipped"));
    }

    #[test]
    fn water_grid_is_stitched_from_tiles() {
        let (base, seen) = fake_bridge(|path, _| {
            // water wherever x >= 0: the tile starting at minX=-1000 is dry
            let number = |name: &str| -> f64 {
                let rest = path.split(&format!("{name}=")).nth(1).unwrap();
                rest.split('&').next().unwrap().parse().unwrap()
            };
            let dry = number("minX") == -1000.0;
            let row = if dry { "a".repeat(120) } else { "~".repeat(120) };
            json!({ "ok": true, "step": 10, "minX": number("minX"), "minZ": number("minZ"), "rows": vec![row; 120] }).to_string()
        });
        let water = Client::new(&base).water(1000.0, 10.0).unwrap();
        assert_eq!(seen.try_iter().count(), 4, "201 samples per axis need 2 x 2 tiles");
        assert!(!water.at(-500.0, 0.0));
        assert!(water.at(204.0, -900.0));
        assert!(water.at(1000.0, 1000.0));
        assert!(!water.at(5000.0, 0.0), "off the map is dry");
    }

    #[test]
    fn water_refuses_a_grid_the_bridge_did_not_use() {
        // the real bridge answers a 16 m request with 20 m rows, and a request
        // it cannot parse with its default area at x = -2880
        let (base, _seen) = fake_bridge(|_, _| json!({ "ok": true, "step": 20, "minX": -2880, "minZ": -960, "rows": ["~~"] }).to_string());
        let err = Client::new(&base).water(96.0, 16.0).err().unwrap();
        assert!(err.contains("asked for -96, -96 at a 16 m step, got -2880, -960 at 20"), "{err}");
    }

    #[test]
    fn water_grid_sits_on_whole_metres() {
        let (base, seen) = fake_bridge(|_, _| json!({ "ok": true, "step": 20, "minX": -8600, "minZ": -8600, "rows": ["a"] }).to_string());
        // 8599.97 is what a real plan's outermost node looks like
        let _ = Client::new(&base).water(8599.97, 20.0);
        let (path, _) = seen.recv().unwrap();
        assert!(path.starts_with("/state/terrain?minX=-8600&maxX=-6220&minZ=-8600&maxZ=-6220&step=20"), "{path}");
    }

    #[test]
    fn a_cut_off_listing_is_an_error() {
        let (base, _seen) = fake_bridge(|_, _| json!({ "ok": true, "total": 3, "segments": [{ "id": 1 }, { "id": 2 }] }).to_string());
        let err = Client::new(&base).list("/state/networks?service=Road", "segments").unwrap_err();
        assert!(err.contains("listed 2 of 3"), "{err}");
    }

    #[test]
    fn command_turns_ok_false_into_an_error() {
        let (base, _seen) = fake_bridge(|_, _| r#"{"ok":false,"error":"id is required."}"#.to_string());
        let err = Client::new(&base).command("/commands/bulldoze", &json!({})).unwrap_err();
        assert_eq!(err, "/commands/bulldoze: id is required.");
    }
}
