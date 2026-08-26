# Advanced Crew Escape Suit

`crew-escape-suit.glb`

NASA 3D Resources — the orange pressure suit worn by Shuttle crews for launch
and entry. **Public domain**, as NASA-produced work.
<https://nasa3d.arc.nasa.gov/>

## What was done to it

The source file is 858 KB and Draco-compressed (`KHR_draco_mesh_compression`
appears in `extensionsRequired`), which a small parser cannot read — and the
Draco WASM decoder is around 250 KB, larger than the three.js this project
declined to add in the first place. So the mesh was decoded **once, offline**,
with `@gltf-transform/cli`, and what ships is plain glTF:

    weld  ->  simplify --ratio 0.2 --error 0.002  ->  prune  ->  quantize

- 88,872 triangles down to 37,633. It is rendered a few hundred pixels tall.
- `TEXCOORD_0` dropped: there are no textures and never were. The model is 14
  flat `baseColorFactor` materials, which is why it needs no image at all.
- Positions and normals quantized to normalized shorts
  (`KHR_mesh_quantization`), which costs the renderer nothing — WebGL reads
  them directly with `vertexAttribPointer(..., gl.SHORT, true, ...)` and the
  node's own transform undoes the scaling.

4.58 MB decompressed, 540 KB shipped, and it is fetched only when the section
scrolls into view.

## What it is, and is not

It is imagery — the subject of the page, not a readout. Every other visual here
is a planet or a chart, and the thing this product actually reasons about is a
person. Nothing about the pose or the lighting is derived from crew data, and
nothing should be read off it.

# International Space Station

`iss.glb`

NASA Johnson Space Center, Visual Communications Lab -- the 2011 assembly-
complete configuration. **Public domain.** Courtesy NASA.
<https://nasa3d.arc.nasa.gov/>

## How it got here

The source is Lightwave, not glTF: 66 `.lwo` files plus a `.lws` scene, and
the README says translating them is the end user's problem. Two things made it
tractable anyway.

LWO2 is IFF -- big-endian, four-character chunk ids -- and only two chunks
carry geometry: `PNTS` (float32 triples) and `POLS` (a vertex count then
variable-width indices). That is about a hundred lines to read, and 64 of the
66 files parse with zero out-of-range indices. The two that fail are an older
`LWLO` variant holding radiator panels.

And the modules are already positioned in a common station frame -- p6 sits at
y -1930, s6 at +1930, s0 across the middle -- so assembling the station is a
merge rather than a scene-graph walk. The scene file was never needed.

    46 modules  ->  585,324 verts / 570,737 tris  ->  10,431 / 38,250  ->  397 KB

Decimation is vertex clustering rather than edge collapse, and that choice is
not incidental: `gltf-transform simplify` stalls at ~100k triangles here
because the station is 46 separate shells, so nearly every edge is a boundary
edge and an edge-collapse simplifier will not touch it. Clustering quantises
positions onto a grid and merges whatever lands in the same cell, which
collapses across module boundaries because it has no notion of them.

Normals are generated -- LWO carries none.

## Checking it is the right shape

Proportions, against the real station's 109 m truss, 73 m module run and 27 m
depth:

    this model   1 : 0.70 : 0.29
    real ISS     1 : 0.67 : 0.25

Duplicates were dropped by hand: the set ships `fgb-ext`, `fgb-ext_layers` and
`fgb-ext_closed` as one module three ways, and visiting vehicles (Soyuz,
Progress, ATV, HTV) are not part of the station's silhouette.
