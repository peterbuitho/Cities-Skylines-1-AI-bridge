"""Measure how evenly the picture moves from frame to frame in a video.

For each pair of neighbouring frames it estimates how far the whole picture shifted (phase
correlation). A smooth camera gives shifts that change slowly; a jumpy one gives shifts that
alternate, for example 0, 8, 0, 8 when frames were grabbed twice or skipped.

Use: jitter.py <video> [start seconds] [length seconds]
Prints the shifts and one number: the typical change of shift between frames, in pixels at 480 px width.
"""
import subprocess, sys

import numpy as np

W, H = 480, 270


def main():
    video = sys.argv[1]
    start = sys.argv[2] if len(sys.argv) > 2 else "0"
    length = sys.argv[3] if len(sys.argv) > 3 else "6"
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", start, "-t", length, "-i", video, "-vf", f"scale={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)
    window = np.outer(np.hanning(H), np.hanning(W))
    shifts = []
    for a, b in zip(frames, frames[1:]):
        fa, fb = np.fft.fft2(a * window), np.fft.fft2(b * window)
        cross = fa * np.conj(fb)
        peak = np.abs(np.fft.ifft2(cross / (np.abs(cross) + 1e-6)))
        y, x = np.unravel_index(np.argmax(peak), peak.shape)
        shifts.append((x - W if x > W // 2 else x, y - H if y > H // 2 else y))
    s = np.array(shifts, dtype=float)
    size = np.hypot(s[:, 0], s[:, 1])
    change = np.hypot(*np.diff(s, axis=0).T)
    print("shift per frame (x,y):", " ".join(f"{int(x)},{int(y)}" for x, y in shifts[:60]))
    print(f"frames: {len(frames)}; mean shift {size.mean():.2f} px; typical change between frames {np.median(change):.2f} px; "
          f"worst {change.max():.1f} px; frames that did not move: {int((size == 0).sum())}")


if __name__ == "__main__":
    main()
