"""Round-4 presentation + proof sheets (system python3 + PIL).

  python3 blender/present.py --plan blender/plans/twobed.json --report R/modern/twobed_modern_report.json \
      --top R/modern/twobed_modern_top_hero.png --plan2d R/twobed_plan_2d.png --out R [--doll ... --living ... --kitchen ... --bedroom ...]
      [--styles modern.png,scandinavian.png,japandi.png]

Outputs
  geometry_proof.json/.csv/.png  plan data vs the Blender model's own coordinates (walls, openings, door swings)
  geometry_overlay.png           model-space geometry drawn over the ortho top render, legend in the margin only
  technical_top.png              labelled top view: rooms + net areas, dimension chains, door/window tags, entrance
  gallery_*.jpg (1280x769)       short-title gallery compositions
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import plan2d as P2   # reads --plan from argv

argv = sys.argv[1:]
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
PLAN = P2.PLAN; OUT = arg("--out"); os.makedirs(OUT, exist_ok=True)
REP = json.load(open(arg("--report"))) if arg("--report") else None
FD = "/usr/share/fonts/truetype/sand-box/google/Poppins/"
F = lambda w, s: ImageFont.truetype(FD + f"Poppins-{w}.ttf", s)
minx, maxx, miny, maxy, cx, cy, pw, ph = P2.minx, P2.maxx, P2.miny, P2.maxy, P2.cx, P2.cy, P2.pw, P2.ph
WALLS = {w["id"]: w for w in PLAN["walls"]}
INK = (34, 36, 40); MUTED = (110, 112, 118); PAPER = (248, 247, 244)


def inpoly(x, y, pts):
    c = False
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i - 1], pts[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
    return c


def room_at(x, y):
    for r in PLAN["rooms"]:
        if inpoly(x, y, r["points"]): return r["name"]
    return "outside"


def wall_geo(w):
    (ax, ay), (bx, by) = w["a"], w["b"]; L = math.hypot(bx - ax, by - ay); u = ((bx - ax) / L, (by - ay) / L)
    return (ax, ay), u, (-u[1], u[0]), L


def tags():
    """D1.. doors, W1.. windows, S1.. sliders in plan order."""
    out = {}; n = {"door": 0, "window": 0, "slider": 0}; pre = {"door": "D", "window": "W", "slider": "S"}
    for op in PLAN["openings"]:
        n[op["kind"]] += 1; out[op["id"]] = f"{pre[op['kind']]}{n[op['kind']]}"
    return out
TAG = tags()


def exterior(op):
    w = WALLS[op["wallId"]]; return w["thickness"] >= 0.19


# ------------------------------------------------------------------ geometry proof (model coords from render_plan.py)
def proof():
    B = REP["built"]; rows_w, rows_o = [], []; worst = 0.0
    for w in PLAN["walls"]:
        b = B["walls"][w["id"]]
        # built endpoints are unordered along the axis: match to the plan's a/b
        pa, pb = w["a"], w["b"]; ba, bb = b["a"], b["b"]
        if math.dist(pa, ba) + math.dist(pb, bb) > math.dist(pa, bb) + math.dist(pb, ba): ba, bb = bb, ba
        dev = max(math.dist(pa, ba), math.dist(pb, bb)) * 1000; worst = max(worst, dev)
        rows_w.append({"wall": w["id"], "plan_a": pa, "plan_b": pb, "model_a": ba, "model_b": bb, "endpoint_dev_mm": round(dev, 1),
                       "t_plan_mm": round(w["thickness"] * 1000), "t_model_mm": round(b["thickness"] * 1000, 1),
                       "h_plan_m": w["height"], "h_model_m": b["height"], "ok": dev < 2 and abs(b["thickness"] - w["thickness"]) < 0.002})
    for op in PLAN["openings"]:
        w = WALLS[op["wallId"]]; (ax, ay), u, n, L = wall_geo(w); b = B["openings"][op["id"]]
        c_plan = op["t"] * L; head = op["sill"] + op["height"]
        r = {"id": op["id"], "tag": TAG[op["id"]], "kind": op["kind"], "wall": op["wallId"],
             "centre_plan_m": round(c_plan, 3), "centre_model_m": b["centre_from_a"], "centre_dev_mm": round(abs(b["centre_from_a"] - c_plan) * 1000, 1),
             "width_plan_m": op["width"], "width_model_m": b["width"], "width_dev_mm": round(abs(b["width"] - op["width"]) * 1000, 1),
             "sill_plan_m": op["sill"], "sill_model_m": b["sill"], "head_plan_m": round(head, 3), "head_model_m": b["head"]}
        ok = r["centre_dev_mm"] < 2 and r["width_dev_mm"] < 2 and abs(b["head"] - head) < 0.005 and abs(b["sill"] - op["sill"]) < 0.03
        if op["kind"] == "door":
            sgn = -1 if op.get("flip") else 1                     # plan convention (2D plan + web app): leaf to the +normal side when not flipped
            hx = ax + u[0] * (c_plan - op["width"] / 2); hy = ay + u[1] * (c_plan - op["width"] / 2)
            into_plan = room_at(hx + n[0] * sgn * 0.4 + u[0] * 0.3, hy + n[1] * sgn * 0.4 + u[1] * 0.3)
            ms = b["opens_to_normal_side"]; fx, fy = b["leaf_free_edge"]
            into_model = room_at(hx + n[0] * ms * 0.4 + u[0] * 0.3, hy + n[1] * ms * 0.4 + u[1] * 0.3)
            hinge_plan_end = "a-side jamb"; hinge_model_end = "a-side jamb" if b["hinge_from_a"] < c_plan else "b-side jamb"
            r.update({"swing_plan": into_plan, "swing_model": into_model, "hinge_plan": hinge_plan_end, "hinge_model": hinge_model_end,
                      "shown_closed": b.get("shown_closed", False)})
            ok = ok and into_plan == into_model and hinge_model_end == hinge_plan_end
        r["ok"] = ok; rows_o.append(r)
        worst = max(worst, r["centre_dev_mm"], r["width_dev_mm"])
    res = {"source": "plan JSON vs Blender object coordinates (built wall boxes before the boolean union, window frames / door casings, door "
                     "leaf evaluated at its modelled 80° open angle)", "walls": rows_w, "openings": rows_o, "max_dev_mm": round(worst, 2),
           "all_ok": all(r["ok"] for r in rows_w + rows_o)}
    json.dump(res, open(os.path.join(OUT, "geometry_proof.json"), "w"), indent=2)
    with open(os.path.join(OUT, "geometry_proof.csv"), "w") as f:
        f.write("element,id,check,plan,model,deviation_mm,ok\n")
        for r in rows_w:
            f.write(f"wall,{r['wall']},centre-line a->b,\"{r['plan_a']}->{r['plan_b']}\",\"{r['model_a']}->{r['model_b']}\",{r['endpoint_dev_mm']},{r['ok']}\n")
            f.write(f"wall,{r['wall']},thickness mm,{r['t_plan_mm']},{r['t_model_mm']},{abs(r['t_plan_mm'] - r['t_model_mm']):.1f},{r['ok']}\n")
        for r in rows_o:
            f.write(f"{r['kind']},{r['tag']} ({r['id']}),centre from wall start m,{r['centre_plan_m']},{r['centre_model_m']},{r['centre_dev_mm']},{r['ok']}\n")
            f.write(f"{r['kind']},{r['tag']} ({r['id']}),width m,{r['width_plan_m']},{r['width_model_m']},{r['width_dev_mm']},{r['ok']}\n")
            if r["kind"] == "door":
                f.write(f"door,{r['tag']} ({r['id']}),swings into,{r['swing_plan']},{r['swing_model']},,{r['ok']}\n")
    # table image
    DJ = "/usr/share/fonts/truetype/dejavu/"
    fb = ImageFont.truetype(DJ + "DejaVuSans.ttf", 21); fs = ImageFont.truetype(DJ + "DejaVuSans-Bold.ttf", 21); fok = ImageFont.truetype(DJ + "DejaVuSans-Bold.ttf", 24)
    cols_w = ["Wall", "Plan centre-line (m)", "Model centre-line (m)", "Endpoint Δ max", "Thickness plan / model", "Height plan / model", ""]
    cols_o = ["Tag", "Type / wall", "Centre plan / model (m)", "Width plan / model (m)", "Sill–head plan / model (m)", "Swing plan / model", ""]
    rowsW = [[r["wall"], f"{tuple(r['plan_a'])} → {tuple(r['plan_b'])}", f"({abs(r['model_a'][0]) if abs(r['model_a'][0]) < 5e-4 else r['model_a'][0]:.3f}, {abs(r['model_a'][1]) if abs(r['model_a'][1]) < 5e-4 else r['model_a'][1]:.3f}) → ({abs(r['model_b'][0]) if abs(r['model_b'][0]) < 5e-4 else r['model_b'][0]:.3f}, {abs(r['model_b'][1]) if abs(r['model_b'][1]) < 5e-4 else r['model_b'][1]:.3f})",
              f"{r['endpoint_dev_mm']:.1f} mm", f"{r['t_plan_mm']} / {r['t_model_mm']:.0f} mm", f"{r['h_plan_m']:.2f} / {r['h_model_m']:.2f}", "✓" if r["ok"] else "✗"] for r in rows_w]
    rowsO = [[r["tag"], f"{r['kind']} · {r['wall']}", f"{r['centre_plan_m']:.3f} / {r['centre_model_m']:.3f}", f"{r['width_plan_m']:.3f} / {r['width_model_m']:.3f}",
              f"{r['sill_plan_m']:.2f}–{r['head_plan_m']:.2f} / {r['sill_model_m']:.2f}–{r['head_model_m']:.2f}",
              (f"{r['swing_plan']} / {r['swing_model']}" + (" (closed)" if r.get("shown_closed") else "")) if r["kind"] == "door" else "—", "✓" if r["ok"] else "✗"] for r in rows_o]
    X = [60, 200, 620, 1120, 1330, 1690, 2010, 2460]; Xo = [60, 170, 420, 800, 1140, 1560, 2290, 2460]
    H_ = 200 + 46 * (len(rowsW) + len(rowsO)) + 260
    im = Image.new("RGB", (2560, H_), PAPER); d = ImageDraw.Draw(im)
    d.text((60, 40), "Geometry proof — plan data vs Blender model coordinates", font=F("SemiBold", 44), fill=INK)
    d.text((60, 104), f"{PLAN.get('name', PLAN['id'])} · max deviation {res['max_dev_mm']:.2f} mm · "
                      f"{sum(r['ok'] for r in rows_w + rows_o)}/{len(rows_w) + len(rows_o)} checks pass · measured on built objects, not pixels", font=fb, fill=MUTED)
    y = 170
    def table(cols, rows, xs, y):
        d.rectangle([40, y - 6, 2520, y + 36], fill=(232, 230, 225))
        for c, x in zip(cols, xs): d.text((x, y), c, font=fs, fill=INK)
        y += 46
        for i, rr in enumerate(rows):
            if i % 2: d.rectangle([40, y - 6, 2520, y + 36], fill=(242, 241, 237))
            for c, x in zip(rr, xs):
                col = (30, 130, 70) if c == "✓" else (200, 40, 40) if c == "✗" else INK
                d.text((x, y), str(c), font=fb if c not in ("✓", "✗") else fok, fill=col)
            y += 46
        return y
    y = table(cols_w, rowsW, X, y) + 30
    y = table(cols_o, rowsO, Xo, y) + 20
    d.text((60, y), "Swing = room the leaf opens into, from the hinge jamb; plan convention as in the web app and the 2D plan. Doors marked "
                    "(closed) are rendered shut but their modelled swing is still checked.", font=fb, fill=MUTED)
    im.save(os.path.join(OUT, "geometry_proof.png")); return res


def top_map(top_png):
    im = Image.open(top_png).convert("RGB"); Wi, Hi = im.size
    scale = max(pw * 1.1, ph * 1.1 * 16 / 9); k = Wi / scale
    return im, (lambda x, y: (Wi / 2 + (x - cx) * k, Hi / 2 + (y - cy) * k)), k


def overlay(top_png):
    im, T, k = top_map(top_png); d = ImageDraw.Draw(im, "RGBA"); B = REP["built"]
    RED = (225, 40, 40, 255); YEL = (255, 190, 0, 255); CY = (0, 180, 230, 255); OR = (255, 120, 0, 255)
    for wid, b in B["walls"].items():
        (ax, ay), (bx, by) = b["a"], b["b"]; t = b["thickness"] / 2; e = t
        if abs(ay - by) < 1e-6:   # horizontal
            q = [T(min(ax, bx) - e, ay - t), T(max(ax, bx) + e, ay + t)]
        else:
            q = [T(ax - t, min(ay, by) - e), T(ax + t, max(ay, by) + e)]
        d.rectangle(q, outline=RED, width=2)
        d.line([T(ax, ay), T(bx, by)], fill=YEL, width=2)
    for op in PLAN["openings"]:
        w = WALLS[op["wallId"]]; (ax, ay), u, n, L = wall_geo(w); b = B["openings"][op["id"]]; t = w["thickness"] / 2 + 0.06
        for s in (-1, 1):
            c = b["centre_from_a"] + s * b["width"] / 2; px, py = ax + u[0] * c, ay + u[1] * c
            d.line([T(px - n[0] * t, py - n[1] * t), T(px + n[0] * t, py + n[1] * t)], fill=CY, width=4)
        if op["kind"] == "door":
            hc = b["hinge_from_a"]; hx, hy = ax + u[0] * hc, ay + u[1] * hc; fx, fy = b["leaf_free_edge"]
            d.line([T(hx, hy), T(fx, fy)], fill=OR, width=3)
            r = math.hypot(fx - hx, fy - hy) * k; C = T(hx, hy)
            a0 = math.degrees(math.atan2(fy - hy, fx - hx)); a1 = math.degrees(math.atan2(u[1], u[0]))
            lo, hi = sorted((a0, a1))
            if hi - lo > 180: lo, hi = hi, lo + 360
            d.arc([C[0] - r, C[1] - r, C[0] + r, C[1] + r], lo, hi, fill=OR, width=2)
    # text only in the left margin (building starts ~ x=446 px at 2560)
    Wi, Hi = im.size; mx = int(T(minx - 0.15, 0)[0]) - 30
    d.rounded_rectangle([24, 24, mx, 250], 14, fill=(255, 255, 255, 235))
    d.text((44, 38), "Geometry check", font=F("SemiBold", 30), fill=INK)
    pr = json.load(open(os.path.join(OUT, "geometry_proof.json")))
    d.text((44, 84), f"model vs plan: max {pr['max_dev_mm']:.2f} mm", font=F("Regular", 20), fill=MUTED)
    d.text((44, 112), f"{sum(r['ok'] for r in pr['walls'] + pr['openings'])}/{len(pr['walls']) + len(pr['openings'])} checks pass", font=F("Regular", 20), fill=MUTED)
    d.text((44, 140), "drawn from Blender object coords", font=F("Regular", 20), fill=MUTED)
    d.text((44, 168), "table: geometry_proof.png", font=F("Regular", 20), fill=MUTED)
    y0 = Hi - 230
    d.rounded_rectangle([24, y0, mx, Hi - 24], 14, fill=(255, 255, 255, 235))
    items = [(RED, "wall faces (model)", "rect"), (YEL, "wall centre-line", "line"), (CY, "opening jambs", "tick"), (OR, "door leaf + swing", "line")]
    for i, (c, lab, kind) in enumerate(items):
        yy = y0 + 28 + i * 44
        if kind == "rect": d.rectangle([44, yy, 84, yy + 18], outline=c, width=2)
        elif kind == "tick": d.line([(64, yy - 4), (64, yy + 22)], fill=c, width=4)
        else: d.line([(44, yy + 9), (84, yy + 9)], fill=c, width=3)
        d.text((100, yy - 4), lab, font=F("Regular", 21), fill=INK)
    im.save(os.path.join(OUT, "geometry_overlay.png"))


def technical(top_png):
    src, T0, k = top_map(top_png); W, H = 2560, 1440; m = 0.35
    x0, y0 = T0(minx - m, miny - m); x1, y1 = T0(maxx + m, maxy + m)
    crop = src.crop((int(x0), max(0, int(y0)), int(x1), min(src.size[1], int(y1))))
    PANEL = 640; avail_w, avail_h = W - PANEL - 330, H - 330
    f = min(avail_w / crop.size[0], avail_h / crop.size[1]); crop = crop.resize((int(crop.size[0] * f), int(crop.size[1] * f)), Image.LANCZOS)
    ox = 190 + (avail_w - crop.size[0]) // 2; oy = 165 + (avail_h - crop.size[1]) // 2
    im = Image.new("RGB", (W, H), PAPER); im.paste(crop, (ox, oy)); d = ImageDraw.Draw(im, "RGBA")
    T = lambda x, y: (ox + (x - (minx - m)) * k * f, oy + (y - (miny - m)) * k * f + (0 if y0 >= 0 else y0 * f))
    A = P2.areas()
    # rooms
    for r in PLAN["rooms"]:
        net = P2.net_polygon(r["points"]); X = sum(p[0] for p in net) / len(net); Y = sum(p[1] for p in net) / len(net)
        X_, Y_ = T(X, Y); a = A["rooms"][r["name"]]
        if r["name"] == "Hall": X_, Y_ = T(X + 0.1, Y + 0.45)
        t1 = r["name"].upper(); t2 = f"{a['net_m2']:.2f} m²  ·  {a['net_dims_m'][0]:.2f} × {a['net_dims_m'][1]:.2f}"
        f1, f2 = F("SemiBold", 22), F("Regular", 17)
        w_ = max(d.textlength(t1, font=f1), d.textlength(t2, font=f2)) + 26
        d.rounded_rectangle([X_ - w_ / 2, Y_ - 34, X_ + w_ / 2, Y_ + 30], 10, fill=(255, 255, 255, 225))
        d.text((X_, Y_ - 14), t1, font=f1, fill=INK, anchor="mm"); d.text((X_, Y_ + 13), t2, font=f2, fill=MUTED, anchor="mm")
    # opening tags + entrance
    for op in PLAN["openings"]:
        w = WALLS[op["wallId"]]; (ax, ay), u, n, L = wall_geo(w); c = op["t"] * L; px, py = ax + u[0] * c, ay + u[1] * c
        out = 1 if not P2_inside(px + n[0] * 0.5, py + n[1] * 0.5) else -1     # +1: normal points outside
        # tags sit just inside the wall (the margins carry the dimension chains)
        tx, ty = T(px - n[0] * out * 0.36, py - n[1] * out * 0.36) if exterior(op) else T(px + n[0] * 0.3, py + n[1] * 0.3)
        col = (40, 110, 170) if op["kind"] != "door" else (190, 90, 30)
        d.ellipse([tx - 21, ty - 21, tx + 21, ty + 21], fill=(255, 255, 255, 240), outline=col, width=3)
        d.text((tx, ty), TAG[op["id"]], font=F("SemiBold", 17), fill=col, anchor="mm")
        if op["kind"] == "door" and exterior(op):
            ex, ey = T(px + n[0] * out * 1.2, py + n[1] * out * 1.2); ix, iy = T(px + n[0] * out * 0.7, py + n[1] * out * 0.7)
            d.line([(ex, ey), (ix, iy)], fill=(190, 90, 30), width=5)
            ang = math.atan2(iy - ey, ix - ex)
            d.polygon([(ix, iy), (ix - 18 * math.cos(ang - 0.45), iy - 18 * math.sin(ang - 0.45)), (ix - 18 * math.cos(ang + 0.45), iy - 18 * math.sin(ang + 0.45))], fill=(190, 90, 30))
            d.text((ex + 10, ey - 40), "ENTRANCE", font=F("SemiBold", 20), fill=(190, 90, 30), anchor="mm")
    # dimension chains (outside faces + centre-line splits), drawn in the margins
    fdim = F("Medium", 18); g = (80, 82, 88)
    def hdim(xa, xb, y, off, label=None):
        (X0, Y0), (X1, _) = T(xa, y), T(xb, y); Y_ = Y0 + off
        d.line([(X0, Y_), (X1, Y_)], fill=g, width=2)
        for X_ in (X0, X1): d.line([(X_, Y_ - 9), (X_, Y_ + 9)], fill=g, width=2); d.line([(X_ - 6, Y_ + 6), (X_ + 6, Y_ - 6)], fill=g, width=2)
        d.text(((X0 + X1) / 2, Y_ - 16), label or f"{abs(xb - xa):.2f}", font=fdim, fill=INK, anchor="mm")
    def vdim(ya, yb, x, off, label=None):
        (X0, Y0), (_, Y1) = T(x, ya), T(x, yb); X_ = X0 + off
        d.line([(X_, Y0), (X_, Y1)], fill=g, width=2)
        for Y_ in (Y0, Y1): d.line([(X_ - 9, Y_), (X_ + 9, Y_)], fill=g, width=2); d.line([(X_ - 6, Y_ + 6), (X_ + 6, Y_ - 6)], fill=g, width=2)
        t = Image.new("RGBA", (160, 30), (0, 0, 0, 0)); ImageDraw.Draw(t).text((80, 15), label or f"{abs(yb - ya):.2f}", font=fdim, fill=INK, anchor="mm")
        t = t.rotate(90, expand=True); im.paste(t, (int(X_ - (34 if off < 0 else -4)), int((Y0 + Y1) / 2 - 80)), t)
    e = 0.1
    xs_top = sorted({minx, maxx} | {w["a"][0] for w in PLAN["walls"] if abs(w["a"][0] - w["b"][0]) < 1e-6 and min(w["a"][1], w["b"][1]) <= miny + 1e-6})
    for a_, b_ in zip(xs_top, xs_top[1:]): hdim(a_, b_, miny - e, -40)
    hdim(minx - e, maxx + e, miny - e, -95, f"{pw + 2 * e:.2f} (outside)")
    ys_l = sorted({miny, maxy} | {w["a"][1] for w in PLAN["walls"] if abs(w["a"][1] - w["b"][1]) < 1e-6 and min(w["a"][0], w["b"][0]) <= minx + 1e-6})
    for a_, b_ in zip(ys_l, ys_l[1:]): vdim(a_, b_, minx - e, -40)
    vdim(miny - e, maxy + e, minx - e, -95, f"{ph + 2 * e:.2f} (outside)")
    # bottom: openings on the bottom wall
    bot = [op for op in PLAN["openings"] if abs(WALLS[op["wallId"]]["a"][1] - maxy) < 1e-6 and abs(WALLS[op["wallId"]]["b"][1] - maxy) < 1e-6]
    pts = [minx]
    for op in bot:
        w = WALLS[op["wallId"]]; (ax, ay), u, n, L = wall_geo(w); c = op["t"] * L
        pts += sorted((ax + u[0] * (c - op["width"] / 2), ax + u[0] * (c + op["width"] / 2)))
    pts.append(maxx)
    for a_, b_ in zip(pts, pts[1:]): hdim(a_, b_, maxy + e, 40)
    hdim(minx - e, maxx + e, maxy + e, 95, f"{pw + 2 * e:.2f} (outside)")
    ys_r = sorted({miny, maxy} | {w["a"][1] for w in PLAN["walls"] if abs(w["a"][1] - w["b"][1]) < 1e-6 and max(w["a"][0], w["b"][0]) >= maxx - 1e-6})
    for a_, b_ in zip(ys_r, ys_r[1:]): vdim(a_, b_, maxx + e, 40)
    # right panel: title, schedule, areas, legend, scale
    px0 = W - PANEL + 20
    d.text((px0, 70), PLAN.get("name", PLAN["id"]).upper(), font=F("SemiBold", 40), fill=INK)
    d.text((px0, 124), "Technical top view · dimensions in metres", font=F("Regular", 21), fill=MUTED)
    y = 180; d.text((px0, y), "OPENINGS", font=F("SemiBold", 22), fill=INK); y += 36
    for op in PLAN["openings"]:
        kind = {"door": "Door", "window": "Window", "slider": "Sliding door"}[op["kind"]]
        extra = " · entrance" if op["kind"] == "door" and exterior(op) else ""
        sill = f" · sill {op['sill']:.2f}" if op["sill"] > 0 else ""
        d.text((px0, y), TAG[op["id"]], font=F("SemiBold", 19), fill=(190, 90, 30) if op["kind"] == "door" else (40, 110, 170))
        d.text((px0 + 56, y), f"{kind} {op['width']:.2f} × {op['height']:.2f}{sill}{extra}", font=F("Regular", 19), fill=INK); y += 31
    y += 22; d.text((px0, y), "AREAS", font=F("SemiBold", 22), fill=INK); y += 36
    for nm, a in A["rooms"].items():
        d.text((px0, y), nm, font=F("Regular", 19), fill=INK); d.text((px0 + 420, y), f"{a['net_m2']:.2f} m²", font=F("Regular", 19), fill=INK, anchor="ra"); y += 30
    d.line([(px0, y + 4), (px0 + 420, y + 4)], fill=(190, 190, 190), width=1); y += 14
    for lab, v in (("Net (inside wall faces)", A["net_total_m2"]), ("Gross (wall centre-lines)", A["gross_centreline_m2"]), ("Gross external", A["gross_external_m2"])):
        d.text((px0, y), lab, font=F("Medium", 19), fill=INK); d.text((px0 + 420, y), f"{v:.2f} m²", font=F("Medium", 19), fill=INK, anchor="ra"); y += 30
    y += 18
    d.text((px0, y), "Walls: exterior 200 mm, interior 120 mm, ceiling 2.70 m", font=F("Regular", 18), fill=MUTED)
    # scale bar
    sx0, sy0 = px0, H - 110; L1 = k * f
    for i in range(4):
        d.rectangle([sx0 + i * L1 / 2, sy0, sx0 + (i + 1) * L1 / 2, sy0 + 12], fill=INK if i % 2 == 0 else PAPER, outline=INK)
    d.text((sx0, sy0 + 20), "0", font=F("Regular", 18), fill=MUTED); d.text((sx0 + 2 * L1, sy0 + 20), "2 m", font=F("Regular", 18), fill=MUTED, anchor="ma")
    im.save(os.path.join(OUT, "technical_top.png"))


def P2_inside(x, y): return minx < x < maxx and miny < y < maxy


# ------------------------------------------------------------------ gallery compositions (1280 x 769)
GW, GH = 1280, 769
def cover(im, w, h, fx=0.5, fy=0.5):
    im = im.convert("RGB"); s = max(w / im.size[0], h / im.size[1]); im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
    x = int((im.size[0] - w) * fx); y = int((im.size[1] - h) * fy); return im.crop((x, y, x + w, y + h))


def title_band(im, text, sub=None, dark=True):
    d = ImageDraw.Draw(im, "RGBA"); f = F("SemiBold", 34)
    tw = d.textlength(text, font=f); bw = tw + 64
    d.rounded_rectangle([28, 26, 28 + bw, 26 + (78 if not sub else 104)], 12, fill=(22, 24, 28, 215) if dark else (255, 255, 255, 230))
    d.text((60, 46), text, font=f, fill=(255, 255, 255) if dark else INK)
    if sub: d.text((60, 92), sub, font=F("Regular", 18), fill=(200, 202, 206) if dark else MUTED)


def label(im, x, y, text, dark=True):
    d = ImageDraw.Draw(im, "RGBA"); f = F("Medium", 17); w = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + w + 24, y + 34], 8, fill=(22, 24, 28, 200) if dark else (255, 255, 255, 225))
    d.text((x + 12, y + 6), text, font=f, fill=(255, 255, 255) if dark else INK)


def gallery():
    out = []
    if arg("--doll"):
        im = cover(Image.open(arg("--doll")), GW, GH); title_band(im, "2D FLOOR PLAN TO 3D APARTMENT")
        p = os.path.join(OUT, "gallery_a_dollhouse.jpg"); im.save(p, quality=92); out.append(p)
    if arg("--plan2d") and arg("--top"):
        im = Image.new("RGB", (GW, GH), PAPER); pad = 18; cw = (GW - 3 * pad) // 2; ch = GH - 130 - pad
        a = Image.open(arg("--plan2d")).convert("RGB").crop((60, 40, 1800, 1420)); b = Image.open(arg("--top")).convert("RGB")
        _, T0, k = top_map(arg("--top")); x0, y0 = T0(minx - 0.6, miny - 0.6); x1, y1 = T0(maxx + 0.6, maxy + 0.6)
        b = b.crop((int(x0), max(0, int(y0)), int(x1), min(b.size[1], int(y1))))
        for i, src in enumerate((a, b)):
            s = min(cw / src.size[0], ch / src.size[1]); t = src.resize((int(src.size[0] * s), int(src.size[1] * s)), Image.LANCZOS)
            im.paste(t, (pad + i * (cw + pad) + (cw - t.size[0]) // 2, 118 + (ch - t.size[1]) // 2))
        title_band(im, "ACCURATE FLOORPLAN RECONSTRUCTION", dark=True)
        label(im, pad + 10, GH - 52, "2D PLAN", dark=True); label(im, pad + cw + pad + 10, GH - 52, "3D MODEL", dark=True)
        p = os.path.join(OUT, "gallery_b_plan_vs_3d.jpg"); im.save(p, quality=92); out.append(p)
    if arg("--living") and arg("--kitchen") and arg("--bedroom"):
        im = Image.new("RGB", (GW, GH), (18, 19, 22)); g = 8; lw = 820; rw = GW - lw - 3 * g; rh = (GH - 3 * g) // 2
        im.paste(cover(Image.open(arg("--living")), lw, GH - 2 * g), (g, g))
        im.paste(cover(Image.open(arg("--kitchen")), rw, rh), (lw + 2 * g, g))
        im.paste(cover(Image.open(arg("--bedroom")), rw, rh), (lw + 2 * g, rh + 2 * g))
        title_band(im, "COMPLETE INTERIOR VISUALIZATION")
        label(im, g + 14, GH - 52, "Living & dining"); label(im, lw + 2 * g + 14, rh - 40, "Kitchen"); label(im, lw + 2 * g + 14, GH - 52, "Bedroom")
        p = os.path.join(OUT, "gallery_c_interiors.jpg"); im.save(p, quality=92); out.append(p)
    if arg("--styles"):
        fs = arg("--styles").split(","); names = ["Modern", "Scandinavian", "Japandi"]
        im = Image.new("RGB", (GW, GH), (18, 19, 22)); g = 8; cw = (GW - 4 * g) // 3
        for i, (f_, n_) in enumerate(zip(fs, names)):
            im.paste(cover(Image.open(f_), cw, GH - 2 * g, fx=0.42), (g + i * (cw + g), g))
            label(im, g + i * (cw + g) + 14, GH - 52, n_)
            s16 = cover(Image.open(f_), 1920, 1080); label(s16, 32, 1080 - 70, f"{n_} · same camera, same light")
            s16.save(os.path.join(OUT, f"style_{n_.lower()}_16x9.jpg"), quality=92)
        title_band(im, "ONE ROOM, THREE STYLES")
        p = os.path.join(OUT, "gallery_d_styles.jpg"); im.save(p, quality=92); out.append(p)
    return out


if __name__ == "__main__":
    if REP:
        r = proof(); print("proof max dev", r["max_dev_mm"], "all ok", r["all_ok"])
        if arg("--top"): overlay(arg("--top")); technical(arg("--top"))
    print(gallery())
