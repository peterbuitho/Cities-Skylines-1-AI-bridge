"""Record a fly-by video of the city along a route of camera keys.

Moves the game camera frame by frame through the mod, grabs the game window each frame and lets
ffmpeg join the frames. The game interface is hidden while recording; street names stay, because
the game draws them in the world when the camera is close. Record in daylight with the game paused.

Use: flyby.py <route.json> <out.mp4> [--fps 30]

route.json is a list of keys: {"t": seconds, "x":.., "z":.., "size": distance from the spot,
"bearing": compass direction the camera looks in (0 north, 90 east), "tilt": degrees below level}.
"""
import ctypes, ctypes.wintypes, json, os, shutil, subprocess, sys, tempfile, urllib.request

from PIL import Image

B = "http://127.0.0.1:32123"


def post(path, body):
    req = urllib.request.Request(B + path, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
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


def ease(u):
    return u * u * (3 - 2 * u)


def view_at(keys, t):
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            u = ease((t - a["t"]) / (b["t"] - a["t"]))
            turn = (b["bearing"] - a["bearing"] + 180) % 360 - 180   # the short way round
            mix = lambda k: a[k] + (b[k] - a[k]) * u
            return {"x": mix("x"), "z": mix("z"), "size": mix("size"), "bearing": (a["bearing"] + turn * u) % 360, "tilt": mix("tilt")}
    return {k: keys[-1][k] for k in ("x", "z", "size", "bearing", "tilt")}


def main():
    keys = json.load(open(sys.argv[1], encoding="utf-8"))
    out = os.path.abspath(sys.argv[2])
    fps = int(sys.argv[sys.argv.index("--fps") + 1]) if "--fps" in sys.argv else 30
    window = ctypes.windll.user32.FindWindowW(None, "Cities: Skylines")
    if not window:
        sys.exit("the game window was not found")
    # Behind every other window, without moving or activating it: the camera steps look jerky live,
    # and the grab does not need the window to be visible.
    ctypes.windll.user32.SetWindowPos(window, 1, 0, 0, 0, 0, 0x0013)
    frames = tempfile.mkdtemp(prefix="flyby_")
    count = int(keys[-1]["t"] * fps) + 1
    post("/commands/set-ui", {"visible": False})
    try:
        for i in range(count):
            v = view_at(keys, i / fps)
            post("/commands/set-camera", {"position": {"x": round(v["x"], 2), "z": round(v["z"], 2)}, "size": round(v["size"], 1),
                                          "rotation": round(v["bearing"], 2), "tilt": round(v["tilt"], 2)})
            grab(window).save(os.path.join(frames, f"{i:05d}.jpg"), quality=92)
            if i % 150 == 0:
                print(f"frame {i} of {count}", flush=True)
    finally:
        post("/commands/set-ui", {"visible": True})
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(frames, "%05d.jpg"),
                    "-vf", "scale=1920:-2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out], check=True)
    shutil.rmtree(frames)
    print("saved", out, f"({os.path.getsize(out) / 1e6:.0f} MB, {count / fps:.0f} s)")


if __name__ == "__main__":
    main()
