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
