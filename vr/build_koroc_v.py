"""
Build the Koroc V Floating Cabin 3D model for web export.
Blender 5.0+ — run headless:
  blender --background --python build_koroc_v.py

Output GLB is written next to this script under ./export/ by default. Override
with the KOROC_EXPORT_DIR environment variable.
"""

import bpy
import bmesh
import math
import os

# ---------------------------------------------------------------------------
# Constants — all measurements in meters (1 Blender unit = 1 m)
# ---------------------------------------------------------------------------
TOTAL_LENGTH = 8.5       # 28 ft
TOTAL_BEAM = 2.6         # 8.5 ft
PONTOON_DIA = 0.64       # 25 in
PONTOON_RADIUS = PONTOON_DIA / 2
CABIN_LENGTH = 6.7        # ~22 ft
CABIN_WIDTH = 2.13        # ~7 ft
CABIN_WALL_HEIGHT = 1.5   # 5 ft walls
ROOF_HEIGHT = 2.0         # from deck
DECK_THICKNESS = 0.1      # ~4 in
FRONT_DECK_LENGTH = 1.8   # open bow area
DRAFT = 0.3               # below waterline
RAILING_HEIGHT = 0.6      # ~2 ft

# Export path (override with KOROC_EXPORT_DIR; defaults to ./export next to this script)
EXPORT_DIR = os.environ.get(
    "KOROC_EXPORT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "export"),
)
EXPORT_PATH = os.path.join(EXPORT_DIR, "koroc-v.glb")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clear_scene():
    """Remove all default objects."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # Purge orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def hex_to_linear(hex_str):
    """Convert hex color string to linear sRGB tuple (r, g, b, 1.0)."""
    hex_str = hex_str.lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    # sRGB to linear
    def to_linear(c):
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    return (to_linear(r), to_linear(g), to_linear(b), 1.0)


def make_material(name, color_hex, roughness=0.5, metallic=0.0, alpha=1.0):
    """Create a PBR material with the given properties."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hex_to_linear(color_hex)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None
    return mat


def assign_material(obj, mat):
    """Assign material to object, replacing any existing."""
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def set_smooth(obj):
    """Enable smooth shading."""
    for poly in obj.data.polygons:
        poly.use_smooth = True


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def create_materials():
    """Create all materials and return as a dict."""
    return {
        "pontoon": make_material("Pontoon_Aluminum", "#B8B8B8", roughness=0.25, metallic=0.9),
        "deck": make_material("Deck_Cedar", "#8B6914", roughness=0.7, metallic=0.0),
        "cabin_wall": make_material("Cabin_WhiteCedar", "#FFF8E7", roughness=0.85, metallic=0.0),
        "window": make_material("Window_Tinted", "#1A3A4A", roughness=0.3, metallic=0.2),
        "roof": make_material("Roof_Composite", "#2A2A3A", roughness=0.4, metallic=0.3),
        "solar": make_material("Solar_Panel", "#1A1A4A", roughness=0.2, metallic=0.6),
        "canvas": make_material("Bimini_Canvas", "#E8DCC8", roughness=0.9, metallic=0.0, alpha=0.85),
        "steel": make_material("Stainless_Steel", "#C0C0C0", roughness=0.3, metallic=0.8),
        "railing": make_material("Railing_Cedar", "#A07828", roughness=0.8, metallic=0.0),
    }


# ---------------------------------------------------------------------------
# Build functions
# ---------------------------------------------------------------------------
def build_pontoon(name, y_offset, mats):
    """Create a single pontoon — tapered cylinder."""
    # Main cylinder body
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12,
        radius=PONTOON_RADIUS,
        depth=TOTAL_LENGTH * 0.85,
        location=(0, y_offset, 0),
        rotation=(0, math.radians(90), 0),
    )
    body = bpy.context.active_object
    body.name = name

    # Bow taper (front cone)
    bpy.ops.mesh.primitive_cone_add(
        vertices=12,
        radius1=PONTOON_RADIUS,
        radius2=0.05,
        depth=TOTAL_LENGTH * 0.1,
        location=(TOTAL_LENGTH * 0.85 / 2 + TOTAL_LENGTH * 0.05, y_offset, 0),
        rotation=(0, math.radians(90), 0),
    )
    bow = bpy.context.active_object

    # Stern taper (rear cone)
    bpy.ops.mesh.primitive_cone_add(
        vertices=12,
        radius1=0.08,
        radius2=PONTOON_RADIUS,
        depth=TOTAL_LENGTH * 0.05,
        location=(-(TOTAL_LENGTH * 0.85 / 2 + TOTAL_LENGTH * 0.025), y_offset, 0),
        rotation=(0, math.radians(90), 0),
    )
    stern = bpy.context.active_object

    # Join all parts
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bow.select_set(True)
    stern.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()

    assign_material(body, mats["pontoon"])
    set_smooth(body)
    return body


def build_pontoons(mats):
    """Create three pontoons."""
    spacing = TOTAL_BEAM / 2 - PONTOON_RADIUS
    pontoons = []
    for i, y in enumerate([-spacing, 0, spacing]):
        p = build_pontoon(f"Pontoon_{i}", y, mats)
        pontoons.append(p)
    return pontoons


def build_deck(mats):
    """Create the main deck platform."""
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, 0, PONTOON_RADIUS + DECK_THICKNESS / 2),
    )
    deck = bpy.context.active_object
    deck.name = "Deck"
    deck.scale = (TOTAL_LENGTH, TOTAL_BEAM, DECK_THICKNESS)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(deck, mats["deck"])
    return deck


def build_cabin(mats):
    """Create cabin walls with window cutouts."""
    deck_top = PONTOON_RADIUS + DECK_THICKNESS
    cabin_x_start = -TOTAL_LENGTH / 2 + (TOTAL_LENGTH - CABIN_LENGTH) / 2 - FRONT_DECK_LENGTH / 2
    cabin_center_x = cabin_x_start + CABIN_LENGTH / 2

    # Main cabin box
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(cabin_center_x, 0, deck_top + CABIN_WALL_HEIGHT / 2),
    )
    cabin = bpy.context.active_object
    cabin.name = "Cabin"
    cabin.scale = (CABIN_LENGTH, CABIN_WIDTH, CABIN_WALL_HEIGHT)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Remove interior faces using solidify modifier for thin walls
    solidify = cabin.modifiers.new(name="Solidify", type="SOLIDIFY")
    solidify.thickness = 0.06
    solidify.offset = -1  # Outward
    bpy.ops.object.modifier_apply(modifier="Solidify")

    assign_material(cabin, mats["cabin_wall"])
    set_smooth(cabin)

    # --- Windows (port side) ---
    window_height = 0.6
    window_length = CABIN_LENGTH * 0.75
    window_z = deck_top + CABIN_WALL_HEIGHT * 0.5

    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(cabin_center_x, CABIN_WIDTH / 2 + 0.005, window_z),
    )
    win_port = bpy.context.active_object
    win_port.name = "Window_Port"
    win_port.scale = (window_length, 0.02, window_height)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(win_port, mats["window"])

    # --- Windows (starboard side) ---
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(cabin_center_x, -CABIN_WIDTH / 2 - 0.005, window_z),
    )
    win_star = bpy.context.active_object
    win_star.name = "Window_Starboard"
    win_star.scale = (window_length, 0.02, window_height)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(win_star, mats["window"])

    # --- Cabin door (front face) ---
    door_x = cabin_center_x + CABIN_LENGTH / 2 + 0.005
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(door_x, 0, deck_top + 0.9 / 2),
    )
    door = bpy.context.active_object
    door.name = "Cabin_Door"
    door.scale = (0.02, 0.55, 0.9)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(door, mats["railing"])

    # Door window
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(door_x + 0.005, 0, deck_top + 0.65),
    )
    door_win = bpy.context.active_object
    door_win.name = "Door_Window"
    door_win.scale = (0.01, 0.35, 0.25)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(door_win, mats["window"])

    return cabin


def build_roof(mats):
    """Create roof with solar panels."""
    deck_top = PONTOON_RADIUS + DECK_THICKNESS
    cabin_x_start = -TOTAL_LENGTH / 2 + (TOTAL_LENGTH - CABIN_LENGTH) / 2 - FRONT_DECK_LENGTH / 2
    cabin_center_x = cabin_x_start + CABIN_LENGTH / 2
    roof_z = deck_top + CABIN_WALL_HEIGHT

    roof_length = 7.0   # ~23 ft
    roof_width = 2.3    # ~7.5 ft

    # Roof base
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(cabin_center_x, 0, roof_z + 0.04),
    )
    roof = bpy.context.active_object
    roof.name = "Roof"
    roof.scale = (roof_length, roof_width, 0.08)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(roof, mats["roof"])

    # Solar panel array
    solar_length = 5.5   # ~18 ft
    solar_width = 1.7    # ~5.5 ft
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(cabin_center_x, 0, roof_z + 0.09),
    )
    solar = bpy.context.active_object
    solar.name = "Solar_Panels"
    solar.scale = (solar_length, solar_width, 0.02)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(solar, mats["solar"])

    # Solar panel frame
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(cabin_center_x, 0, roof_z + 0.085),
    )
    frame = bpy.context.active_object
    frame.name = "Solar_Frame"
    frame.scale = (solar_length + 0.06, solar_width + 0.06, 0.015)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(frame, mats["steel"])

    # Ventilation fans (2 cylinders)
    for i, x_off in enumerate([-1.5, 1.5]):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8,
            radius=0.12,
            depth=0.15,
            location=(cabin_center_x + x_off, 0.7, roof_z + 0.15),
        )
        vent = bpy.context.active_object
        vent.name = f"Vent_Fan_{i}"
        assign_material(vent, mats["steel"])

    return roof


def build_front_deck(mats):
    """Create bow railing and bimini shade."""
    deck_top = PONTOON_RADIUS + DECK_THICKNESS

    # Front railing — U-shape using 3 boxes (left, front, right)
    bow_front_x = TOTAL_LENGTH / 2
    bow_back_x = bow_front_x - FRONT_DECK_LENGTH

    railing_parts = []

    # Front rail
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(bow_front_x - 0.02, 0, deck_top + RAILING_HEIGHT / 2),
    )
    r = bpy.context.active_object
    r.name = "Railing_Front"
    r.scale = (0.04, TOTAL_BEAM - 0.1, RAILING_HEIGHT)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    railing_parts.append(r)

    # Left rail
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=((bow_front_x + bow_back_x) / 2, TOTAL_BEAM / 2 - 0.02, deck_top + RAILING_HEIGHT / 2),
    )
    r = bpy.context.active_object
    r.name = "Railing_Left"
    r.scale = (FRONT_DECK_LENGTH, 0.04, RAILING_HEIGHT)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    railing_parts.append(r)

    # Right rail
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=((bow_front_x + bow_back_x) / 2, -TOTAL_BEAM / 2 + 0.02, deck_top + RAILING_HEIGHT / 2),
    )
    r = bpy.context.active_object
    r.name = "Railing_Right"
    r.scale = (FRONT_DECK_LENGTH, 0.04, RAILING_HEIGHT)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    railing_parts.append(r)

    for part in railing_parts:
        assign_material(part, mats["railing"])

    # --- Bimini shade ---
    bimini_center_x = (bow_front_x + bow_back_x) / 2
    pole_height = 2.2

    # Left pole
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=0.02,
        depth=pole_height,
        location=(bimini_center_x, TOTAL_BEAM / 2 - 0.15, deck_top + pole_height / 2),
    )
    pole_l = bpy.context.active_object
    pole_l.name = "Bimini_Pole_L"
    assign_material(pole_l, mats["steel"])

    # Right pole
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=0.02,
        depth=pole_height,
        location=(bimini_center_x, -TOTAL_BEAM / 2 + 0.15, deck_top + pole_height / 2),
    )
    pole_r = bpy.context.active_object
    pole_r.name = "Bimini_Pole_R"
    assign_material(pole_r, mats["steel"])

    # Canvas shade
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(bimini_center_x, 0, deck_top + pole_height),
    )
    canvas = bpy.context.active_object
    canvas.name = "Bimini_Canvas"
    canvas.scale = (FRONT_DECK_LENGTH * 0.8, TOTAL_BEAM * 0.7, 0.02)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(canvas, mats["canvas"])


def build_accessories(mats):
    """Add cleats, propane tank, ladder, water tank."""
    deck_top = PONTOON_RADIUS + DECK_THICKNESS
    stern_x = -TOTAL_LENGTH / 2

    # Cleats — 4 small T-shapes (simplified as small boxes)
    cleat_positions = [
        (TOTAL_LENGTH / 2 - 0.1, 0, deck_top + 0.03),           # bow
        (stern_x + 0.1, 0, deck_top + 0.03),                     # stern
        (0, TOTAL_BEAM / 2 - 0.05, deck_top + 0.03),             # port
        (0, -TOTAL_BEAM / 2 + 0.05, deck_top + 0.03),            # starboard
    ]
    for i, pos in enumerate(cleat_positions):
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        cleat = bpy.context.active_object
        cleat.name = f"Cleat_{i}"
        cleat.scale = (0.12, 0.04, 0.04)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        assign_material(cleat, mats["steel"])

    # Propane tank (stern)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=0.15,
        depth=0.35,
        location=(stern_x + 0.4, 0.6, deck_top + 0.2),
    )
    propane = bpy.context.active_object
    propane.name = "Propane_Tank"
    assign_material(propane, mats["steel"])

    # Stern ladder — 2 vertical bars + 3 rungs
    ladder_x = stern_x + 0.05
    ladder_z_bottom = -0.2
    ladder_z_top = deck_top + 0.1

    for y_off in [-0.15, 0.15]:
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(ladder_x, y_off, (ladder_z_bottom + ladder_z_top) / 2),
        )
        bar = bpy.context.active_object
        bar.name = f"Ladder_Bar_{y_off}"
        bar.scale = (0.02, 0.02, ladder_z_top - ladder_z_bottom)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        assign_material(bar, mats["steel"])

    for j in range(3):
        rung_z = ladder_z_bottom + (ladder_z_top - ladder_z_bottom) * (j + 1) / 4
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(ladder_x, 0, rung_z),
        )
        rung = bpy.context.active_object
        rung.name = f"Ladder_Rung_{j}"
        rung.scale = (0.02, 0.3, 0.02)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        assign_material(rung, mats["steel"])


# ---------------------------------------------------------------------------
# Finalize & Export
# ---------------------------------------------------------------------------
def finalize_and_export():
    """Apply transforms, clean up, set origin, export GLB."""
    # Select all mesh objects
    bpy.ops.object.select_all(action="SELECT")

    # Apply all transforms
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Remove doubles on each mesh
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.remove_doubles(threshold=0.001)
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode="OBJECT")

    # Join all objects into one
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = bpy.data.objects[0]
    bpy.ops.object.join()

    boat = bpy.context.active_object
    boat.name = "KorocV"

    # Set origin to center bottom (waterline)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    # Move origin to bottom center
    boat.location.z = 0

    # Print stats
    tri_count = sum(len(p.vertices) - 2 for p in boat.data.polygons)
    print(f"Triangle count: {tri_count}")

    # Ensure export directory exists
    os.makedirs(EXPORT_DIR, exist_ok=True)

    # Export as GLB with Draco compression
    bpy.ops.export_scene.gltf(
        filepath=EXPORT_PATH,
        export_format="GLB",
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_apply=True,
        export_yup=True,
    )
    print(f"Exported to: {EXPORT_PATH}")

    # Check file size
    file_size = os.path.getsize(EXPORT_PATH)
    print(f"File size: {file_size / 1024:.1f} KB")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    clear_scene()
    mats = create_materials()

    print("Building pontoons...")
    build_pontoons(mats)

    print("Building deck...")
    build_deck(mats)

    print("Building cabin...")
    build_cabin(mats)

    print("Building roof & solar...")
    build_roof(mats)

    print("Building front deck & bimini...")
    build_front_deck(mats)

    print("Building accessories...")
    build_accessories(mats)

    print("Finalizing & exporting...")
    finalize_and_export()

    print("Done! Koroc V model built and exported.")


if __name__ == "__main__":
    main()
