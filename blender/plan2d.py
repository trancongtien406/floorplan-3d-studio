"""2D architectural plan image + dimension check against the Blender top render (system python3 + PIL).

  python3 blender/plan2d.py --plan blender/plans/twobed.json --out plan.png [--top render_top_hero.png --check check.png]

The check overlays the plan's wall centre-lines / faces (red) and opening extents (cyan) on the orthographic top
render using the exact camera framing of render_plan.py, and measures the rendered outer wall extents in pixels.
"""
import json, math, sys
from PIL import Image, ImageDraw, ImageFont

argv = sys.argv[1:]
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
PLAN = json.load(open(arg("--plan")))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 2560, 1440
xs = [p[0] for w in PLAN["walls"] for p in (w["a"], w["b"])]; ys = [p[1] for w in PLAN["walls"] for p in (w["a"], w["b"])]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
cx, cy, pw, ph = (minx + maxx) / 2, (miny + maxy) / 2, maxx - minx, maxy - miny


def wall_quad(w, T):
    (ax, ay), (bx, by) = w["a"], w["b"]; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
    nx, ny = -uy * w["thickness"] / 2, ux * w["thickness"] / 2; e = w["thickness"] / 2
    a = (ax - ux * e, ay - uy * e); b = (bx + ux * e, by + uy * e)
    return [T(a[0] + nx, a[1] + ny), T(b[0] + nx, b[1] + ny), T(b[0] - nx, b[1] - ny), T(a[0] - nx, a[1] - ny)]


def op_geom(op):
    w = next(w for w in PLAN["walls"] if w["id"] == op["wallId"]); (ax, ay), (bx, by) = w["a"], w["b"]
    L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L; c = op["t"] * L
    p0 = (ax + ux * (c - op["width"] / 2), ay + uy * (c - op["width"] / 2)); p1 = (ax + ux * (c + op["width"] / 2), ay + uy * (c + op["width"] / 2))
    return w, (ux, uy), p0, p1


def poly_area(pts):
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2


def edge_wall(p, q):
    """Wall whose centre-line covers room edge p-q (collinear, >50 % overlap) or None (open edge)."""
    (px, py), (qx, qy) = p, q; L = math.hypot(qx - px, qy - py)
    for w in PLAN["walls"]:
        (ax, ay), (bx, by) = w["a"], w["b"]; dx, dy = bx - ax, by - ay; WL = math.hypot(dx, dy)
        if WL < 1e-9: continue
        nx, ny = -dy / WL, dx / WL
        if abs((px - ax) * nx + (py - ay) * ny) > 0.02 or abs((qx - ax) * nx + (qy - ay) * ny) > 0.02: continue
        t0 = ((px - ax) * dx + (py - ay) * dy) / WL; t1 = ((qx - ax) * dx + (qy - ay) * dy) / WL
        ov = min(max(t0, t1), WL) - max(min(t0, t1), 0)
        if ov > 0.5 * L: return w
    return None


def net_polygon(pts):
    """Room polygon shrunk to the inside faces of its walls: each edge moves inward by half the thickness of the wall
    on it (open-plan edges without a wall stay on the line)."""
    n = len(pts); sa = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    lines = []
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]; dx, dy = q[0] - p[0], q[1] - p[1]; L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
        inx, iny = (-uy, ux) if sa > 0 else (uy, -ux)
        w = edge_wall(p, q); off = w["thickness"] / 2 if w else 0.0
        lines.append(((p[0] + inx * off, p[1] + iny * off), (ux, uy)))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9: out.append(p2); continue
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append((p1[0] + d1[0] * t, p1[1] + d1[1] * t))
    return out


def areas():
    rooms = {r["name"]: {"net_m2": round(poly_area(net_polygon(r["points"])), 2), "centreline_m2": round(poly_area(r["points"]), 2),
                         "net_dims_m": [round(max(p[0] for p in net_polygon(r["points"])) - min(p[0] for p in net_polygon(r["points"])), 3),
                                        round(max(p[1] for p in net_polygon(r["points"])) - min(p[1] for p in net_polygon(r["points"])), 3)]}
             for r in PLAN["rooms"]}
    ext = max(w["thickness"] for w in PLAN["walls"])
    return {"rooms": rooms, "net_total_m2": round(sum(v["net_m2"] for v in rooms.values()), 2),
            "gross_centreline_m2": round(pw * ph, 2), "gross_external_m2": round((pw + ext) * (ph + ext), 2),
            "method": "net = room polygons offset to the inside wall faces (half the wall thickness per walled edge; open-plan "
                      "edges stay on the line, so living/kitchen and hall/living are split on the open boundary)"}


def draw_plan(out):
    s = min((W - 900) / pw, (H - 380) / ph); ox = (W - 640 - pw * s) / 2 - minx * s + 60; oy = (H - ph * s) / 2 - miny * s + 30
    T = lambda x, y: (ox + x * s, oy + y * s)
    im = Image.new("RGB", (W, H), (250, 249, 246)); d = ImageDraw.Draw(im)
    f_room = ImageFont.truetype(FONTB, 30); f_area = ImageFont.truetype(FONT, 24); f_dim = ImageFont.truetype(FONT, 27); f_t = ImageFont.truetype(FONTB, 40)
    # floors
    fill = {"wood": (236, 226, 208), "tile": (226, 230, 232), "carpet": (232, 226, 236), "stone": (228, 228, 224)}
    for r in PLAN["rooms"]:
        d.polygon([T(*p) for p in r["points"]], fill=fill.get(r["floor"], (240, 240, 240)))
    # grid (0.5 m)
    for gx in range(int(minx * 2), int(maxx * 2) + 1):
        d.line([T(gx / 2, miny), T(gx / 2, maxy)], fill=(225, 222, 216), width=1)
    for gy in range(int(miny * 2), int(maxy * 2) + 1):
        d.line([T(minx, gy / 2), T(maxx, gy / 2)], fill=(225, 222, 216), width=1)
    for w in PLAN["walls"]:
        d.polygon(wall_quad(w, T), fill=(40, 42, 48))
    # openings: clear the wall, draw symbols
    for op in PLAN["openings"]:
        w, (ux, uy), p0, p1 = op_geom(op); t = w["thickness"] / 2 + 0.005; nx, ny = -uy, ux
        q = [T(p0[0] + nx * t, p0[1] + ny * t), T(p1[0] + nx * t, p1[1] + ny * t), T(p1[0] - nx * t, p1[1] - ny * t), T(p0[0] - nx * t, p0[1] - ny * t)]
        d.polygon(q, fill=(250, 249, 246))
        if op["kind"] in ("window", "slider"):
            for k in (-0.3, 0.3) if op["kind"] == "window" else (-0.35, 0.0, 0.35):
                d.line([T(p0[0] + nx * t * k * 2, p0[1] + ny * t * k * 2), T(p1[0] + nx * t * k * 2, p1[1] + ny * t * k * 2)], fill=(60, 120, 170), width=3)
            d.line([q[0], q[3]], fill=(40, 42, 48), width=3); d.line([q[1], q[2]], fill=(40, 42, 48), width=3)
        else:  # door: leaf + 90 deg swing arc, same handedness as the web app
            sgn = -1 if op.get("flip") else 1
            hx, hy = p0; Lw = op["width"]
            # leaf opens to the side given by the app's -s*80 deg rotation (plan frame: +normal for s=1)
            lx, ly = hx + nx * sgn * Lw, hy + ny * sgn * Lw
            d.line([T(hx, hy), T(lx, ly)], fill=(40, 42, 48), width=4)
            a0 = math.degrees(math.atan2(ny * sgn, nx * sgn)); a1 = math.degrees(math.atan2(uy, ux))
            c = T(hx, hy); r = Lw * s
            lo, hi = sorted((a0, a1))
            if hi - lo > 180: lo, hi = hi, lo + 360
            d.arc([c[0] - r, c[1] - r, c[0] + r, c[1] + r], lo, hi, fill=(120, 120, 120), width=2)
    # room labels
    for r in PLAN["rooms"]:
        px = sum(p[0] for p in r["points"]) / len(r["points"]); py = sum(p[1] for p in r["points"]) / len(r["points"])
        X, Y = T(px, py); a = poly_area(net_polygon(r["points"]))
        if a < 4: X += 0.45 * s  # small rooms: keep the label clear of door swings
        d.text((X, Y - 16), r["name"], font=f_room, fill=(30, 30, 30), anchor="mm")
        d.text((X, Y + 18), f"{a:.2f} m² net", font=f_area, fill=(90, 90, 90), anchor="mm")
    # dimension chains (centre-line, like the app's labels)
    def dim(p, q, off, horiz):
        (x0, y0), (x1, y1) = T(*p), T(*q)
        if horiz:
            y = y0 + off; d.line([(x0, y), (x1, y)], fill=(70, 70, 70), width=2)
            for x in (x0, x1): d.line([(x, y - 10), (x, y + 10)], fill=(70, 70, 70), width=2)
            d.text(((x0 + x1) / 2, y - 16 if off < 0 else y + 16), f"{abs(q[0] - p[0]):.2f}", font=f_dim, fill=(40, 40, 40), anchor="mm")
        else:
            x = x0 + off; d.line([(x, y0), (x, y1)], fill=(70, 70, 70), width=2)
            for y in (y0, y1): d.line([(x - 10, y), (x + 10, y)], fill=(70, 70, 70), width=2)
            tx = Image.new("RGBA", (150, 38), (0, 0, 0, 0)); ImageDraw.Draw(tx).text((75, 19), f"{abs(q[1] - p[1]):.2f}", font=f_dim, fill=(40, 40, 40), anchor="mm")
            tx = tx.rotate(90, expand=True); im.paste(tx, (int(x - 17 - (18 if off < 0 else -18)), int((y0 + y1) / 2 - 70)), tx)
    # chains: walls that meet each outer edge
    def chain(axis, edge):
        v = {minx, maxx} if axis == 0 else {miny, maxy}
        for w in PLAN["walls"]:
            for p, q in ((w["a"], w["b"]), (w["b"], w["a"])):
                if abs(p[1 - axis] - edge) < 1e-6 and abs(q[1 - axis] - edge) > 1e-6 and abs(p[axis] - q[axis]) < 1e-6: v.add(p[axis])
        return sorted(v)
    top = chain(0, miny); left = chain(1, minx); right = chain(1, maxx); bot = chain(0, maxy)
    for i in range(len(top) - 1): dim((top[i], miny), (top[i + 1], miny), -70, True)
    dim((minx, miny), (maxx, miny), -125, True)
    for i in range(len(left) - 1): dim((minx, left[i]), (minx, left[i + 1]), -70, False)
    dim((minx, miny), (minx, maxy), -125, False)
    for i in range(len(right) - 1): dim((maxx, right[i]), (maxx, right[i + 1]), 70, False)
    # opening positions along the bottom (maxy) edge
    for op in PLAN["openings"]:
        w, _, p0, p1 = op_geom(op)
        if abs(w["a"][1] - maxy) < 1e-6 and abs(w["b"][1] - maxy) < 1e-6:
            a_, b_ = sorted((p0[0], p1[0])); dim((minx, maxy), (a_, maxy), 70, True); dim((a_, maxy), (b_, maxy), 70, True); dim((b_, maxy), (maxx, maxy), 70, True)
    dim((minx, maxy), (maxx, maxy), 125, True)
    # title block
    bx = W - 600
    d.text((bx, 120), PLAN.get("name", PLAN["id"]).upper(), font=f_t, fill=(30, 30, 30))
    d.text((bx, 175), PLAN.get("subtitle", ""), font=f_area, fill=(90, 90, 90))
    A = areas()
    lines = [f"Net floor area: {A['net_total_m2']:.2f} m²  (inside wall faces)", f"Gross area: {A['gross_centreline_m2']:.1f} m²  (wall centre-lines)",
             f"Gross external: {A['gross_external_m2']:.1f} m²  (outside faces)",
             f"Outer: {pw + 0.2:.2f} × {ph + 0.2:.2f} m outside faces", "Exterior walls 200 mm, interior 120 mm",
             f"Ceiling height {max(w['height'] for w in PLAN['walls']):.2f} m", "Dimensions in metres", "", "Legend:"]
    for i, l in enumerate(lines): d.text((bx, 230 + i * 36), l, font=f_area, fill=(50, 50, 50))
    yy = 230 + len(lines) * 36
    d.rectangle([bx, yy, bx + 40, yy + 14], fill=(40, 42, 48)); d.text((bx + 55, yy - 6), "wall", font=f_area, fill=(50, 50, 50))
    d.line([(bx, yy + 44), (bx + 40, yy + 44)], fill=(60, 120, 170), width=3); d.text((bx + 55, yy + 30), "window / slider", font=f_area, fill=(50, 50, 50))
    d.arc([bx - 10, yy + 64, bx + 50, yy + 124], 270, 360, fill=(120, 120, 120), width=2); d.text((bx + 55, yy + 76), "door swing", font=f_area, fill=(50, 50, 50))
    # north arrow + scale bar
    sx0, sy0 = bx, H - 160
    for k in range(4):
        d.rectangle([sx0 + k * s / 2, sy0, sx0 + (k + 1) * s / 2, sy0 + 14], fill=(40, 40, 40) if k % 2 == 0 else (250, 249, 246), outline=(40, 40, 40))
    d.text((sx0, sy0 + 24), "0", font=f_area, fill=(50, 50, 50)); d.text((sx0 + 2 * s, sy0 + 24), "2 m", font=f_area, fill=(50, 50, 50), anchor="ma")
    im.save(out); return out


def check(top, out):
    """Overlay plan geometry on the ortho top render (camera as in render_plan.py) and measure the outer walls."""
    im = Image.open(top).convert("RGB"); Wi, Hi = im.size
    rot90 = ph > pw; span_x, span_y = (ph, pw) if rot90 else (pw, ph)
    scale = max(span_x * 1.1, span_y * 1.1 * 16 / 9); k = Wi / scale
    assert not rot90
    T = lambda x, y: (Wi / 2 + (x - cx) * k, Hi / 2 + (y - cy) * k)
    d = ImageDraw.Draw(im); f = ImageFont.truetype(FONTB, 26)
    for w in PLAN["walls"]:
        q = wall_quad(w, T); d.polygon(q, outline=(255, 30, 30)); d.line([q[0], q[1]], fill=(255, 30, 30), width=2); d.line([q[2], q[3]], fill=(255, 30, 30), width=2)
        d.line([T(*w["a"]), T(*w["b"])], fill=(255, 200, 0), width=1)
    for op in PLAN["openings"]:
        _, _, p0, p1 = op_geom(op)
        for p in (p0, p1):
            X, Y = T(*p); d.ellipse([X - 6, Y - 6, X + 6, Y + 6], outline=(0, 220, 255), width=3)
    # measure: walls render in the dark wallTop colour; scan the centre row / column for the outermost dark pixels
    px = Image.open(top).convert("RGB").load()
    ref = px[int(T(minx, 6.5)[0]), int(T(minx, 6.5)[1])]   # wall-top colour sampled on a solid outer wall
    near = lambda c: sum((a - b) ** 2 for a, b in zip(c, ref)) ** 0.5 < 45
    def run(fixed, horiz):
        idx = [i for i in range(Wi if horiz else Hi) if near(px[i, fixed] if horiz else px[fixed, i])]
        return (min(idx), max(idx)) if idx else (0, 0)
    rowY = int(T(cx, 6.5)[1]); colX = int(T(6.5, cy)[0])   # rows / columns crossing solid outer wall runs only
    x0, x1 = run(rowY, True); y0, y1 = run(colX, False)
    mw, mh = (x1 - x0 + 1) / k, (y1 - y0 + 1) / k
    res = {"px_per_m": round(k, 2), "measured_outer_m": [round(mw, 3), round(mh, 3)], "expected_outer_m": [pw + 0.2, ph + 0.2],
           "error_mm": [round((mw - pw - 0.2) * 1000, 1), round((mh - ph - 0.2) * 1000, 1)]}
    d.rectangle([20, 20, 900, 150], fill=(255, 255, 255))
    d.text((40, 32), "Dimension check: plan geometry (red/yellow/cyan) over Blender top render", font=f, fill=(20, 20, 20))
    d.text((40, 72), f"measured outer {mw:.3f} × {mh:.3f} m  vs plan {pw + 0.2:.2f} × {ph + 0.2:.2f} m", font=f, fill=(20, 20, 20))
    d.text((40, 108), f"error {res['error_mm'][0]:+.0f} / {res['error_mm'][1]:+.0f} mm  (1 px = {1000 / k:.1f} mm)", font=f, fill=(20, 20, 20))
    im.save(out); return res


if __name__ == "__main__":
    print(draw_plan(arg("--out")))
    if arg("--areas"):
        json.dump(areas(), open(arg("--areas"), "w"), indent=2); print(json.dumps(areas()))
    if arg("--top"):
        r = check(arg("--top"), arg("--check")); print(json.dumps(r))
        json.dump(r, open(arg("--check").rsplit(".", 1)[0] + ".json", "w"), indent=2)
