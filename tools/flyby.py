"""Record a fly-by video of the city along a route of camera keys.

Moves the game camera frame by frame through the mod, grabs the game window each frame and lets
ffmpeg join the frames. The game interface is hidden while recording; street names stay, because
the game draws them in the world when the camera is close. Record in daylight with the game paused.

Use: flyby.py <route.json> <out.mp4> [--fps 60]

route.json is a list of keys: {"t": seconds, "x":.., "z":.., "size": distance from the spot,
"bearing": compass direction the camera looks in (0 north, 90 east), "tilt": degrees below level}.

What keeps the result smooth:
- the path is a spline through the keys, so the camera never stops and starts at a key;
- the height of the spot looked at is smoothed, so the camera does not bob over bumps in the ground;
- each frame is grabbed only after the game has drawn the new view.
"""
import ctypes, ctypes.wintypes, json, os, shutil, subprocess, sys, tempfile, urllib.request

from PIL import Image

B = "http://127.0.0.1:32123"


def post(path, body):
    req = urllib.request.Request(B + path, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(B + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def grab(window):
    """The window's own picture, also when another window covers it (PrintWindow, full content)."""
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(window, ctypes.byref(rect))
    width, height = rect.right, rect.bottom
    window_dc = user32.GetDC(window)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)
    user32.PrintWindow(window, memory_dc, 3)   # client area only, rendered by the compositor
    header = (ctypes.c_uint32 * 10)(40, width, ctypes.c_uint32(-height).value, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    pixels = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory_dc, bitmap, 0, height, pixels, header, 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory_dc)
    user32.ReleaseDC(window, window_dc)
    return Image.frombuffer("RGB", (width, height), pixels, "raw", "BGRX", 0, 1)


def unwrap(keys):
    """Bearings as one continuous run of degrees, always turning the short way to the next key."""
    out = [dict(keys[0])]
    for key in keys[1:]:
        turn = (key["bearing"] - out[-1]["bearing"] + 180) % 360 - 180
        out.append(dict(key, bearing=out[-1]["bearing"] + turn))
    return out


def spline(keys, name, t):
    """Catmull-Rom through the keys' values at their own times: smooth speed through every key."""
    i = max(k for k in range(len(keys) - 1) if keys[k]["t"] <= t) if t < keys[-1]["t"] else len(keys) - 2
    p0, p1, p2, p3 = (keys[min(max(j, 0), len(keys) - 1)] for j in (i - 1, i, i + 1, i + 2))
    span = p2["t"] - p1["t"]
    u = (t - p1["t"]) / span
    # slopes from the neighbours; zero at the two ends of the route
    m1 = (p2[name] - p0[name]) / (p2["t"] - p0["t"]) * span if p2["t"] != p0["t"] else 0.0
    m2 = (p3[name] - p1[name]) / (p3["t"] - p1["t"]) * span if p3["t"] != p1["t"] else 0.0
    return ((2 * u**3 - 3 * u**2 + 1) * p1[name] + (u**3 - 2 * u**2 + u) * m1 +
            (-2 * u**3 + 3 * u**2) * p2[name] + (u**3 - u**2) * m2)


def camera(view, height=None):
    body = {"position": {"x": round(view["x"], 2), "z": round(view["z"], 2)}, "size": round(view["size"], 1),
            "rotation": round(view["bearing"] % 360, 2), "tilt": round(view["tilt"], 2)}
    if height is not None:
        body["height"] = round(height, 2)
    return post("/commands/set-camera", body)


def main():
    keys = unwrap(json.load(open(sys.argv[1], encoding="utf-8")))
    out = os.path.abspath(sys.argv[2])
    fps = int(sys.argv[sys.argv.index("--fps") + 1]) if "--fps" in sys.argv else 60
    window = ctypes.windll.user32.FindWindowW(None, "Cities: Skylines")
    if not window:
        sys.exit("the game window was not found")
    # Behind every other window, without moving or activating it: the camera steps look jerky live,
    # and the grab does not need the window to be visible.
    ctypes.windll.user32.SetWindowPos(window, 1, 0, 0, 0, 0, 0x0013)

    count = int(keys[-1]["t"] * fps) + 1
    views = [{name: spline(keys, name, i / fps) for name in ("x", "z", "size", "bearing", "tilt")} for i in range(count)]

    # ground height under the path, then a moving average over 1.5 seconds
    step = max(1, fps // 6)
    ground = [camera(views[i])["y"] for i in range(0, count, step)]
    ground = [ground[min(i // step, len(ground) - 1)] for i in range(count)]
    half = int(fps * 0.75)
    heights = [sum(ground[max(0, i - half):i + half + 1]) / len(ground[max(0, i - half):i + half + 1]) for i in range(count)]

    frames = tempfile.mkdtemp(prefix="flyby_")
    post("/commands/set-ui", {"visible": False})
    try:
        for i in range(count):
            drawn = camera(views[i], heights[i])["frame"]
            while get("/state/frame")["frame"] <= drawn:   # the view is on screen one frame later
                pass
            grab(window).save(os.path.join(frames, f"{i:05d}.jpg"), quality=92)
            if i % 300 == 0:
                print(f"frame {i} of {count}", flush=True)
    finally:
        post("/commands/set-ui", {"visible": True})
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(frames, "%05d.jpg"),
                    "-vf", "scale=1920:-2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out], check=True)
    shutil.rmtree(frames)
    print("saved", out, f"({os.path.getsize(out) / 1e6:.0f} MB, {count / fps:.0f} s)")


if __name__ == "__main__":
    main()
