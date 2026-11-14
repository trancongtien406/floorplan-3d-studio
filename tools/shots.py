"""Render README / portfolio media with headless Chrome (SwiftShader WebGL, no GPU needed).

    npm run dev &            # http://127.0.0.1:5180
    python3 tools/shots.py   # needs `pip install playwright` + Chrome (or set --chrome)

Writes docs/*.png, docs/walkthrough-*.mp4, docs/orbit-*.mp4 and checks the GLB / PNG exports really download.
"""
import argparse
import shutil
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
PLANS = ["studio", "twobed", "townhouse"]


def ff(*a):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *a], check=True)


def st(page, js, wait=1800):
    page.evaluate(f"(() => {{ const s = __store.getState(); {js} }})()")
    page.wait_for_timeout(wait)


def load(page, i):
    st(page, f"s.loadPlan({i}); s.select(null);", 2200)


HIDE = ".layoutbar,.viewbar,.pane-tag,.walkhint{visibility:hidden!important}"


def canvas_shot(page, path):
    box = page.locator("canvas").first.bounding_box()
    page.evaluate(f"(() => {{ const s = document.createElement('style'); s.id = '__hide'; s.textContent = '{HIDE}'; document.head.appendChild(s); }})()")
    page.screenshot(path=str(path), clip=box)
    page.evaluate("document.getElementById('__hide')?.remove()")


def frames(page, path_mp4, js_for_t, seconds, fps=24, size=None):
    tmp = DOCS / "_frames"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    n = int(seconds * fps)
    for i in range(n):
        page.evaluate(js_for_t(i / fps))
        page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        canvas_shot(page, tmp / f"{i:04d}.png")
    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2" if not size else f"scale={size}"
    ff("-framerate", str(fps), "-i", str(tmp / "%04d.png"), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", str(path_mp4))
    shutil.rmtree(tmp)


def stills(page):
    # 1. hero: split editor (2-bed, modern)
    st(page, "s.setLayout('split'); s.setView('dollhouse');", 2500)
    page.screenshot(path=str(DOCS / "app-split-2bed.png"))

    # 2. each demo plan: dollhouse / iso / top (3D only layout)
    st(page, "s.setLayout('3d');", 1500)
    for i, pid in enumerate(PLANS):
        load(page, i)
        for v in ("dollhouse", "iso", "top"):
            st(page, f"s.setView('{v}')", 2600)
            canvas_shot(page, DOCS / f"{pid}-{v}.png")
        st(page, "s.setView('walk')", 1500)
        page.evaluate("__three.setTour(0.6)")
        page.wait_for_timeout(1200)
        canvas_shot(page, DOCS / f"{pid}-walk.png")
        page.evaluate("__three.setTour(null)")
    page.screenshot(path=str(DOCS / "app-3d-townhouse.png"))

    # 3. style presets on the 2-bed (dollhouse) -> 2x2 collage
    load(page, 1)
    st(page, "s.setView('dollhouse')", 1500)
    for sid in ("modern", "scandinavian", "japandi", "industrial"):
        st(page, f"s.setStyle('{sid}')", 2600)
        canvas_shot(page, DOCS / f"style-{sid}.png")
    st(page, "s.setStyle('modern')", 800)
    ff(*sum((["-i", str(DOCS / f"style-{s}.png")] for s in ("modern", "scandinavian", "japandi", "industrial")), []),
       "-filter_complex",
       "".join(f"[{i}:v]scale=800:-2,drawtext=text='{n}':fontcolor=white:fontsize=34:box=1:boxcolor=0x1c1f24cc:boxborderw=14:x=24:y=24[s{i}];"
               for i, n in enumerate(["Modern", "Scandinavian", "Japandi", "Industrial"])) +
       "[s0][s1]hstack[top];[s2][s3]hstack[bot];[top][bot]vstack", str(DOCS / "style-presets.png"))

    # 4. 2D plan (before) vs 3D top render (after)
    st(page, "s.setLayout('2d')", 1800)
    page.add_style_tag(content=HIDE)
    page.locator("[data-testid=editor2d]").screenshot(path=str(DOCS / "twobed-2d.png"))
    page.evaluate("document.querySelectorAll('style').forEach(s => s.textContent.includes('layoutbar,.viewbar') && s.remove())")
    st(page, "s.setLayout('3d'); s.setView('top')", 2600)
    canvas_shot(page, DOCS / "twobed-top-for-compare.png")
    ff("-i", str(DOCS / "twobed-2d.png"), "-i", str(DOCS / "twobed-top-for-compare.png"), "-filter_complex",
       "[0:v]scale=-2:820,drawtext=text='2D plan':fontcolor=white:fontsize=30:box=1:boxcolor=0x1c1f24cc:boxborderw=12:x=20:y=20[a];"
       "[1:v]scale=-2:820,drawtext=text='Furnished 3D':fontcolor=white:fontsize=30:box=1:boxcolor=0x0f766ecc:boxborderw=12:x=20:y=20[b];[a][b]hstack",
       str(DOCS / "before-after-2d-3d.png"))

    # 5. editing: draw a wall + selection inspector on the studio
    load(page, 0)
    st(page, "s.setLayout('split'); s.setView('dollhouse'); s.setTool('select');", 1500)
    item = page.locator("[data-k=item]").nth(6)
    item.click()
    page.wait_for_timeout(1200)
    page.screenshot(path=str(DOCS / "app-edit-studio.png"))

    # 6. exports: hi-res PNG + GLB really download
    st(page, "s.setLayout('3d'); s.setView('dollhouse');", 2500)
    with page.expect_download() as d:
        page.get_by_role("button", name="PNG render · 4×").click()
    d.value.save_as(str(DOCS / "export-studio-dollhouse-4x.png"))
    with page.expect_download() as d:
        page.get_by_role("button", name="GLB 3D model").click()
    glb = ROOT / "examples" / "studio-apartment.glb"
    glb.parent.mkdir(exist_ok=True)
    d.value.save_as(str(glb))
    print("GLB bytes", glb.stat().st_size)



def videos(page, orbit=True):
    # 7. videos: frame-exact walkthrough + 360 orbit
    # full-bleed canvas for video: hide the side panels, ~16:9 frame
    page.set_viewport_size({"width": 1304, "height": 800})
    page.add_style_tag(content=".app{grid-template-columns:1fr!important} header{grid-column:1!important} aside{display:none!important} .stage{padding:0!important} .pane{border-radius:0!important;border:0!important}")
    st(page, "s.setLayout('3d');", 2000)
    for i, pid in [(1, "twobed"), (2, "townhouse")]:
        load(page, i)
        st(page, "s.setView('walk')", 1500)
        seconds = page.evaluate("__three.tourLength()")
        frames(page, DOCS / f"walkthrough-{pid}.mp4", lambda t: f"__three.setTour({t})", seconds, fps=20)
        page.evaluate("__three.setTour(null)")
        if not orbit:
            continue
        st(page, "s.setView('dollhouse')", 2000)
        frames(page, DOCS / f"orbit-{pid}.mp4", lambda t: f"__three.orbit({t * 36})", 10, fps=20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5180/")
    ap.add_argument("--chrome", default="/usr/bin/google-chrome")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--only-video", action="store_true")
    ap.add_argument("--orbit", action="store_true", help="with --only-video: also render the 360 orbits")
    a = ap.parse_args()
    DOCS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=a.chrome, headless=True, args=ARGS)
        ctx = b.new_context(viewport={"width": 1680, "height": 945}, device_scale_factor=1, accept_downloads=True)
        page = ctx.new_page()
        page.goto(a.url)
        page.wait_for_selector("canvas")
        page.wait_for_timeout(4000)

        if not a.only_video:
            stills(page)
        if not a.no_video:
            videos(page, orbit=not a.only_video or a.orbit)
        b.close()
    print("done ->", DOCS)


if __name__ == "__main__":
    main()
