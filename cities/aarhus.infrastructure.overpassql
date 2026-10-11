[out:json][timeout:180];
(
  nwr["power"="plant"](56.03,9.98,56.28,10.48);
  nwr["power"="generator"]["generator:source"!="solar"](56.03,9.98,56.28,10.48);
  nwr["power"="substation"]["substation"="transmission"](56.03,9.98,56.28,10.48);
  nwr["man_made"~"^(water_works|wastewater_plant|water_tower|pumping_station)$"](56.03,9.98,56.28,10.48);
  nwr["amenity"~"^(recycling|waste_transfer_station)$"]["recycling_type"="centre"](56.03,9.98,56.28,10.48);
  nwr["landuse"="landfill"](56.03,9.98,56.28,10.48);
);
out center tags;