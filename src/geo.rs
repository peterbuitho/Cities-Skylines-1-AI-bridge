//! Latitude/longitude to game metres.

use serde::Deserialize;

/// How a city's heightmap sits on the globe. The game map is centred on (0, 0),
/// +x is east and +z is north.
#[derive(Debug, Clone, Deserialize)]
pub struct Georef {
    /// Real-world point that sits at the centre of the game map.
    pub center_lat: f64,
    pub center_lon: f64,
    /// Game metres per real metre.
    #[serde(default = "one")]
    pub scale: f64,
    /// Counter-clockwise rotation of the real world on the game map, in degrees.
    /// Non-zero when the heightmap was cut from a projected grid such as UTM.
    #[serde(default)]
    pub rotation_deg: f64,
}

fn one() -> f64 {
    1.0
}

// WGS84
const A: f64 = 6_378_137.0;
const E2: f64 = 0.006_694_379_990_14;

impl Georef {
    /// Returns (x, z) in game metres. Accurate to a few metres within ~20 km of the centre.
    pub fn project(&self, lat: f64, lon: f64) -> (f64, f64) {
        let lat0 = self.center_lat.to_radians();
        let phi = lat.to_radians();
        let w = |p: f64| 1.0 - E2 * p.sin().powi(2);
        let meridian = A * (1.0 - E2) / w(lat0).powf(1.5);
        let normal = A / w(phi).sqrt();

        let east = normal * phi.cos() * (lon - self.center_lon).to_radians();
        // Meridians converge towards the pole, so a point east or west of the
        // centre sits slightly north of its parallel on a flat map.
        let north = meridian * (phi - lat0) + east * east * lat0.tan() / (2.0 * normal);

        let (sin, cos) = self.rotation_deg.to_radians().sin_cos();
        (
            self.scale * (east * cos - north * sin),
            self.scale * (east * sin + north * cos),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn aarhus() -> Georef {
        Georef { center_lat: 56.15, center_lon: 10.2, scale: 1.0, rotation_deg: 0.0 }
    }

    #[test]
    fn centre_maps_to_origin() {
        let (x, z) = aarhus().project(56.15, 10.2);
        assert!(x.abs() < 1e-6 && z.abs() < 1e-6);
    }

    #[test]
    fn one_minute_of_latitude_is_about_1856_metres_north() {
        let (x, z) = aarhus().project(56.15 + 1.0 / 60.0, 10.2);
        assert!(x.abs() < 1e-6);
        assert!((z - 1856.0).abs() < 2.0, "z = {z}");
    }

    #[test]
    fn one_minute_of_longitude_is_about_1036_metres_east() {
        let (x, z) = aarhus().project(56.15, 10.2 + 1.0 / 60.0);
        assert!((x - 1036.0).abs() < 2.0, "x = {x}");
        assert!(z.abs() < 1.0);
    }

    #[test]
    fn rotation_and_scale_apply() {
        let g = Georef { rotation_deg: 90.0, scale: 0.5, ..aarhus() };
        let (x, z) = g.project(56.15 + 1.0 / 60.0, 10.2);
        // north turns into -x under a 90 degree counter-clockwise rotation
        assert!((x + 928.0).abs() < 1.0, "x = {x}");
        assert!(z.abs() < 1e-6);
    }
}
