"""Two motion versions of the dashboard for the README (GIF) and the Pages site (MP4).

Capture-only: showcase.js/.css are injected into the page here; the app ships no entrance
animation (DESIGN.md, MOTION 1). Frames are deterministic: every animation is paused and stepped
with currentTime at 30 fps, then ffmpeg builds a 15 fps GIF (palettegen/paletteuse) and an H.264 MP4.

    uv run python scripts/showcase/motion.py            # both variants
    uv run python scripts/showcase/motion.py cards-stagger
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from ui_screenshots import _serve  # noqa: E402

from dk_sales.web.settings import Settings  # noqa: E402

FPS = 30
VARIANTS = ["cards-stagger", "isometric-lift"]
GIF_DIR = ROOT / "docs/img"
VIDEO_DIR = ROOT / "site/media"


def capture(url: str, mode: str, frames_dir: Path) -> int:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, bypass_csp=True)
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_function("document.fonts.status === 'loaded'")
        page.add_style_tag(content=(HERE / "showcase.css").read_text())
        page.evaluate((HERE / "showcase.js").read_text())
        total = page.evaluate(f"window.__setup({mode!r})")
        n = int(total / 1000 * FPS)
        for i in range(n):
            page.evaluate(f"window.__seek({i * 1000 / FPS})")
            page.screenshot(path=frames_dir / f"f{i:04d}.png")
        b.close()
    return n


def encode(frames_dir: Path, mode: str) -> tuple[Path, Path]:
    gif = GIF_DIR / f"motion-{mode}.gif"
    mp4 = VIDEO_DIR / f"{mode}.mp4"
    poster = VIDEO_DIR / f"{mode}.jpg"
    src = ["-framerate", str(FPS), "-i", str(frames_dir / "f%04d.png")]
    run = lambda *a: subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)  # noqa: E731
    run(
        *src,
        "-vf",
        "fps=15,scale=1200:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle",
        "-loop",
        "0",
        str(gif),
    )
    run(*src, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30", "-preset", "slow", "-movflags", "+faststart", "-an", str(mp4))
    frames = sorted(frames_dir.glob("f*.png"))
    run("-i", str(frames[int(len(frames) * 0.6)]), "-q:v", "4", str(poster))
    return gif, mp4


def main() -> None:
    modes = [a for a in sys.argv[1:] if not a.startswith("--")] or VARIANTS
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    url = _serve(Settings(app_env="test", data_dir=Path(tempfile.mkdtemp()) / "var"))
    for mode in modes:
        frames = Path(tempfile.mkdtemp(prefix=f"frames-{mode}-"))
        n = capture(url, mode, frames)
        gif, mp4 = encode(frames, mode)
        print(f"{mode}: {n} frames, {gif.name} {gif.stat().st_size:,} B, {mp4.name} {mp4.stat().st_size:,} B, frames in {frames}")
        if "--keep" not in sys.argv:
            shutil.rmtree(frames, ignore_errors=True)


if __name__ == "__main__":
    main()
