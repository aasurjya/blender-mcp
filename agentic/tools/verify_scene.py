r"""verify_scene — cheap pre-flight checks for an agent-built Blender scene.

Every check here corresponds to a failure that actually shipped in the Sail Tower build
(../RETROSPECTIVE.md). They are all fast (no rendering) and project-agnostic, so an agent can run
this before AND after a change and diff the two.

    import sys; sys.path.append(r"...\agentic\tools")
    import verify_scene; verify_scene.run()                      # full table
    verify_scene.run(expect_cameras={"Cam_Ref": (-94.76, -472.39, 71.0)})   # + camera lock check

Exit signal: `run()` returns (ok: bool, problems: list[str]).
"""

import bpy


def _tris(obj, dg):
    try:
        me = obj.evaluated_get(dg).to_mesh()
    except Exception:
        return 0
    try:
        return sum(len(p.vertices) - 2 for p in me.polygons)
    finally:
        obj.evaluated_get(dg).to_mesh_clear()


def generated_images_without_pixels():
    """Blender does NOT store generated-image pixels in the .blend. After a reload they come back
    black and every material sampling them renders wrong — this silently ruined a set of finals."""
    bad = []
    for im in bpy.data.images:
        if im.source == 'GENERATED' and im.users:
            try:
                if not im.has_data or len(im.pixels) == 0:
                    bad.append(im.name)
            except Exception:
                bad.append(im.name)
    return bad


def missing_image_files():
    """File-backed images whose file is gone AND whose pixels are not packed into the .blend.

    Note `has_data` is NOT the test — Blender loads image pixels lazily, and a packed image
    reports a dead filepath while being perfectly safe. Asset downloaders (PolyHaven) unpack to
    a temp directory that Windows will eventually clear, so 'packed' is the thing that matters.
    """
    import os
    bad = []
    for im in bpy.data.images:
        if im.source != 'FILE' or not im.users or im.packed_file is not None:
            continue
        fp = bpy.path.abspath(im.filepath_raw or im.filepath)
        if not fp or not os.path.exists(fp):
            bad.append(im.name)
    return bad


def unpacked_temp_images():
    """Images still pointing at a temp directory. Packed ones are safe but should be repacked
    into the project's assets/ folder if the .blend is ever shared."""
    import os, tempfile
    tmp = os.path.realpath(tempfile.gettempdir()).lower()
    out = []
    for im in bpy.data.images:
        if im.source != 'FILE' or not im.users:
            continue
        fp = bpy.path.abspath(im.filepath_raw or im.filepath)
        if fp and os.path.realpath(fp).lower().startswith(tmp):
            out.append(im.name)
    return out


def empty_material_slots():
    return [f"{o.name}[{i}]" for o in bpy.data.objects if o.type == 'MESH'
            for i, s in enumerate(o.material_slots) if s.material is None]


def materials_without_output():
    bad = []
    for m in bpy.data.materials:
        if not m.users or not m.use_nodes or not m.node_tree:
            continue
        if not any(n.type == 'OUTPUT_MATERIAL' for n in m.node_tree.nodes):
            bad.append(m.name)
    return bad


def duplicate_suffix_objects(limit=12):
    """`Foo.001` usually means something was duplicated instead of instanced or reused by name."""
    dup = [o.name for o in bpy.data.objects
           if len(o.name) > 4 and o.name[-4] == '.' and o.name[-3:].isdigit()]
    return dup[:limit], len(dup)


def instancing(objs=None):
    """Objects sharing mesh data are instances; a low ratio means memory is being wasted."""
    meshes = {}
    for o in (objs or bpy.data.objects):
        if o.type == 'MESH' and o.data:
            meshes.setdefault(o.data.name, 0)
            meshes[o.data.name] += 1
    users = sum(meshes.values())
    return users, len(meshes)


def bad_transforms():
    out = []
    for o in bpy.data.objects:
        loc, sc = o.location, o.scale
        if any(v != v for v in (*loc, *sc)):                      # NaN
            out.append(f"{o.name}: NaN transform")
        elif min(abs(v) for v in sc) < 1e-5:
            out.append(f"{o.name}: near-zero scale")
        elif max(abs(v) for v in loc) > 1e6:
            out.append(f"{o.name}: location out of range")
    return out


def tri_report(top=8):
    dg = bpy.context.evaluated_depsgraph_get()
    per_coll, total = {}, 0
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.hide_render:
            continue
        t = _tris(o, dg)
        total += t
        key = o.users_collection[0].name if o.users_collection else "(none)"
        per_coll[key] = per_coll.get(key, 0) + t
    ranked = sorted(per_coll.items(), key=lambda kv: -kv[1])[:top]
    return total, ranked


def run(expect_cameras=None, tri_budget=None, verbose=True):
    problems = []
    p = print if verbose else (lambda *a, **k: None)

    p("=" * 62)
    p(f"scene '{bpy.context.scene.name}'  file: {bpy.data.filepath or '(unsaved)'}")
    p(f"objects {len(bpy.data.objects)}  materials {len(bpy.data.materials)}  "
      f"images {len(bpy.data.images)}  dirty {bpy.data.is_dirty}")

    gen = generated_images_without_pixels()
    if gen:
        problems.append(f"generated images with no pixel data (re-bake them): {gen}")
    miss = missing_image_files()
    if miss:
        problems.append(f"image files missing on disk AND not packed: {miss}")
    tmpimgs = unpacked_temp_images()
    if tmpimgs:
        p(f"note: {len(tmpimgs)} images point at a temp dir (packed, so safe now — repack into "
          f"assets/ before sharing the .blend): {tmpimgs[:4]}{' …' if len(tmpimgs) > 4 else ''}")
    slots = empty_material_slots()
    if slots:
        problems.append(f"empty material slots: {slots[:10]}{' …' if len(slots) > 10 else ''}")
    nomat = materials_without_output()
    if nomat:
        problems.append(f"materials with no output node: {nomat}")
    bad = bad_transforms()
    if bad:
        problems.append(f"bad transforms: {bad[:8]}")

    dups, ndup = duplicate_suffix_objects()
    if ndup:
        p(f"note: {ndup} objects have a .NNN suffix (duplicated rather than instanced/reused): "
          f"{dups}{' …' if ndup > len(dups) else ''}")

    users, uniq = instancing()
    p(f"mesh objects {users} sharing {uniq} unique meshes "
      f"(instancing ratio {users / max(1, uniq):.1f}x)")

    total, ranked = tri_report()
    p(f"render-visible tris {total:,}" + (f"  / budget {tri_budget:,}" if tri_budget else ""))
    for name, t in ranked:
        p(f"    {name:<24} {t:>10,}")
    if tri_budget and total > tri_budget:
        problems.append(f"tri budget exceeded: {total:,} > {tri_budget:,}")

    if expect_cameras:
        for name, xyz in expect_cameras.items():
            cam = bpy.data.objects.get(name)
            if cam is None:
                problems.append(f"camera '{name}' is missing")
                continue
            d = max(abs(a - b) for a, b in zip(cam.location, xyz))
            p(f"camera {name}: {tuple(round(v, 2) for v in cam.location)}  drift {d:.3f} m")
            if d > 0.01:
                problems.append(f"camera '{name}' moved by {d:.3f} m (it is meant to be fixed)")

    p("-" * 62)
    if problems:
        p(f"{len(problems)} PROBLEM(S):")
        for x in problems:
            p(f"  ! {x}")
    else:
        p("no problems found")
    p("=" * 62)
    return (not problems), problems
