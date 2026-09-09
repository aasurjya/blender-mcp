# agentic/ — running Blender as an AI-driven modelling pipeline

Everything here came out of building a 300 m parametric tower from reference images through the
Blender MCP bridge, over 13 agent passes. It is the process, the guard rails and the measurement
tools that project needed and did not have.

| File | What it is |
|---|---|
| `WORKFLOW_2D_TO_3D.md` | **The process.** Reference image → measured spec → parametric build → probe → finals. Read first. |
| `RETROSPECTIVE.md` | What actually went wrong, with the cost and the fix. Read before repeating any of it. |
| `AGENT_GUIDE.md` | Machine-specific runbook: bring-up, failure modes, Blender 5.1 API gotchas, glTF export lessons. |
| `WORKSPACE.md` | Folder layout for a multi-project Blender MCP workspace. |
| `tools/ref_match.py` | Scores a render against a reference image: apex offset, skyline RMS in metres, per-band error table. Runs inside Blender. |
| `tools/verify_scene.py` | Pre-flight health check: unpacked/missing textures, empty material slots, camera drift, tri budget, instancing ratio. |
| `tools/blender_socket.py` | Minimal client for the addon socket — run code or render without the MCP bridge. |
| `tools/launch_blender.ps1` | Start Blender on a file with the server up; refuses to start a second instance. |
| `tools/check_mcp.ps1` | Is Blender up, is 9876 listening, which PID, which file, are there duplicate listeners. |
| `templates/project_skeleton/` | Copy to `blend/<project>/` to start a new model. |
| `templates/agent_brief_template.md` | How to brief a modelling pass so it is checkable. |

## The two rules that matter most

1. **Measure before you re-model.** Three separate passes rebuilt geometry that was not the problem.
2. **The script is the truth, the scene is a cache.** Every pass ends with `build_all()` and an
   object-count delta of 0.

## Quick start

```powershell
powershell -File tools\launch_blender.ps1 -Blend "D:\...\blend\my_project\my_project_work.blend"
powershell -File tools\check_mcp.ps1
```

```python
# inside Blender, via the MCP bridge or tools/blender_socket.py
import sys; sys.path.append(r"D:\...\blender-mcp\agentic\tools")
import verify_scene, ref_match
verify_scene.run(expect_cameras={"Cam_Ref": (-94.76, -472.39, 71.0)}, tri_budget=1_600_000)
ref_match.report(ref=r"...\refs\front.png", render=r"...\renders\front.png", frame_width_m=347.0)
```
