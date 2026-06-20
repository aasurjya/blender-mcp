"""
VR Lightmap + Normal Map Bake Script (project-specific reference pipeline).

Run headless against your own .blend, e.g.:
  blender --background your_scene.blend --python vr_bake.py

Outputs (lightmaps, FBX) are written next to this script, under ./lightmaps/.
NOTE: BACKUP_PATH and HERO_OBJECTS below are specific to the original interior
scene; adjust them (or the GROUPS table) for your own project. Objects that are
not found are skipped, so it degrades gracefully.

For an interactive, generalized version driven from chat, use the MCP tools
`bake_lightmaps` and `export_vr_fbx` instead.
"""

import bpy
import os
import math

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lightmaps")
os.makedirs(OUTPUT_DIR, exist_ok=True)

UV_LM = "UVMap_Lightmap"
LINEAR_CS = "Linear Rec.709"   # confirmed valid in this Blender build

# ─── Material group → (resolution, bake_order)
GROUPS = [
    ("floors",         512,  1),
    ("walls_ceilings", 1024, 2),
    ("upholstery",     2048, 3),   # hero curved objects
    ("wood_furniture", 2048, 4),
    ("small_decor",    2048, 5),
]

# ─── Configure Cycles ──────────────────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine = "CYCLES"
# CPU is required for headless/background mode on macOS (Metal GPU unavailable)
scene.cycles.device = "CPU"
scene.cycles.samples = 256
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPENIMAGEDENOISE"
scene.cycles.max_bounces = 4
scene.cycles.diffuse_bounces = 3
scene.cycles.glossy_bounces = 2
scene.cycles.transmission_bounces = 2
scene.cycles.volume_bounces = 0
scene.cycles.transparent_max_bounces = 4
scene.render.bake.use_pass_direct = True
scene.render.bake.use_pass_indirect = True
scene.render.bake.use_pass_color = True
scene.render.bake.use_selected_to_active = False
scene.render.bake.margin = 4
scene.render.bake.margin_type = "EXTEND"

print("Cycles configured.")

# ─── Normal Map Baking from Backup (Selected-to-Active) ───────────────────────
# Bake normals for the 5 heaviest objects using backup high-poly meshes.
BACKUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interior__BACKUP_pre_vr.blend")
HERO_OBJECTS = ["Object204", "Object001.001", "Object002.001", "003", "001"]
NORMAL_RES = 1024

def bake_normal_map(lowpoly_name, hipoly_name, resolution):
    """Bake normal from hi-poly (appended from backup) to lo-poly UV0."""
    lowpoly = bpy.context.scene.objects.get(lowpoly_name)
    hipoly  = bpy.context.scene.objects.get(hipoly_name)
    if not lowpoly or not hipoly:
        print(f"  [NORMAL] SKIP {lowpoly_name}: object(s) not found")
        return None

    img_name = f"NM_{lowpoly_name.replace('.', '_')}_{resolution}"
    if img_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[img_name])
    nm_img = bpy.data.images.new(img_name, resolution, resolution,
                                  alpha=False, float_buffer=True)
    nm_img.colorspace_settings.name = LINEAR_CS

    # Wire NM image node into lowpoly material(s)
    for slot in lowpoly.material_slots:
        mat = slot.material
        if not mat:
            continue
        if not mat.use_nodes:
            mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nm_node = nodes.get("__NM_BAKE__")
        if not nm_node:
            nm_node = nodes.new("ShaderNodeTexImage")
            nm_node.name = "__NM_BAKE__"
            nm_node.location = (-800, -600)
        nm_node.image = nm_img
        nodes.active = nm_node

    # Set UV0 as active on lowpoly
    if lowpoly.data.uv_layers:
        lowpoly.data.uv_layers.active = lowpoly.data.uv_layers[0]

    # Select hipoly(s), active = lowpoly
    bpy.ops.object.select_all(action="DESELECT")
    hipoly.select_set(True)
    lowpoly.select_set(True)
    bpy.context.view_layer.objects.active = lowpoly

    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = 0.05

    try:
        bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True,
                             use_clear=True, margin=4)
        out_path = os.path.join(OUTPUT_DIR, f"{img_name}.exr")
        nm_img.file_format = "OPEN_EXR"
        nm_img.filepath_raw = out_path
        nm_img.save()
        print(f"  [NORMAL] Saved: {out_path}")
        # Wire it back in as actual Normal Map node
        for slot in lowpoly.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes:
                continue
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nm_tex_node = nodes.get("__NM_BAKE__")
            if nm_tex_node:
                nm_tex_node.image = nm_img
                # Add NormalMap node between texture and BSDF
                nm_map_node = nodes.new("ShaderNodeNormalMap")
                nm_map_node.location = (-400, -600)
                bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf:
                    links.new(nm_tex_node.outputs["Color"], nm_map_node.inputs["Color"])
                    links.new(nm_map_node.outputs["Normal"], bsdf.inputs["Normal"])
        return img_name
    except Exception as e:
        print(f"  [NORMAL] ERROR {lowpoly_name}: {e}")
        return None
    finally:
        scene.render.bake.use_selected_to_active = False
        bpy.ops.object.select_all(action="DESELECT")

# Append hero objects from backup and bake normal maps
print("\n=== NORMAL MAP BAKING ===")
with bpy.data.libraries.load(BACKUP_PATH, link=False) as (data_from, data_to):
    hero_to_append = [n for n in data_from.objects if n in HERO_OBJECTS]
    data_to.objects = hero_to_append
    print(f"Appending {len(hero_to_append)} hi-poly objects from backup...")

# Link appended objects and build lowpoly_name → hipoly_name map
# (Blender may rename appended objects to avoid conflicts, e.g. "Object204.001")
hipoly_map = {}   # original_hero_name → actual_appended_object_name
hipoly_names = []
for i, obj in enumerate(data_to.objects):
    if obj is None:
        continue
    original_name = hero_to_append[i]  # the name we requested
    bpy.context.scene.collection.objects.link(obj)
    obj.name = f"HIPOLY_{original_name}"   # rename to HIPOLY_ prefix
    # After rename, Blender may add suffix if conflict — read actual name
    actual_name = obj.name
    hipoly_map[original_name] = actual_name
    hipoly_names.append(actual_name)
    tris = sum(len(p.vertices)-2 for p in obj.data.polygons)
    print(f"  Appended: {actual_name} (requested '{original_name}', {tris:,} tris)")

# Bake normals using the tracked actual names
for hero in HERO_OBJECTS:
    hipoly_name = hipoly_map.get(hero)
    if not hipoly_name:
        print(f"  [NORMAL] SKIP {hero}: not appended")
        continue
    nm = bake_normal_map(hero, hipoly_name, NORMAL_RES)
    print(f"  {hero}: {'OK — ' + str(nm) if nm else 'SKIP'}")

# Remove hi-poly objects after baking
for hname in hipoly_names:
    obj = bpy.context.scene.objects.get(hname)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
print("Hi-poly objects removed.")

# ─── Lightmap Baking ──────────────────────────────────────────────────────────
print("\n=== LIGHTMAP BAKING ===")

def bake_group(group_name, resolution):
    print(f"\n  Group: {group_name} ({resolution}x{resolution})")
    objs = [o for o in bpy.context.scene.objects
            if o.type == "MESH" and o.get("vr_material_group") == group_name]
    if not objs:
        print(f"  No objects, skipping.")
        return None

    # Re-pack UV1 just for this group
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objs:
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
        if UV_LM in obj.data.uv_layers:
            obj.data.uv_layers.active = obj.data.uv_layers[UV_LM]
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.01,
                              area_weight=0.0, correct_aspect=True, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Create bake image
    img_name = f"LM_{group_name}_{resolution}"
    if img_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[img_name])
    bake_img = bpy.data.images.new(img_name, resolution, resolution,
                                    alpha=False, float_buffer=True)
    bake_img.colorspace_settings.name = LINEAR_CS

    # Wire bake image as active node in all materials
    mats_done = set()
    for obj in objs:
        for slot in obj.material_slots:
            mat = slot.material
            if not mat or id(mat) in mats_done:
                continue
            mats_done.add(id(mat))
            if not mat.use_nodes:
                mat.use_nodes = True
            nodes = mat.node_tree.nodes
            bk = nodes.get("__BAKE_TARGET__")
            if not bk:
                bk = nodes.new("ShaderNodeTexImage")
                bk.name = "__BAKE_TARGET__"
                bk.location = (-800, -500)
            bk.image = bake_img
            nodes.active = bk  # CRITICAL

    # Set UV1 as active on all group objects
    for obj in objs:
        if UV_LM in obj.data.uv_layers:
            obj.data.uv_layers.active = obj.data.uv_layers[UV_LM]

    bpy.context.view_layer.objects.active = objs[0]
    print(f"  Baking {len(objs)} objects...")

    try:
        bpy.ops.object.bake(type="COMBINED",
                             pass_filter={"DIRECT", "INDIRECT", "COLOR"},
                             use_selected_to_active=False,
                             use_clear=True, margin=4)
    except Exception as e:
        print(f"  BAKE ERROR: {e}")
        bpy.ops.object.select_all(action="DESELECT")
        return None

    # Save EXR
    out_path = os.path.join(OUTPUT_DIR, f"{img_name}.exr")
    bake_img.file_format = "OPEN_EXR"
    bake_img.filepath_raw = out_path
    bake_img.save()
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"  Saved: {out_path} ({size_mb:.1f} MB)")
    bpy.ops.object.select_all(action="DESELECT")
    return img_name

baked = []
for group_name, resolution, _ in sorted(GROUPS, key=lambda x: x[2]):
    result = bake_group(group_name, resolution)
    if result:
        baked.append(result)

# ─── Export PC VR FBX ─────────────────────────────────────────────────────────
print("\n=== FBX EXPORT ===")
fbx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interior_vr_pcvr.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=False,
    use_visible=True,
    use_mesh_modifiers=True,
    use_triangles=True,
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_NONE",
    axis_forward="-Z",
    axis_up="Y",
    global_scale=1.0,
    mesh_smooth_type="FACE",
    path_mode="COPY",
    embed_textures=True,
    bake_anim=False,
    add_leaf_bones=False,
)
fbx_size = os.path.getsize(fbx_path) / (1024 * 1024)
print(f"PC VR FBX: {fbx_path} ({fbx_size:.1f} MB)")

# ─── Quest Pass: further decimate ─────────────────────────────────────────────
print("\n=== QUEST DECIMATE PASS ===")
total_before = sum(sum(len(p.vertices)-2 for p in o.data.polygons)
                   for o in bpy.context.scene.objects if o.type == "MESH")

for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    tris = sum(len(p.vertices)-2 for p in obj.data.polygons)
    if tris < 100:
        continue
    obj.hide_viewport = False
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    mod = obj.modifiers.new("Quest_Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = 0.25  # keep 25% of current (PC VR) mesh
    mod.use_collapse_triangulate = True
    try:
        bpy.ops.object.modifier_apply(modifier="Quest_Decimate")
    except:
        obj.modifiers.remove(mod)
    obj.select_set(False)

total_after = sum(sum(len(p.vertices)-2 for p in o.data.polygons)
                  for o in bpy.context.scene.objects if o.type == "MESH")
print(f"Quest tris: {total_before:,} → {total_after:,} ({100*(1-total_after/total_before):.0f}% reduction)")

# Resize lightmaps for Quest (2048→1024, 1024→512, 512→256)
from pathlib import Path
for exr in Path(OUTPUT_DIR).glob("LM_*.exr"):
    # Blender rescale
    for img in bpy.data.images:
        if img.filepath_raw == str(exr):
            img.scale(max(img.size[0]//2, 256), max(img.size[1]//2, 256))
            quest_path = str(exr).replace(".exr", "_quest.png")
            img.file_format = "PNG"
            img.filepath_raw = quest_path
            img.save()
            print(f"  Quest lightmap: {quest_path}")
            break

# Export Quest FBX
quest_fbx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interior_vr_quest.fbx")
bpy.ops.export_scene.fbx(
    filepath=quest_fbx,
    use_selection=False, use_visible=True,
    use_mesh_modifiers=True, use_triangles=True,
    apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
    axis_forward="-Z", axis_up="Y", global_scale=1.0,
    mesh_smooth_type="FACE", path_mode="COPY",
    embed_textures=True, bake_anim=False, add_leaf_bones=False,
)
q_size = os.path.getsize(quest_fbx) / (1024 * 1024)
print(f"Quest FBX: {quest_fbx} ({q_size:.1f} MB)")

print("\n=== ALL DONE ===")
print(f"Lightmaps: {OUTPUT_DIR}")
print(f"PC VR FBX: {fbx_path}")
print(f"Quest FBX: {quest_fbx}")
