"""Point the game camera at a spot and save a picture of the game window.

Grabs the window's own picture, so the game does not have to be in front and is not brought there.

Use: screenshot.py <x> <z> <out.png> [--size 300] [--bearing 0] [--tilt 35] [--ui] [--full]
bearing is the compass direction the camera looks in; tilt is degrees below level.
The game interface is hidden for the picture unless --ui is given. Street and landmark names show
when the camera is near enough for the game to draw them (about --size 400 or less).
"""
import ctypes, sys, time

from flyby import get, grab, post


def option(name, default):
    return float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def main():
    x, z, out = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
    window = ctypes.windll.user32.FindWindowW(None, "Cities: Skylines")
    if not window:
        sys.exit("the game window was not found")
    show_ui = "--ui" in sys.argv
    if not show_ui:
        post("/commands/set-ui", {"visible": False})
    try:
        post("/commands/set-camera", {"position": {"x": x, "z": z}, "size": option("--size", 300),
                                      "rotation": option("--bearing", 0), "tilt": option("--tilt", 35)})
        time.sleep(1.5)   # let the game draw the new view
        if not show_ui:
            # With the interface hidden the game fades street names out. Giving the same view again as
            # an exact pose turns them back on, as flyby.py does. The game still only draws names near the camera.
            now = get("/state/camera")
            drawn = post("/commands/set-camera-pose", {"position": {"x": x, "z": z}, "size": option("--size", 300),
                                                        "rotation": option("--bearing", 0), "tilt": option("--tilt", 35), "eye": now["eye"],
                                                        "yaw": now["yaw"], "pitch": now["pitch"]})["frame"]
            while get("/state/frame")["frame"] <= drawn + 2:
                pass
        image = grab(window)
    finally:
        if not show_ui:
            post("/commands/set-ui", {"visible": True})
    if "--full" not in sys.argv:   # full size keeps the street names readable
        image = image.resize((image.width // 2, image.height // 2))
    image.convert("RGB").save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
