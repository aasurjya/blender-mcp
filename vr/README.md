# VR / web export scripts

Standalone Blender scripts for the VR baking + export pipeline. These run headless
against your own `.blend` files and are independent of the MCP server.

## `vr_bake.py`
Lightmap + normal-map baking for VR, batched by material group, then exports both a
PC-VR FBX and a decimated Quest FBX with resized lightmaps.

```bash
blender --background your_scene.blend --python vr_bake.py
```

Outputs go to `./lightmaps/` and FBX files next to the script. `BACKUP_PATH`,
`HERO_OBJECTS`, and the `GROUPS` table near the top are project-specific — adjust
them for your scene (missing objects are skipped, so it won't crash).

## `build_koroc_v.py`
Procedurally builds the "Koroc V" floating-cabin model and exports a Draco-compressed
GLB for the web.

```bash
blender --background --python build_koroc_v.py
# optional: set the output directory
KOROC_EXPORT_DIR=/path/to/out blender --background --python build_koroc_v.py
```

Default output: `./export/koroc-v.glb`.

## Prefer the MCP tools for interactive use
For chat-driven baking/export against the *currently open* scene, use the MCP tools
instead — they're generalized versions of this pipeline:

- `bake_lightmaps(output_dir, resolution, samples, selected_only, image_format, uv_layer)`
- `export_vr_fbx(filepath, decimate_ratio, triangulate)` — `decimate_ratio=0.25` gives a Quest LOD
