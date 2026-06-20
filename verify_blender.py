"""End-to-end check for BlenderMCP: connects to the Blender addon's socket
server (port 9876) and asks for scene info. Run AFTER enabling the addon and
clicking 'Connect to Claude' in Blender's BlenderMCP sidebar.
"""
import socket
import json
import sys

HOST, PORT = "127.0.0.1", 9876


def send_command(cmd_type, params=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((HOST, PORT))
    s.sendall(json.dumps({"type": cmd_type, "params": params or {}}).encode("utf-8"))
    chunks = []
    while True:
        try:
            data = s.recv(8192)
        except socket.timeout:
            break
        if not data:
            break
        chunks.append(data)
        # responses are a single JSON object; stop once it parses
        try:
            json.loads(b"".join(chunks).decode("utf-8"))
            break
        except json.JSONDecodeError:
            continue
    s.close()
    return json.loads(b"".join(chunks).decode("utf-8"))


def main():
    try:
        resp = send_command("get_scene_info")
    except ConnectionRefusedError:
        print("FAIL: nothing is listening on 127.0.0.1:9876.")
        print("      Enable the 'Interface: Blender MCP' addon and click")
        print("      'Connect to Claude' in the BlenderMCP sidebar (press N).")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        sys.exit(1)

    if resp.get("status") == "success":
        info = resp.get("result", {})
        print("SUCCESS: Claude <-> Blender link is working end-to-end.")
        print(f"  Scene name   : {info.get('name')}")
        print(f"  Object count : {info.get('object_count')}")
        objs = info.get("objects", [])
        if objs:
            names = ", ".join(o.get("name", "?") for o in objs[:10])
            print(f"  Objects      : {names}")
    else:
        print(f"FAIL: Blender returned an error: {resp.get('message')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
