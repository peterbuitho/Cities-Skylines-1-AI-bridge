[out:json][timeout:120];
(
  way["railway"~"light_rail|tram"](56.03,9.98,56.28,10.48);
  node["railway"~"tram_stop|station|halt"](56.03,9.98,56.28,10.48);
);
out body;
>;
out skel qt;
