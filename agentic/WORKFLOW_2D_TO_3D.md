# Agentic 2D → 3D: turning a reference image into a parametric Blender model

The Sail Tower took 13 passes because this process did not exist and was reinvented each time.
Follow it in order. Each stage produces an artefact the next stage can check.

---

## 0. Intake — get the image onto disk

Chat images are invisible to subagents. **Save every reference to `<project>/refs/`** with a name
that says what it shows (`front_dusk.png`, `sheet_10view.png`, `entrance_aurora.png`), and list it in
`PROJECT.md`. Put the *path* in the agent brief — the Read tool accepts images, so the agent looks at
the sheet itself instead of at someone's paraphrase.

Prose specs still get written (stage 2), but as *measurements alongside the image*, never instead
of it.

## 1. Solve the camera before any geometry

Everything else is measured through the camera, so a camera that moves later invalidates every
number. Pick the reference's hero view, build one camera to match it, and freeze it (`Cam_Ref` by
convention — the guide's rule is that it never moves again).

Establish **scale**: find one dimension you know (a stated building height, a road width, a storey
at ~3.5 m) and derive *metres per frame width*. For the Sail Tower: 300 m tower spanning 0.865 of
frame height ⇒ 1.0 frame width ≈ 347 m. Record it in `PROJECT.md`; every probe uses it to report
errors in metres rather than pixels.

## 2. Measure the reference into numbers

Read landmark positions off the image in normalised frame coordinates (0–1 from the left / top) and
convert with the scale factor:

- apex / highest point, base line, horizon
- silhouette left and right edge at 4–8 heights
- major subdivisions (where a form splits, steps, or changes direction)
- material and lighting values: base colours, where the light comes from, what glows

Write this to `<project>/specs/<pass>_spec.txt` **as an acceptance test**, not as prose: each line
should be checkable ("A's left silhouette 55–60 m left of the apex line at z 100–150"), because
stage 5 will check them.

## 3. Build parametrically, in a script

Geometry lives in `<project>/scripts/build_*.py` with one function per subsystem and a `build_all()`
that reproduces the scene from scratch. Never model only in the live session: the scene is a cache,
the script is the truth. Every pass ends by running `build_all()` and reporting the object-count
delta — it must be 0.

## 4. Stage the work: plan → massing → detail

Check the *plan and massing* against the reference before adding any detail. Pass 8b caught a
symmetric-loops mistake at the plan stage, cheaply; pass 8 had already spent an hour detailing the
wrong plan. Render the cheap views (plan, aerial) first and only then commit to detailing.

## 5. Probe — make the match a number

```python
import sys; sys.path.append(r"...\agentic\tools")
import ref_match, verify_scene
verify_scene.run(expect_cameras={"Cam_Ref": (-94.76, -472.39, 71.0)}, tri_budget=1_600_000)
ref_match.report(ref=r"...\refs\front_dusk.png", render=r"...\renders\pass14_front.png",
                 frame_width_m=347.0, debug_png=r"...\renders\pass14_match.png")
```

`ref_match` reports apex offset, skyline RMS/max in metres, and a per-band table of where the
silhouette is wrong. `verify_scene` catches the cheap structural failures (missing textures,
empty material slots, camera drift, tri budget, instancing ratio).

Calibrate `tol` once per project against a landmark you know, and record it:

```python
ref_match.calibrate(r"...\renders\front.png", apex_uv=(0.590, 0.039))
```

## 6. Iterate against the number, not against opinion

An agent brief should name the probe and the target ("skyline RMS < 4 m, apex within 3 m"), so the
agent can tell on its own whether it improved anything. Reserve human review for design intent —
*is this the right building?* — not for measurement.

**Measure before you re-model.** Three passes rebuilt geometry that was already correct: the "claw"
was an LED-placement problem, the "fold" was the shell's chord construction, the "black box" was the
signage monolith standing in front of the doors. One measurement each would have found them.

## 7. Finalise

Cycles for finals (measured **faster** than EEVEE here: 84 s vs 160 s at 2048²/256 spp on an
RTX 5070 — do not assume), then GLB export from a dedicated Export scene, then the web/VR viewer.
The export gotchas are in `AGENT_GUIDE.md`; the short version is that procedural materials, world,
volumetrics and area lights do not travel, and objects hidden only via `visible_camera` still export.

---

## Which model for which job

Measured on identical tasks in this project:

| Job | Use | Evidence |
|---|---|---|
| Numeric spec → geometry code | a cheap strong coder is fine | `gpt-6-astra-pro` produced a 393-line generator that ran first time, $0.85 |
| Look at a render, decide what is wrong, revise | the strongest model you have | the same model, given this loop, deleted the fluting and flattened the foot over 5 iterations and was discarded |
| Blender API-heavy work | a model that actually knows `bpy` | `glm-5.3` emitted four successive API errors (`BMFace.use_smooth`, `SMOOTH_BY_ANGLE`, `bpy.data.node_trees`, `GeometryNodeGroupOutput`) |

## Anti-patterns

- Paraphrasing an image into prose and then building from the paraphrase.
- Re-modelling before measuring.
- Letting the live scene drift ahead of the script.
- Comparing this pass's number against a gate whose definition changed.
- One agent run that does plan, massing, detail and finals without a checkpoint.
- Assuming a renderer is faster without timing it.
