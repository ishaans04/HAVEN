# Earth maps

`2k_earth_daymap.jpg`, `2k_earth_nightmap.jpg`, `2k_earth_clouds.jpg`,
`2k_earth_normal_map.jpg`, `2k_moon.jpg`

Solar System Scope texture set, 2048x1024 equirectangular.
<https://www.solarsystemscope.com/textures/>

Licensed **CC BY 4.0**. Derived from NASA imagery: Blue Marble Next Generation
(albedo), Black Marble / VIIRS Day-Night Band (city lights), MODIS cloud
composites, and SRTM/GEBCO-derived relief for the normals.

Only the *albedo lookup* and the *surface relief* use these. Sun direction, the
terminator, orbital mechanics, sunrise counting, axial tilt and the drag are all
computed -- see the header of `src/components/Earth.tsx`. If these files are
removed the shader falls back to procedural continents and everything else still
works.

## The normal map

Supplied as a 521 KB TIFF, which no browser decodes, so it was converted once:

    2048x1024 RGB TIFF  ->  JPEG q92, 4:4:4 chroma  ->  92 KB

Chroma subsampling is off deliberately. This is a vector field, not a
photograph: the red and green channels carry the X and Y of a surface normal,
and 4:2:0 would average away exactly the detail the relief is made of. Measured
against the TIFF, the conversion moves a channel by 1.28/255 on average and
13/255 at worst.

Verified as a genuine tangent-space normal map before being wired in -- mean
RGB 128.0 / 127.9 / 255.0, which is the flat vector (0, 0, 1), with blue
dominant on 100% of samples.

It loads on its own promise rather than joining the other three. Folded into the
same `Promise.all`, losing 92 KB of normals would drop the albedo, the city
lights and the clouds back to procedural along with it.

## The moon map

`2k_moon.jpg` -- same set, same licence, derived from Lunar Reconnaissance
Orbiter imagery. Recompressed from 1.03 MB to 538 KB at q82: it is drawn about
seventy pixels across, where the difference is not visible.

It supplies craters and nothing else. The **phase** -- the only thing on that
disc carrying meaning -- comes from the shared sun vector in `lib/sun.ts`, the
same one the Earth's terminator uses, so the crescent tracks the day/night line
on the planet beside it. If this file is missing the moon still shows the
correct phase in flat grey.
