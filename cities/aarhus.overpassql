[out:json][timeout:300][maxsize:1073741824];
(
  way["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|living_street)$"](56.03,9.98,56.28,10.48);
  way["natural"="coastline"](56.03,9.98,56.28,10.48);
);
out body;
>;
out skel qt;
