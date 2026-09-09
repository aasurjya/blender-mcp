# Blender MCP — Agent Operating Guide (this machine)

> **Start here:** `WORKFLOW_2D_TO_3D.md` is the process (reference image → measured spec →
> parametric build → probe → finals). `RETROSPECTIVE.md` is what went wrong across 13 passes and
> why the rules below exist. `tools/ref_match.py` scores a render against a reference image;
> `tools/verify_scene.py` is the pre-flight health check — run both before and after every change.

> Workspace layout (2026-09-08): everything lives under `D:\aasurjya\Blender\mcp\` — this bridge in
> `blender-mcp\` (with this folder at `blender-mcp\agentic\`), shared helpers in `agentic\tools\`
> (`launch_blender.ps1`, `check_mcp.ps1`, `blender_socket.py`, `ref_match.py`, `verify_scene.py`),
> templates in `templates\`, and one folder per blend project under `blend\<project>\` (blend files at the
> project root; `scripts\ specs\ refs\ renders\ assets\ exports\`; `PROJECT.md` = state file). See
> `..\README.md`. The Sail Tower project is `blend\sail_tower\` — MIGRATED 2026-09-08 (master
> `sail_tower.blend`, working copy `sail_tower_work.blend`, `scripts\build_pass3.py`, `specs\`, `renders\`).
> Wherever section 5 below says `D:\aasurjya\nex\gaussian-splats\blender\...` or `outputs\sail_tower\`,
> read `D:\aasurjya\Blender\mcp\blend\sail_tower\{scripts,renders}\` instead.

Read this before driving Blender through the MCP bridge. It captures how the system is
wired on this PC, the failure modes already hit, and the working method that produced the
Sail Tower model. `README.md` is the upstream project doc; this file is the local runbook.

## 1. What the pieces are

| Piece | Where | Role |
|---|---|---|
| MCP bridge (`blender-mcp.exe`) | `D:\aasurjya\Blender\mcp\blender-mcp\.venv\Scripts\blender-mcp.exe` (source in `src/blender_mcp/server.py`) | Launched by the Claude desktop app. Exposes `mcp__blender__*` tools. Connects to **localhost:9876** (`BLENDER_HOST`/`BLENDER_PORT` env override). |
| Blender addon | `%APPDATA%\Blender Foundation\Blender\5.1\scripts\addons\addon.py` (copy of `./addon.py`) | Legacy `bl_info` addon, module name `addon`. N-panel tab **BlenderMCP**, button **Connect to Claude** = operator `blendermcp.start_server`, binds `127.0.0.1:<scene.blendermcp_port>` (default 9876). |
| Blender | `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe` (5.1.0) | Must be running WITH GUI; the server refuses to start in `-b` background mode. |

Tools of note: `get_scene_info`, `get_object_info`, `execute_blender_code`, `render_scene`,
`get_viewport_screenshot`, `export_scene` (glb/fbx/obj/…), `export_gaussian_splat`,
`export_splat_training_data`, `bake_lightmaps`, `export_vr_fbx`, PolyHaven/Sketchfab/
BlenderKit/Hyper3D/Hunyuan helpers. Tools are deferred: load with
`ToolSearch "select:mcp__blender__execute_blender_code,mcp__blender__render_scene,..."`.

## 2. Bring-up (do this first, every session)

1. Check state from a shell:
   ```
   tasklist | findstr /i blender
   netstat -ano | findstr 9876
   ```
   Want: exactly ONE `blender.exe`, and one `LISTENING` line on `127.0.0.1:9876` owned by it.
2. If Blender is not running, launch it with the file AND auto-start the server:
   ```powershell
   Start-Process 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' -ArgumentList @(
     '"D:\path\to\file.blend"',
     '--python-expr', '"import bpy; bpy.ops.preferences.addon_enable(module=\"addon\"); bpy.ops.blendermcp.start_server()"')
   ```
   Wait ~20 s, re-run the netstat check, then call `mcp__blender__get_scene_info`.
3. If Blender is running but nothing listens on 9876, have the user paste in Blender's
   Python Console (Scripting workspace):
   ```python
   import bpy; bpy.ops.blendermcp.stop_server(); bpy.context.scene.blendermcp_port = 9876; bpy.ops.blendermcp.start_server(); s = bpy.types.blendermcp_server; print(s.port, s.running, s.socket)
   ```
   Diagnostic if still failing: `print(sys.platform, os.getpid(), bpy.app.binary_path, s.socket.getsockname())`
   and compare the PID with `tasklist`.

### Known failure modes (all seen on this machine)
- **"Could not connect to Blender. Make sure the Blender addon is running."** — the bridge
  is fine; the addon server inside Blender is not listening. Fix via step 2/3. Never
  conclude the MCP server is misconfigured.
- **Addon present but not enabled.** `addon.py` in the addons folder is not enough; it must
  be ticked in Preferences → Add-ons (legacy add-ons may be hidden behind the filter) or
  enabled with `bpy.ops.preferences.addon_enable(module="addon")`.
- **Stale server object.** `bpy.types.blendermcp_server` with `running=True` but a dead
  socket makes `start()` return early ("Server is already running"). `stop_server` then
  `start_server` clears it.
- **Two Blender instances both listening on 9876** (SO_REUSEADDR allows it). Connections
  then go to an arbitrary instance and the file on disk can be overwritten by the wrong
  one. Cause: an agent launched a second Blender. **Never launch Blender from an agent
  if one is already running** — check `tasklist` first. Kill the duplicate that was NOT
  opened by the user (`Get-CimInstance Win32_Process` shows each instance's command line
  and parent), keep the one the bridge is connected to (`os.getpid()` via
  `execute_blender_code`).
- **PC restart / Claude process restart.** Background agents die silently; the bridge
  `blender-mcp.exe` usually survives, Blender does not. Re-run bring-up, then check what the
  dead agent left on disk (render files, `.blend` mtime, build scripts) before relaunching.
- **Destructive datablock removals are now BLOCKED by the addon.** `execute_code` refuses code
  containing `bpy.data.{materials,meshes,images}.remove`, `orphans_purge`, `wm.open_mainfile` and the
  factory-reset ops. Prefer unlink/hide/rename or reuse-by-name; if a removal is genuinely required,
  save the file first and include the comment `# ALLOW_DESTRUCTIVE` in the code to opt in.
- **Blender hard crash (EXCEPTION_ACCESS_VIOLATION in `DepsgraphNodeBuilder::build_materials`).**
  Seen 2026-09-07 during pass 6: a material datablock was removed / orphan-purged while an
  object still referenced it (or the user was transforming objects in the viewport while the
  script rebuilt materials). Rule: **never call `bpy.data.materials.remove()` or
  `bpy.ops.outliner.orphans_purge()` mid-build**; reuse materials by name, and only purge as
  the very last step after `save_mainfile()`. Crash log: `%TEMP%\<blendname>.crash.txt`.
  Recovery: relaunch (step 2), the `.blend` saved before the crash reloads fine; check
  `material_slots` for `None` and `bpy.data.materials` for `users==0` before continuing.
- **BlenderKit search returns HTTP 400.** The addon sent `addon_version=3.12.0.240907`; the
  BlenderKit API now requires `X.X` or `X.X.X`. Fixed to `3.12.0` in both addon copies (2026-09-08).
  Enabling BlenderKit needs no reconnect: `scene.blendermcp_use_blenderkit = True` is read per
  command. A running server can be hot-patched by re-exec'ing the method source into the `addon`
  module and assigning it on `BlenderMCPServer`. SEARCH works without a key, but DOWNLOADS
  (`import_blenderkit_model`) return HTTP 403 without one even for free assets — a free
  blenderkit.com account key pasted into the N-panel (`scene.blendermcp_blenderkit_api_key`) is
  required; until then agents must fall back to procedural vegetation/props.
- **Bash tool is Git Bash (POSIX)** — `where`, `if exist`, `%VAR%` fail. Use
  `where.exe`, `tasklist.exe`, `netstat`, `find`, or call `powershell.exe -NoProfile -Command`.
  Sandbox may block loopback; add `dangerouslyDisableSandbox` for netstat/PowerShell checks.

## 3. Working method that produced good results

- **Small chunks.** Every `execute_blender_code` call must finish in < ~20 s or the bridge
  times out. Build one subsystem per call; print numbers back.
- **Keep the build in a script, not the console.** Generators live in a `.py` next to the
  `.blend`; import with
  `sys.path.append(r"D:\...\blender"); import sail_tower_lib as L; importlib.reload(L)`.
  Edit the file with the Edit tool, reload, delete objects by name, regenerate. Pass 1 had
  no script and was unreproducible; from pass 2 on, `build_passN.py` with `build_all()`.
- **Render → Read → measure → iterate.** After each step `render_scene` to a numbered PNG
  and view it with the Read tool. Do not trust "looks about right": measure with
  `bpy_extras.object_utils.world_to_camera_view` (apex/base/horizon positions), BVH overlap
  tests between solids (must be 0 faces), luminance/hue samples of the rendered image via
  `bpy.data.images.load` + numpy (clip max, core-vs-shell ratio).
- **Multiple cameras.** Front-only matching drifted badly. Keep `Cam_Ref` (front, never
  moved once solved) plus `Cam_SideL/SideR/Rear/Aerial` and re-render all after any geometry
  change — the design sheet has 10 views; check each claim against the view that shows it.
- **Reference images cannot be read from chat by subagents.** Either save the image to disk
  (ask the user for the exact path) or translate it into numbers: normalise silhouette
  landmarks to frame coordinates and convert with the frame width in metres
  (here 1.0 frame width ≈ 347 m at Cam_Ref). Write those numbers into the agent brief.
- **Briefs must be self-contained and numeric.** Coordinate frame (z up, camera looks +y,
  image-right ≈ +x), object names, material names, file paths, target dimensions, acceptance
  tests per view, hard rules (no second Blender, retry on connection error, save after each
  step, tri budget), and the report format.
- **One agent at a time on Blender.** Two agents in one session collide. Stop the previous
  agent (`TaskStop`) before launching a new one; check what it left behind first.
- **Save often.** `bpy.ops.wm.save_mainfile()` after every successful step; Blender keeps
  `.blend1` as the previous version.
- **Specs can be mutually exclusive.** Ribbons on one cylinder radius can't both hug the
  core and stand 60 m out — when an agent reports a conflict, resolve it with an
  asymmetric/per-object schedule rather than forcing a number.

## 4. Blender 5.1 API gotchas
- Compositor was rebuilt (`scene.compositing_node_group`; old node names gone) — avoid it.
- `mesh.use_auto_smooth` removed → set `polygon.use_smooth` + "Smooth by Angle" modifier.
- Principled BSDF input names: `'Transmission Weight'`, `'Emission Color'`,
  `'Emission Strength'`, `'Coat Weight'`.
- `scene.eevee.use_bloom` gone; Musgrave texture gone (use Noise).
- EEVEE screen-space refraction can't show geometry behind glass — put "interior" emissive
  strips flush with the glass surface.
- Lights: set `visible_camera=False` and, for accent lights, `specular_factor=0` — a
  sun/area glint on a large water plane renders as a huge glow "halo".
- Z-fighting between coplanar slabs (paths/plaza/road) renders as dark shards.
- **Ruled surfaces between two helical edges crease.** Joining the lead/trail edges with a straight
  chord (`_surface`) makes a flat plank at every height whose silhouette hands over from one edge to
  the other with a slope step of w·dθ/dz → a visible fold where the band turns edge-on (pass 7–9).
  Build the band ON the helix cylinder instead (`helix_surf()` in build_pass3.py, pass 10); verify with
  a monotone silhouette-slope check, not just curvature of the centre-line.
- **Measure before re-modelling.** Pass 11: the "claw / bundle of pipes" at the ribbon→strand split was
  not geometry — a real cross-section (constant guide parameter, not per-strand arc length) showed the
  gaps were already tiny; the look came from an LED line on BOTH edges of EVERY strand bracketing each
  slot with two bright rims. Lighting only the sheet's outer edges until slots exceed 1 m fixed it.
- **glTF/GLB export lessons (pass 12).** Export from a dedicated "Export" scene with
  `use_active_scene=True` — otherwise the whole working scene rides along as a second glTF scene.
  Objects hidden only via `visible_camera=False` STILL EXPORT (use hide_render/exclude or delete the
  copies). glTF has no AREA lights (only sun/point/spot), no world/HDRI, no volumetrics; procedural
  node trees (noise, Object-Position PBR, Fresnel alpha) do not travel — bake to images or swap to
  image textures; UV-math alpha (palm fronds) can be evaluated into an RGBA image. Verify by
  re-importing into an empty scene and rendering (`renders\pass12_glb_check_front.png`).
- **Generated images are not saved in the .blend.** `bpy.data.images.new(...)` + pixels
  (e.g. the `MullionGrid` texture) comes back solid black after a reload → glass renders as a
  black slab. Either `image.pack()` after filling pixels, or rebuild it on load
  (`fix_mullion_tex()` in build_pass3.py does this).
- `object.visible_camera` is GLOBAL, not per-camera. To hide objects for one camera only,
  tag them and toggle before each render (`apply_cam_vis(cam)` in build_pass3.py).
- Set `surface_render_method='DITHERED'` on glass materials in EEVEE Next; BLENDED breaks
  sorting with raytracing on.

## 5. Current project: Sail Tower (NexVR)

- Files: `D:\aasurjya\nex\gaussian-splats\blender\sail_tower.blend`,
  `sail_tower_lib.py` (generators), `build_pass3.py` (current end-to-end build, `build_all()`),
  `build_pass2.py` (older). Renders: `D:\aasurjya\nex\gaussian-splats\outputs\sail_tower\`
  (`passN_final_<view>.png`). Plan file used for the build:
  `C:\Users\ANT PC\.claude\plans\plan-it-well-create-tender-gizmo.md`.
- Concept (from the user's 10-view sheet): round steel-blue glass core (30×26 m, 262 m,
  centre (−6,+4)) wrapped by two white vertically-fluted ribbons that spiral ~180° around it
  (B = A + 180°, crossing at z≈152 → X in side views), closing in one fin at apex (1,0,300);
  outer ribbon A bows out to R≈50 m at z 130, inner ribbon B hugs at R≈22; feet flare
  horizontally onto a louvered S-swoosh podium (165 m, 5→24 m tall, 19 fins at 1.3 m);
  plaza with lawns/palms, rock breakwater seaward (+y), 6-lane highway landward (−y).
- Camera `Cam_Ref` (−94.76, −472.39, 71), 50 mm, shift_y 0.20: apex ndc 0.590/0.961.
- Acceptance numbers used: ribbon max pixel < 0.88–0.90; core/ribbon mean luminance
  0.45–0.55 with R < B; ribbon/ribbon overlap 0 faces; tris < 450k (currently ~220k).
- End use: render + GLB export for web/VR (Principled + image textures only; transmission
  exports as KHR_materials_transmission), optional `export_splat_training_data` for 3DGS.
- Status log: pass 1 proportions/camera; pass 2 mood/ribs/glow; pass 3 helical ribbons,
  round core, site plan; pass 4 ribbons hug core, artefacts fixed; pass 5 asymmetric bow,
  glass core; pass 6 materials/detail/context DONE (finals `pass6_final_*.png`, 297k tris;
  `build_pass3.py` must be exec'd before re-rendering other cameras — `apply_cam_vis` and
  `fix_mullion_tex` live only in the script). Pass 7 (2026-09-08, Opus, working copy
  `sail_tower_base.blend`): open crown (A tip z 300, B tip z 284, no needle), observation deck +
  helipad + sky-lobby drum (`build_crown()`), inner-edge lighting lines, `gsmooth` C2 schedules,
  `set_cam()` replaces the broken `apply_cam_vis`. Pass 8 (in progress): "curves into ground" base
  per `blender/base_spec_v3_curves_into_ground.txt` — ribbons split into strands that loop into the
  landscape; replaces the Astra concentric-ring base. Passes 8b–12 (2026-09-08, Opus, in
  `blend\sail_tower\`): asymmetric strand knot, strands lying on the landscape (0 legs), cylindrical
  ribbon shells (fold fixed), white-balanced lighting, real HDRI sky, PBR ground, procedural palms v3,
  Aurora entrance (bands, lobby, doors, pools, monolith), planting 64 %, `build_all()` reproduces the
  scene in ~10 s. **GLB exported: `blend\sail_tower\exports\sail_tower.glb` (33.4 MB).** Master
  `sail_tower.blend` is still the pass-6 state — promote `sail_tower_work.blend` only with user approval.
- Alternative code-writers under evaluation via the Experiential Labs gateway
  (`blender/astra_client.py`, key in env `EXPLABS_API_KEY`, endpoint OpenAI-compatible
  `/v1/chat/completions`): `gpt-6-astra-pro` (works, ~$0.75 per 400-line script;
  `gpt-6-astra` is geo-blocked here), `glm-5.3`, `kimi-k3`. GLM/Kimi are thinking models:
  without `"reasoning_effort":"low"` (or `"thinking":{"type":"disabled"}`) they burn the whole
  `max_tokens` on hidden reasoning and return nothing (`finish_reason=length`, empty content);
  pass it via `--extra`. `/v1/models` is slow (~90 s) — use a long timeout.
  **Results (2026-09-07, identical numeric ribbon task, renders `outputs\sail_tower\cmp_*_front.png`):**
  `gpt-6-astra-pro` — ran first time, 0.3 s, 85k tris, $0.85, visually near the Opus result (smooth
  PCHIP curves, correct apex closure, slightly weaker glow/fluting). `kimi-k3` (low effort) — ran first
  time, 0.2 s, 74k tris, $0.10, correct topology but kinked curves and a stub foot. `glm-5.3` (low
  effort) — four successive bpy API errors (`BMFace.use_smooth`, `'SMOOTH_BY_ANGLE'` modifier,
  `bpy.data.node_trees`, `GeometryNodeGroupOutput`), and once patched the ribbon widths collapsed to
  wires with the apex overshooting to z 309 — not usable for Blender code. Verdict: Astra-pro is a
  viable one-shot geometry writer for a fully numeric spec. **Autonomous judge→revise loop test
  (`blender/astra_loop.py`, 5 iterations, $5.59, 2026-09-08): Astra-pro REGRESSED the model** — it
  deleted the fluting, shrank the warm edge line to 0.07 m while complaining it was faint, left the
  kinks, and turned the foot into a flat blade; 2 of 5 iterations crashed on its own API errors.
  Conclusion: use Astra-pro for spec→code (attach the generators and a numeric brief every call —
  requests are stateless), keep Opus agents for render→judge→revise. Result saved separately as
  `blender/sail_tower_astra.blend`; the pass-6 master was never touched — always work on a
  `save_as_mainfile` copy when an external model drives Blender.
  Gateway is PREPAID: it returned `insufficient_quota` (balance −$0.33) after ~$10 of use on
  2026-09-08 (autonomous loop $5.59, base build $2.45 — attaching both generator scripts made
  the prompt 125k tokens). Check `/api/whoami` + balance before multi-call loops; attach only
  the files the task needs. `bpy.ops.wm.open_mainfile(filepath=..., load_ui=False)` over the socket works and keeps the MCP
  connection alive (the server object lives in `bpy.types`). Test protocol: same task file,
  build into collection `AstraTest`, render from Cam_Ref with the Opus ribbons hidden,
  compare, then delete the collection.

## 6. User preferences that apply here
- No compromise on quality; use Opus for the heavy modeling/shader passes and iterate
  rather than settle. Show renders (SendUserFile) after every pass with an honest
  angle-by-angle comparison against the reference.
