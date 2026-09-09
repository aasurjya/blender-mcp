# Blender MCP workspace

Single root for everything an AI agent needs to drive Blender on this machine: the MCP bridge,
the Blender addon, shared tools, and — under `blend\` — one folder per blend project holding its
.blend files, scripts, specs, references, renders, assets and exports.
Reuse this layout for any new AI application: copy `templates\project_skeleton\` to
`blend\<new_project>\` and start from its `PROJECT.md`.

```
D:\aasurjya\Blender\mcp\
├── README.md                  <- this file (layout + rules)
├── blender-mcp\               <- the MCP: bridge server (src/), addon.py, .venv, AGENT_GUIDE.md runbook
├── tools\                     <- shared helpers, project-independent
│   ├── launch_blender.ps1     start Blender on a .blend with the MCP server auto-started
│   ├── check_mcp.ps1          is Blender up? is 127.0.0.1:9876 listening? which PID? which file?
│   ├── blender_socket.py      tiny Python client for the addon socket (execute_code / render)
│   └── migrate_sail_tower.ps1 one-off: moves the sail_tower project from nex\gaussian-splats here
├── templates\
│   ├── project_skeleton\      empty project tree + PROJECT.md template
│   └── agent_brief_template.md how to brief an Opus/Astra pass (numeric spec, checks, rules)
└── blend\                     <- BLEND FILES: one folder per project
    └── <project>\
        ├── <project>.blend        MASTER — only touched by approved passes
        ├── <project>_work.blend   working copy the agents edit and save
        ├── <project>_<exp>.blend  experiments / archives (e.g. sail_tower_astra.blend)
        ├── PROJECT.md             state file: concept, cameras, acceptance numbers, pass log, next step
        ├── scripts\               parametric generators + build_passN.py (always runnable end-to-end)
        ├── specs\                 design briefs / measured reference descriptions per pass
        ├── refs\                  reference images the user supplied (agents Read them from here)
        ├── renders\               passN_<view>_NN.png, passN_final_<view>.png, cmp_*.png
        ├── assets\                HDRIs, textures, imported models (PolyHaven / BlenderKit copies)
        └── exports\               glb / fbx / splat training data
```

## Rules for agents (details in `blender-mcp\AGENT_GUIDE.md`)
1. One Blender instance, one agent on it at a time. Check `tools\check_mcp.ps1` before launching.
2. Work on `blend\<project>\<project>_work.blend`; promote to the master only after the user approves a pass.
3. Every geometry change lives in `scripts\` (no console-only edits); `build_passN.py` must rebuild the
   scene from scratch. Save after each successful step.
4. Render -> Read -> measure -> iterate; keep the acceptance numbers in `PROJECT.md` current.
5. Never remove materials/meshes/images or purge orphans mid-build (crashes the depsgraph).
6. Reference images go in `refs\` — subagents cannot see chat images.
7. Paths in scripts are relative to the project root (`blend\<project>\`):
   `ROOT = Path(__file__).resolve().parents[1]`; blends at `ROOT`, renders at `ROOT/renders`, etc.
