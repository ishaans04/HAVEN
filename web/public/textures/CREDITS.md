# Earth maps

`2k_earth_daymap.jpg`, `2k_earth_nightmap.jpg`, `2k_earth_clouds.jpg`,
`2k_earth_normal_map.jpg`, `2k_moon.jpg`

Solar System Scope texture set, sourced at 2048x1024 equirectangular.
<https://www.solarsystemscope.com/textures/>

The `2k_` prefix records where each file came from, not what ships. Two of
them were resampled to what they are actually drawn at -- see below. As
shipped:

| file | shipped | source |
| --- | --- | --- |
| `2k_earth_daymap.jpg` | 2048x1024, 452 KB | unchanged |
| `2k_earth_nightmap.jpg` | 2048x1024, 249 KB | unchanged |
| `2k_earth_normal_map.jpg` | 2048x1024, 90 KB | converted from TIFF |
| `2k_earth_clouds.jpg` | **1536x768, 391 KB** | was 2048x1024, 943 KB |
| `2k_moon.jpg` | **512x256, 43 KB** | was 2048x1024, 538 KB |

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
Orbiter imagery.

Resampled to **512x256, 43 KB**, down from 538 KB, because the disc renders 84
device pixels across. An equirectangular map shows half its width at once, so
2048 put 1024 texels behind those 84 pixels -- twelve times more than could be
resolved. At 512 it is still 3x oversampled at dpr 1 and 1.5x on a retina
screen. Measured on the rendered disc before and after: mean RGB moves 0.17 of
255, contrast drops 1%, the lit area is identical to the pixel.

It supplies craters and nothing else. The **phase** -- the only thing on that
disc carrying meaning -- comes from the shared sun vector in `lib/sun.ts`, the
same one the Earth's terminator uses, so the crescent tracks the day/night line
on the planet beside it. If this file is missing the moon still shows the
correct phase in flat grey.

## The cloud map

Resampled to **1536x768 at q90, 391 KB**, down from 943 KB -- the largest file
on the site, for the layer carrying the least information.

Two things make that safe. The shader reads `.r` and nothing else (it is an
opacity mask, and the source is already pure grey -- mean chroma measured at
0.00), and the planet renders 729 device pixels across, so 1536 puts 768 texels
behind them: right at Nyquist, where 2048 was 1.4x oversampled. Re-encoding at
q90 costs the same rmse of 3.13 whether the map is 2048 or 1536, so the
resolution is where the saving is, not the quality.

Note the asymmetry with the albedo, which is deliberate: the daymap stays at
2048 because at 729 pixels it is only 1.4x oversampled at dpr 1 and *under*
sampled on a retina screen, and it is the map carrying the coastlines.
