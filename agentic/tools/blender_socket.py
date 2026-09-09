"""Minimal client for the BlenderMCP addon socket (no Claude bridge needed).

    python blender_socket.py "import bpy; print(bpy.data.filepath)"
    python blender_socket.py --file build.py            # run a script file inside Blender
    python blender_socket.py --render Cam_Ref out.png 1024 1024

Speaks the addon protocol: {"type": <command>, "params": {...}} -> {"status": ..., "result": {...}}.
"""

import json
import socket
import sys


def call(cmd_type, params=None, host="127.0.0.1", port=9876, timeout=900):
    s = socket.create_connection((host, port), timeout=timeout)
    s.sendall(json.dumps({"type": cmd_type, "params": params or {}}).encode())
    buf = b""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
        try:
            r = json.loads(buf.decode())
            s.close()
            return r
        except json.JSONDecodeError:
            continue
    s.close()
    return json.loads(buf.decode())


def run_code(code, **kw):
    r = call("execute_code", {"code": code}, **kw)
    if r.get("status") != "success":
        raise RuntimeError(r.get("message", str(r)))
    return r.get("result", {}).get("result", "")


def render(camera, path, w=1024, h=1024, samples=64):
    code = f"""
import bpy
sc = bpy.context.scene
prev = sc.camera
sc.camera = bpy.data.objects[{camera!r}]
sc.render.resolution_x, sc.render.resolution_y = {w}, {h}
sc.eevee.taa_render_samples = {samples}
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = {path!r}
bpy.ops.render.render(write_still=True)
sc.camera = prev
print('rendered', {path!r})
"""
    return run_code(code)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--file":
        print(run_code(open(a[1], encoding="utf-8").read()))
    elif a[0] == "--render":
        print(render(a[1], a[2], int(a[3]) if len(a) > 3 else 1024, int(a[4]) if len(a) > 4 else 1024))
    else:
        print(run_code(" ".join(a)))
