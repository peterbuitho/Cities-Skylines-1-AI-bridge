[out:json][timeout:180];
(
  way["landuse"~"^(residential|commercial|retail|industrial)$"](56.03,9.98,56.28,10.48);
  relation["landuse"~"^(residential|commercial|retail|industrial)$"](56.03,9.98,56.28,10.48);
  node["place"~"^(suburb|quarter|neighbourhood)$"](56.03,9.98,56.28,10.48);
);
out geom;