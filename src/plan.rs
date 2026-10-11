//! Turn OSM ways into a build plan: straight road segments in game metres.

use crate::geo::Georef;
use crate::osm::{Element, Osm};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fmt::Write;

type Pt = (f64, f64);

/// One city's settings, read from `cities/<name>.toml`.
#[derive(Debug, Deserialize)]
pub struct City {
    pub name: String,
    #[serde(flatten)]
    pub georef: Georef,
    /// Roads are kept inside +-half_extent metres. 8640 is the edge of an 81-tile map.
    #[serde(default = "default_half_extent")]
    pub half_extent: f64,
    /// CS1 holds 36864 segments and 32768 nodes in total, the map's own included.
    #[serde(default = "default_max_segments")]
    pub max_segments: usize,
}

fn default_half_extent() -> f64 {
    8600.0
}

fn default_max_segments() -> usize {
    30000
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Plan {
    pub city: String,
    pub attribution: String,
    pub warnings: Vec<String>,
    /// [x, z] in game metres.
    pub nodes: Vec<[f64; 2]>,
    pub segments: Vec<Segment>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Segment {
    pub a: usize,
    pub b: usize,
    pub prefab: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub name: String,
    pub class: String,
    /// "bridge" or "tunnel" in OSM. The bridge mod builds these at ground level.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub structure: String,
}

/// Road classes we import, most important first.
const CLASSES: [&str; 13] = [
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
];
/// Classes from this rank on are dropped first when the plan is over budget.
const FIRST_MINOR_RANK: usize = 10;

/// Pieces shorter than this are folded into one junction.
const MIN_PIECE: f64 = 6.0;
/// Bend points closer together than this are dropped.
const MIN_SEGMENT: f64 = 12.0;
/// The game's own road tool does not make segments much longer than this.
const MAX_SEGMENT: f64 = 96.0;
/// Bend points that move the road less than this are dropped.
const SIMPLIFY_TOLERANCE: f64 = 1.5;

fn rank(class: &str) -> Option<usize> {
    CLASSES.iter().position(|c| *c == class)
}

fn prefab(class: &str, oneway: bool, lanes: u32) -> &'static str {
    match (class, oneway) {
        ("motorway", true) => "Highway",
        ("motorway_link" | "trunk_link", true) => "HighwayRamp",
        (_, true) => "Oneway Road",
        (_, false) if lanes >= 4 => "Medium Road",
        (_, false) => "Basic Road",
    }
}

struct Way {
    rank: usize,
    prefab: &'static str,
    name: String,
    structure: &'static str,
}

struct Piece {
    way: usize,
    from: i64,
    to: i64,
    pts: Vec<Pt>,
}

pub fn build(osm: &Osm, city: &City) -> Plan {
    let mut pos: HashMap<i64, Pt> = HashMap::new();
    for e in &osm.elements {
        if let Element::Node { id, lat, lon } = e {
            pos.insert(*id, city.georef.project(*lat, *lon));
        }
    }

    // Read the ways and count how many times each node is used: a node used
    // twice is a junction.
    let mut ways = Vec::new();
    let mut way_nodes: Vec<Vec<i64>> = Vec::new();
    let mut usage: HashMap<i64, u32> = HashMap::new();
    for e in &osm.elements {
        let Element::Way { nodes, tags } = e else { continue };
        let tag = |k: &str| tags.get(k).map(String::as_str).unwrap_or("");
        let Some(rank) = rank(tag("highway")) else { continue };
        if tag("area") == "yes" {
            continue;
        }
        let mut ids: Vec<i64> = nodes.iter().copied().filter(|id| pos.contains_key(id)).collect();
        if ids.len() < 2 {
            continue;
        }
        let roundabout = matches!(tag("junction"), "roundabout" | "circular");
        let oneway = match tag("oneway") {
            "yes" | "true" | "1" => true,
            "-1" | "reverse" => {
                ids.reverse();
                true
            }
            "no" | "false" | "0" => false,
            _ => roundabout || CLASSES[rank] == "motorway",
        };
        let lanes = tag("lanes").parse().unwrap_or(0);
        let name = if tag("name").is_empty() { tag("ref") } else { tag("name") };
        for id in &ids {
            *usage.entry(*id).or_default() += 1;
        }
        ways.push(Way {
            rank,
            prefab: prefab(CLASSES[rank], oneway, lanes),
            name: clean_name(name),
            structure: match () {
                _ if !matches!(tag("bridge"), "" | "no") => "bridge",
                _ if !matches!(tag("tunnel"), "" | "no") => "tunnel",
                _ => "",
            },
        });
        way_nodes.push(ids);
    }

    // Cut every way at its junctions.
    let mut pieces = Vec::new();
    for (way, ids) in way_nodes.iter().enumerate() {
        let mut start = 0;
        for i in 1..ids.len() {
            if i == ids.len() - 1 || usage[&ids[i]] > 1 {
                pieces.push(Piece {
                    way,
                    from: ids[start],
                    to: ids[i],
                    pts: ids[start..=i].iter().map(|id| pos[id]).collect(),
                });
                start = i;
            }
        }
    }

    // Fold very short pieces into one junction. The bridge mod refuses roads
    // under 4 m and joins nodes within 2 m anyway.
    let mut merged: HashMap<i64, i64> = HashMap::new();
    for p in &pieces {
        let (a, b) = (find(&merged, p.from), find(&merged, p.to));
        if a != b && length(&p.pts) < MIN_PIECE {
            merged.insert(b, a);
        }
    }

    let inside = |p: Pt| p.0.abs() <= city.half_extent && p.1.abs() <= city.half_extent;
    let mut nodes: Vec<[f64; 2]> = Vec::new();
    let mut junction_index: HashMap<i64, usize> = HashMap::new();
    let mut seen: HashSet<(usize, usize)> = HashSet::new();
    let mut segments = Vec::new();
    let mut outside = 0usize;
    for p in &pieces {
        let (a, b) = (find(&merged, p.from), find(&merged, p.to));
        let mut pts = p.pts.clone();
        pts[0] = pos[&a];
        *pts.last_mut().unwrap() = pos[&b];
        let pts = shape(&pts);
        if a == b && pts.len() < 4 {
            continue; // folded away, or a loop too small to draw
        }

        let last = pts.len() - 1;
        let mut prev: Option<usize> = None;
        for (i, pt) in pts.iter().enumerate() {
            if !inside(*pt) {
                outside += usize::from(i > 0);
                prev = None;
                continue;
            }
            let mut add = |pt: &Pt| {
                nodes.push([round2(pt.0), round2(pt.1)]);
                nodes.len() - 1
            };
            let index = match i {
                0 => *junction_index.entry(a).or_insert_with(|| add(pt)),
                i if i == last => *junction_index.entry(b).or_insert_with(|| add(pt)),
                _ => add(pt),
            };
            if let Some(prev) = prev {
                if prev != index && seen.insert((prev.min(index), prev.max(index))) {
                    let way = &ways[p.way];
                    segments.push(Segment {
                        a: prev,
                        b: index,
                        prefab: way.prefab.to_string(),
                        name: way.name.clone(),
                        class: CLASSES[way.rank].to_string(),
                        structure: way.structure.to_string(),
                    });
                }
            }
            prev = Some(index);
        }
    }

    let mut warnings = Vec::new();
    if outside > 0 {
        warnings.push(format!("{outside} segments fall outside the map and were left out."));
    }

    // Over budget: drop minor streets, farthest from the map centre first.
    if segments.len() > city.max_segments {
        let excess = segments.len() - city.max_segments;
        let dist2 = |s: &Segment| {
            let (a, b) = (nodes[s.a], nodes[s.b]);
            (a[0] + b[0]).powi(2) + (a[1] + b[1]).powi(2)
        };
        let mut minor: Vec<usize> = (0..segments.len())
            .filter(|i| rank(&segments[*i].class).unwrap() >= FIRST_MINOR_RANK)
            .collect();
        minor.sort_by(|x, y| dist2(&segments[*y]).total_cmp(&dist2(&segments[*x])));
        let drop: HashSet<usize> = minor.into_iter().take(excess).collect();
        warnings.push(format!(
            "{} minor-street segments farthest from the centre were left out to stay under {} segments.",
            drop.len(),
            city.max_segments
        ));
        let mut i = 0;
        segments.retain(|_| {
            i += 1;
            !drop.contains(&(i - 1))
        });
    }

    for kind in ["bridge", "tunnel"] {
        let n = segments.iter().filter(|s| s.structure == kind).count();
        if n > 0 {
            warnings.push(format!("{n} {kind} segments will be built at ground level."));
        }
    }

    // Main roads first and the centre before the outskirts, so that is what
    // exists if the game runs out of room. Zoning grids run out first: the
    // game holds 49152 of them, about two per segment.
    let centre_dist = |s: &Segment| nodes[s.a][0].hypot(nodes[s.a][1]);
    segments.sort_by(|x, y| rank(&x.class).cmp(&rank(&y.class)).then(centre_dist(x).total_cmp(&centre_dist(y))));

    // Drop nodes that no segment uses any more.
    let mut remap: HashMap<usize, usize> = HashMap::new();
    let mut used = Vec::new();
    for s in &mut segments {
        for end in [&mut s.a, &mut s.b] {
            *end = *remap.entry(*end).or_insert_with(|| {
                used.push(nodes[*end]);
                used.len() - 1
            });
        }
    }

    Plan {
        city: city.name.clone(),
        attribution: "Map data (c) OpenStreetMap contributors, ODbL".to_string(),
        warnings,
        nodes: used,
        segments,
    }
}

fn find(merged: &HashMap<i64, i64>, mut id: i64) -> i64 {
    while let Some(parent) = merged.get(&id) {
        id = *parent;
    }
    id
}

fn round2(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

fn dist(a: Pt, b: Pt) -> f64 {
    (a.0 - b.0).hypot(a.1 - b.1)
}

fn length(pts: &[Pt]) -> f64 {
    pts.windows(2).map(|w| dist(w[0], w[1])).sum()
}

/// The bridge mod reads JSON with regular expressions and does not understand
/// escapes, so a name must not contain quotes or backslashes.
fn clean_name(name: &str) -> String {
    name.chars().filter(|c| !c.is_control() && !matches!(c, '"' | '\\')).collect()
}

/// Reduce a polyline to straight pieces of a sensible length. Keeps both ends.
fn shape(pts: &[Pt]) -> Vec<Pt> {
    let mut keep = vec![false; pts.len()];
    keep[0] = true;
    keep[pts.len() - 1] = true;
    simplify(pts, 0, pts.len() - 1, &mut keep);

    let end = pts[pts.len() - 1];
    let mut thinned = vec![pts[0]];
    for i in 1..pts.len() - 1 {
        if keep[i] && dist(*thinned.last().unwrap(), pts[i]) >= MIN_SEGMENT && dist(pts[i], end) >= MIN_SEGMENT {
            thinned.push(pts[i]);
        }
    }
    thinned.push(end);

    let mut out = vec![thinned[0]];
    for w in thinned.windows(2) {
        let parts = (dist(w[0], w[1]) / MAX_SEGMENT).ceil().max(1.0) as usize;
        for k in 1..=parts {
            let t = k as f64 / parts as f64;
            out.push((w[0].0 + (w[1].0 - w[0].0) * t, w[0].1 + (w[1].1 - w[0].1) * t));
        }
    }
    out
}

/// Douglas-Peucker: mark the points that matter between `first` and `last`.
fn simplify(pts: &[Pt], first: usize, last: usize, keep: &mut [bool]) {
    let (a, b) = (pts[first], pts[last]);
    let len = dist(a, b);
    let mut worst = (0.0, first);
    for (i, &p) in pts.iter().enumerate().take(last).skip(first + 1) {
        let d = if len < 1e-9 {
            dist(a, p)
        } else {
            ((b.0 - a.0) * (a.1 - p.1) - (a.0 - p.0) * (b.1 - a.1)).abs() / len
        };
        if d > worst.0 {
            worst = (d, i);
        }
    }
    if worst.0 > SIMPLIFY_TOLERANCE {
        keep[worst.1] = true;
        simplify(pts, first, worst.1, keep);
        simplify(pts, worst.1, last, keep);
    }
}

/// A picture of the plan, to check it by eye before touching the game.
pub fn svg(plan: &Plan, half_extent: f64) -> String {
    let e = half_extent;
    let mut out = format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"{} {} {} {}\" fill=\"none\" stroke-linecap=\"round\">\n\
         <rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"#f4f1ea\"/>\n",
        -e, -e, 2.0 * e, 2.0 * e, -e, -e, 2.0 * e, 2.0 * e
    );
    let styles = [("#888", 6.0), ("#d08a00", 12.0), ("#c0392b", 18.0)];
    for (level, (colour, width)) in styles.iter().enumerate() {
        let mut d = String::new();
        for s in &plan.segments {
            let r = rank(&s.class).unwrap_or(FIRST_MINOR_RANK);
            let l = if r < 4 { 2 } else if r < FIRST_MINOR_RANK { 1 } else { 0 };
            if l == level {
                let (a, b) = (plan.nodes[s.a], plan.nodes[s.b]);
                // SVG y grows downwards, game z grows northwards
                let _ = write!(d, "M{} {}L{} {}", a[0], -a[1], b[0], -b[1]);
            }
        }
        let _ = writeln!(out, "<path stroke=\"{colour}\" stroke-width=\"{width}\" d=\"{d}\"/>");
    }
    out.push_str("</svg>\n");
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn city() -> City {
        toml::from_str("name = \"Test\"\ncenter_lat = 56.0\ncenter_lon = 10.0").unwrap()
    }

    /// Nodes on a 100 m grid around the centre: id = 100 + 10*row + col.
    fn osm(ways: &str) -> Osm {
        let mut elements = Vec::new();
        for row in 0..4 {
            for col in 0..4 {
                elements.push(format!(
                    r#"{{"type":"node","id":{},"lat":{},"lon":{}}}"#,
                    100 + 10 * row + col,
                    56.0 + row as f64 * 0.000898,
                    10.0 + col as f64 * 0.001605
                ));
            }
        }
        let json = format!(r#"{{"elements":[{},{}]}}"#, elements.join(","), ways);
        serde_json::from_str(&json).unwrap()
    }

    fn ends(plan: &Plan, s: &Segment) -> ([f64; 2], [f64; 2]) {
        (plan.nodes[s.a], plan.nodes[s.b])
    }

    #[test]
    fn crossing_ways_share_one_node_and_are_cut_there() {
        let plan = build(
            &osm(
                r#"{"type":"way","id":1,"nodes":[110,111,112],"tags":{"highway":"residential","name":"Øst\"gade"}},
                   {"type":"way","id":2,"nodes":[101,111,121],"tags":{"highway":"primary"}}"#,
            ),
            &city(),
        );
        // each way is ~200 m and is cut in two at node 111, 100 m pieces split again
        assert_eq!(plan.segments.len(), 8);
        assert_eq!(plan.nodes.len(), 9);
        assert_eq!(plan.segments[0].class, "primary", "main roads come first");
        let residential = plan.segments.iter().find(|s| s.class == "residential").unwrap();
        assert_eq!(residential.name, "Østgade", "quotes are removed, Danish letters stay");
        assert_eq!(residential.prefab, "Basic Road");
    }

    #[test]
    fn reverse_oneway_is_built_in_travel_direction() {
        let plan = build(
            &osm(r#"{"type":"way","id":1,"nodes":[100,101],"tags":{"highway":"tertiary","oneway":"-1"}}"#),
            &city(),
        );
        assert!(plan.segments.iter().all(|s| s.prefab == "Oneway Road"));
        assert_eq!(plan.segments.len(), 2);
        for s in &plan.segments {
            let (a, b) = ends(&plan, s);
            assert!(a[0] > b[0], "runs west, from node 101 back to node 100");
        }
    }

    #[test]
    fn roads_outside_the_map_are_left_out() {
        let mut c = city();
        c.half_extent = 160.0;
        let plan = build(
            &osm(r#"{"type":"way","id":1,"nodes":[100,101,102,103],"tags":{"highway":"residential"}}"#),
            &c,
        );
        // the 300 m street becomes four 75 m segments; the last two cross the edge
        assert!(plan.nodes.iter().all(|n| n[0] <= 160.0));
        assert_eq!(plan.segments.len(), 2);
        assert!(plan.warnings[0].contains("outside the map"));
    }

    #[test]
    fn over_budget_drops_far_minor_streets_and_keeps_main_roads() {
        let mut c = city();
        c.max_segments = 3;
        let plan = build(
            &osm(
                r#"{"type":"way","id":1,"nodes":[130,131],"tags":{"highway":"motorway"}},
                   {"type":"way","id":2,"nodes":[100,101],"tags":{"highway":"residential"}},
                   {"type":"way","id":3,"nodes":[122,123],"tags":{"highway":"residential"}}"#,
            ),
            &c,
        );
        assert_eq!(plan.segments.len(), 3);
        assert_eq!(plan.segments.iter().filter(|s| s.class == "motorway").count(), 2);
        let kept = plan.segments.iter().find(|s| s.class == "residential").unwrap();
        assert!(ends(&plan, kept).0[1] < 50.0, "the street near the centre survives");
        assert_eq!(plan.nodes.len(), 5, "unused nodes are removed");
    }

    #[test]
    fn shape_keeps_ends_and_respects_segment_lengths() {
        let pts = [(0.0, 0.0), (3.0, 0.2), (150.0, 0.0), (150.0, 5.0), (150.0, 200.0)];
        let out = shape(&pts);
        assert_eq!(out[0], pts[0]);
        assert_eq!(*out.last().unwrap(), pts[4]);
        for w in out.windows(2) {
            let d = dist(w[0], w[1]);
            assert!((MIN_SEGMENT..=MAX_SEGMENT + 1e-9).contains(&d), "segment of {d} m");
        }
    }

    #[test]
    fn tiny_link_between_two_junctions_folds_into_one_node() {
        // 110 and 111 are 100 m apart; put a 4 m link in by reusing close nodes
        let mut o = osm(
            r#"{"type":"way","id":1,"nodes":[100,900],"tags":{"highway":"residential"}},
               {"type":"way","id":2,"nodes":[900,901],"tags":{"highway":"residential"}},
               {"type":"way","id":3,"nodes":[901,102],"tags":{"highway":"residential"}}"#,
        );
        o.elements.push(Element::Node { id: 900, lat: 56.0, lon: 10.001605 });
        o.elements.push(Element::Node { id: 901, lat: 56.0, lon: 10.001605 + 0.00006 });
        let plan = build(&o, &city());
        assert_eq!(plan.segments.len(), 4, "two 100 m streets, each split once");
        assert_eq!(plan.nodes.len(), 5, "the link's two ends became one node");
    }
}
