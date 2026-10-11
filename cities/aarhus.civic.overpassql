[out:json][timeout:120];
(
  nwr["amenity"~"^(school|university|college|hospital|clinic|fire_station|police|crematorium|library)$"](56.105,10.12,56.20,10.26);
  nwr["landuse"="cemetery"](56.105,10.12,56.20,10.26);
  nwr["amenity"="recycling"]["recycling_type"="centre"](56.105,10.12,56.20,10.26);
);
out center tags;