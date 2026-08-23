# Earth maps

`2k_earth_daymap.jpg`, `2k_earth_nightmap.jpg`, `2k_earth_clouds.jpg`

Solar System Scope texture set, 2048×1024 equirectangular.
<https://www.solarsystemscope.com/textures/>

Licensed **CC BY 4.0**. Derived from NASA imagery: Blue Marble Next Generation
(albedo), Black Marble / VIIRS Day-Night Band (city lights), and MODIS cloud
composites.

Only the *albedo lookup* uses these. Sun direction, the terminator, orbital
mechanics, sunrise counting, axial tilt and the drag are all computed — see the
header of `src/components/Earth.tsx`. If these files are removed the shader
falls back to procedural continents and everything else still works.
