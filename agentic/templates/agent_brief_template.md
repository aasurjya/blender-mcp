# Agent brief template (Opus pass / Astra spec-to-code)

Copy, fill every bracket, keep it numeric. Subagents are stateless: everything they need must be here.

## Session facts
- Blender <version> PID <pid> connected on 127.0.0.1:9876. Never launch another Blender; on a connection
  error wait 5 s and retry. You are the ONLY process touching Blender; no sub-agents on Blender.
- Working file: `projects/<project>/blend/<project>_work.blend` (save after each step; never overwrite the
  master `<project>.blend`). Scripts: `projects/<project>/scripts/` (import with sys.path + importlib.reload).
- Safety: never remove materials/meshes/images or purge orphans; re-fetch objects by name after deletes;
  generated images are not saved (rebuild or pack them); `visible_camera` is global.
- Frame: z up; <camera name> looks toward <axis>; image-right = <axis>; units metres.

## Scope
- Objects you OWN: <names/patterns>. Objects you must NOT touch: <names/patterns> (owned by another pass).
- Cameras: <Cam_Ref never moved; verification cameras and their positions>.

## Reference (numbers, not adjectives)
- Silhouette landmarks in frame coordinates and metres (frame width = <N> m at <camera>).
- Dimensions per element; materials with RGB/roughness/emission values; light positions and strengths.
- Reference image files: `projects/<project>/refs/<file>` (Read them; the user cannot paste images to you).

## Fix list (each item verifiable)
1. <what is wrong now> -> <target value> ; verify by <measurement / view>.
2. ...

## Verification
- Render <cameras> after each step to `renders/pass<N>_<view>_<NN>.png` and Read them.
- Numeric checks: <apex ndc, overlap test = 0 faces, clip max < 0.90, luminance ratios, tri budget>.

## Deliverables
- Finals `renders/pass<N>_final_<view>.png`; saved working .blend; `scripts/build_pass<N>.py` runnable
  end-to-end; report (< 350 words): per item what changed, measured numbers, remaining deviations, paths.
