# What actually went wrong — 13 agentic passes, one 300 m tower

Written 2026-09-09 from the Sail Tower build (`blend/sail_tower/PROJECT.md` has the per-pass log).
Every problem below cost real time or a real regression. This file exists so the next project does
not re-pay for the same lessons; the fixes are in `AGENT_GUIDE.md`, `WORKFLOW_2D_TO_3D.md` and
`tools/`.

---

## 1. The reference image never reached the agent (the biggest one)

The user pasted design sheets into chat. Subagents cannot see chat images, so the orchestrator
hand-translated each sheet into numeric prose ("apex at 0.59 of frame width, podium base 0.903…").
`refs/` sat empty for the whole project.

**Cost.** Every design change went through one lossy human-language bottleneck. Three passes
targeted the wrong thing because the prose was an interpretation, not the image: the base was built
as concentric rings when the sheet showed an S-swoosh (pass 8, discarded); the ribbons were built as
flat shells beside an almond core for six passes before the side views showed they should wrap
helically; the "curves into ground" sheet changed the whole base concept at pass 8b.

**Fix.** Save every reference to `<project>/refs/` as a file and put the *path* in the brief — the
Read tool accepts images, so the agent can look at the actual sheet. Prose specs stay, as
measurements, not as a substitute. See `WORKFLOW_2D_TO_3D.md`.

## 2. Nothing measured "does this match the reference?"

Each pass invented ad-hoc gates. There was no number for the only question that mattered.

**Cost.** Agreement was judged by eye, in chat, one round-trip at a time — 13 passes and roughly
20 hours of agent runtime, much of it converging on shape.

**Fix.** `tools/ref_match.py` — renders and reference go in, a skyline profile comparison comes out:
apex position, per-band silhouette edges, RMS error in metres, and *where* the error is. An agent can
now iterate against a falling number instead of asking a human whether it looks better.

## 3. Agents "fixed" things that were not broken

Three separate passes mis-diagnosed, because they re-modelled before measuring:

| Symptom | Assumed cause | Actual cause (found by measuring) |
|---|---|---|
| Bundle-of-pipes "claw" at the split | strand geometry | an LED line on *both* edges of *every* strand bracketing each slot |
| Fold in the outer ribbon | twist schedule | the shell was built from straight chords between two helical edges → a flat plank at every height |
| Black box at the entrance | door geometry | the signage monolith parked 24 m in front of the glass |

**Fix.** Measure-first is now rule 1 of the brief template, and `tools/verify_scene.py` gives the
cheap measurements (counts, gates, health) before anything is rebuilt.

## 4. A destructive call crashed Blender and cost a session

`bpy.data.materials.remove()` on a material still referenced by objects →
`EXCEPTION_ACCESS_VIOLATION` in `DepsgraphNodeBuilder::build_materials`. The agent died with the
process, mid-build.

**Fix.** Now blocked in the addon itself (`execute_code` refuses the known-fatal removals unless the
caller writes `# ALLOW_DESTRUCTIVE`). This is the one guard rail that belongs in the server, not in a
prompt, because a prompt rule only works until an agent forgets it.

## 5. Generated images silently vanish

`MullionGrid` is created with `bpy.data.images.new()`. Blender does not store generated pixels in the
`.blend`, so after a reload the core rendered as a featureless black slab — through a whole set of
"final" renders before anyone noticed.

**Fix.** `verify_scene.py` flags generated images with no pixel data; the build script re-bakes them
on load (`fix_mullion_tex()`).

## 6. Scene and script drift apart

Agents made live tweaks in the session and did not always write them back. Pass 9 admitted a fresh
`build_all()` "won't be pixel-identical". The scene became the source of truth instead of the code —
the thing the whole parametric approach exists to avoid.

**Fix.** Every pass must end by running `build_all()` and reporting the object-count delta. Pass 13
reached delta 0. Keep it there.

## 7. Stale gates, incomparable numbers

`probe_split` still fails a curvature gate written in pass 9 that pass 10 knowingly superseded when
the shell geometry changed. Pass 9's clip-max mask counted emissive strips; pass 10's did not — the
numbers were compared anyway.

**Fix.** Gates live in one registry with the pass that set them and *why*; when a gate is superseded,
retire it in the same commit. `verify_scene.py` prints the table.

## 8. Long, expensive, uninterruptible runs

Passes ran 20 min to 2.4 h. A wrong premise at minute 5 was still burning tokens at minute 90.

**Fix.** Stage the work: cheap preview renders and probes first, the plan checked against the
reference *before* detailing (pass 8b's plan check caught the symmetric loops early — that is the
pattern to repeat), finals last.

## 9. Model choice: one clear result

`gpt-6-astra-pro` wrote excellent one-shot geometry from a numeric spec (393 lines, ran first time,
$0.85). Given the render→judge→revise loop it **regressed the model** — deleted the fluting, shrank
the glow line while reporting it was too faint, flattened the foot; 5 iterations, $5.59, discarded.
`glm-5.3` produced four successive bpy API errors and unusable geometry. `kimi-k3` was cheap and
rough.

**Fix.** Spec→code can be delegated to a cheap model. Judging a render and deciding what to change
stays with the strongest model available. Do not confuse the two.

## 10. Structural gaps still open in the model

- **No UVs.** Materials are driven from world-space position. Fine for these renders, but it blocks
  baking, lightmaps, LODs and any downstream pipeline — and it is why the GLB export needed textures
  baked specially.
- **No panelisation.** The sails are one flawless surface; a real 300 m shell has panel joints,
  expansion gaps and fixings. This is the top remaining tell against photorealism.
- **Entourage.** People and cars are procedural primitives. BlenderKit has good free ones but
  downloads need an account key (403 without); PolyHaven has no people or cars.
- **Surface model only.** No floor plates, core or structure — not an architectural deliverable.

## 11. Tooling friction (all fixed, listed so it stays fixed)

- Two Blender instances both bound port 9876 (SO_REUSEADDR) and commands went to an arbitrary one →
  `check_mcp.ps1` warns; `launch_blender.ps1` refuses to start a second.
- BlenderKit search returned HTTP 400 for every query — the addon sent a 4-part `addon_version`
  the API rejects. One-character class of bug, invisible until someone read the response body.
- `visible_camera=False` hides an object from the viewport render but it **still exports** to glTF —
  two grey slabs across the hero view of the first GLB.
- glTF exported the entire working scene as a second scene until `use_active_scene=True` was set
  (44.7 MB → 31.9 MB).
- EEVEE was assumed faster than Cycles for the whole project. Measured at the end: **Cycles 84 s vs
  EEVEE 160 s** at 2048²/256 spp on this GPU, and better. Assumption cost 12 passes of worse output.

---

## The one-line version

The model improved fastest when something was **measured**, and slowest when something was
**described**. Every fix above moves a judgement from prose into a number a machine can check.
