"""Blender render worker for Floorplan 3D Studio.

Takes a plan JSON exported by the web app ("Plan JSON" button, or blender/plans/*.json) and builds a
photoreal scene: walls with real door/window openings, floors with PBR textures, baseboards, CC0
furniture sized to the plan, sun + HDRI sky. Renders top / isometric / interior views with Cycles.

  blender -b -P blender/render_plan.py -- --plan blender/plans/twobed.json --out renders/twobed \
      [--views top,iso,interior1,interior2] [--samples 128] [--pct 100] [--hero] [--save-blend]
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from common import (reset_scene, link, mesh_obj, box, pbr_material, set_mat, world_hdri, cycles, camera,
                    look_at, render_to, uv_box, ASSETS, bevel)
import furniture_lib as FL

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = json.load(open(arg("--plan")))
FOOT = json.load(open(os.path.join(HERE, "plans", "furniture_footprints.json")))
OUT = arg("--out", os.path.join(HERE, "renders", PLAN["id"])); os.makedirs(OUT, exist_ok=True)
VIEWS = [v for v in arg("--views", "top,iso,interior1").split(",") if v]
SAMPLES = int(arg("--samples", "64")); SAMPLES_INT = int(arg("--samples-interior", "96")); PCT = int(arg("--pct", "100"))
SHOTS = json.load(open(os.path.join(HERE, "shots.json"))).get(PLAN["id"], {})
STYLE = arg("--style", PLAN.get("style", "modern"))
TAG = arg("--tag", "")                      # output name suffix, e.g. "_modern"
SHOTS.update(SHOTS.get("styles", {}).get(STYLE, {}))

P = lambda x, y, z=0.0: Vector((x, -y, z))   # plan (x, y) metres -> Blender (x, -y)

sc = reset_scene()
M = FL.Mats(STYLE)
COL = {k: bpy.data.collections.new(k) for k in ("Walls", "Openings", "WallsCut", "Floors", "Furniture", "Ceiling", "Env")}
CUT = float(arg("--cut", "1.2"))  # wall height for the dollhouse cutaway view
for c in COL.values(): sc.collection.children.link(c)

def put(o, coll):
    for c in list(o.users_collection): c.objects.unlink(o)
    COL[coll].objects.link(o); return o

# ------------------------------------------------------------------ walls with openings
walls = {w["id"]: w for w in PLAN["walls"]}

def wall_spans(w, ops):
    a, b = Vector(w["a"]), Vector(w["b"]); L = (b - a).length; H = w["height"]
    iv = sorted([(max(0, o["t"] * L - o["width"] / 2), min(L, o["t"] * L + o["width"] / 2), o) for o in ops], key=lambda q: q[0])
    out = []; cur = 0.0
    for s, e, o in iv:
        if s > cur: out.append((cur, s, 0, H))
        if o["sill"] > 0: out.append((s, e, 0, o["sill"]))
        top = o["sill"] + o["height"]
        if top < H: out.append((s, e, top, H))
        cur = max(cur, e)
    if cur < L: out.append((cur, L, 0, H))
    return out, L

def wall_frame(w):
    a = P(*w["a"]); b = P(*w["b"]); d = b - a; L = d.length
    ang = math.atan2(d.y, d.x)
    return a, ang, L

def place_local(o, a, ang):
    # NB: use matrix_basis (matrix_world is stale until the depsgraph updates)
    o.matrix_basis = Matrix.Translation(a) @ Matrix.Rotation(ang, 4, "Z") @ o.matrix_basis

for w in PLAN["walls"]:
    ops = [o for o in PLAN["openings"] if o["wallId"] == w["id"]]
    spans, L = wall_spans(w, ops)
    a, ang, _ = wall_frame(w); t = w["thickness"]
    for (s, e, z0, z1) in spans:
        ext0 = t / 2 if s <= 1e-4 else 0; ext1 = t / 2 if e >= L - 1e-4 else 0
        x0, x1 = s - ext0, e + ext1
        o = box(f"Wall_{w['id']}", (x1 - x0, t, z1 - z0), ((x0 + x1) / 2, 0, (z0 + z1) / 2))
        o.data.materials.append(M.wall); o.data.materials.append(M.wall_cut)
        if abs(z1 - w["height"]) < 1e-6: o.data.polygons[1].material_index = 1
        place_local(o, a, ang); put(o, "Walls")
    # openings
    for op in ops:
        c = op["t"] * L; wd = op["width"]; sill = op["sill"]; hh = op["height"]
        parts = []
        fr = 0.045; depth = min(t, 0.07)
        if op["kind"] in ("window", "slider"):
            # frame
            parts += [FL.rb("FrameL", (fr, depth, hh), (c - wd / 2 + fr / 2, 0, sill + hh / 2), M.metal_black, bev=0.003),
                      FL.rb("FrameR", (fr, depth, hh), (c + wd / 2 - fr / 2, 0, sill + hh / 2), M.metal_black, bev=0.003),
                      FL.rb("FrameT", (wd, depth, fr), (c, 0, sill + hh - fr / 2), M.metal_black, bev=0.003),
                      FL.rb("FrameB", (wd, depth, fr), (c, 0, sill + fr / 2), M.metal_black, bev=0.003)]
            nmull = 1 if wd > 1.0 else 0
            if op["kind"] == "slider": nmull = 1 if wd < 2.8 else 2
            for k in range(nmull):
                x = c - wd / 2 + wd * (k + 1) / (nmull + 1)
                parts.append(FL.rb("Mullion", (fr * 0.8, depth, hh - 2 * fr), (x, 0, sill + hh / 2), M.metal_black, bev=0.002))
            parts.append(FL.rb("Glass", (wd - 2 * fr, 0.008, hh - 2 * fr), (c, 0, sill + hh / 2), M.glass, bev=0))
            if sill > 0:
                parts.append(FL.rb("Sill", (wd + 0.06, t + 0.04, 0.025), (c, 0, sill - 0.0125), M.white, bev=0.004))
        else:  # door: casing + leaf open ~80 deg
            parts += [FL.rb("CasingL", (0.04, t + 0.02, hh), (c - wd / 2 + 0.02, 0, hh / 2), M.white, bev=0.004),
                      FL.rb("CasingR", (0.04, t + 0.02, hh), (c + wd / 2 - 0.02, 0, hh / 2), M.white, bev=0.004),
                      FL.rb("CasingT", (wd, t + 0.02, 0.04), (c, 0, hh - 0.02), M.white, bev=0.004)]
            leafW = wd - 0.08
            s = -1 if op.get("flip") else 1
            hinge_x = c - wd / 2 + 0.04
            leaf = FL.rb("DoorLeaf", (leafW, 0.04, hh - 0.04), (leafW / 2, 0, (hh - 0.04) / 2), M.wood, bev=0.004, uv_long=2)
            knob = FL.rb("Handle", (0.12, 0.05, 0.02), (leafW - 0.08, 0, 1.0), M.brass, bev=0.006)
            piv = bpy.data.objects.new("DoorPivot", None); put(piv, "Openings")
            leaf.parent = piv; knob.parent = piv
            ang_open = 0.0 if op["id"] in SHOTS.get("closed_doors", []) else math.radians(80)   # exterior doors can be shown closed
            piv.location = (hinge_x, 0, 0); piv.rotation_euler = (0, 0, -s * ang_open)  # same swing as src/three/build.ts
            parts += [leaf, knob]
            put(leaf, "Openings"); put(knob, "Openings")
            place_local(piv, a, ang)
            parts = [p for p in parts if p not in (leaf, knob)]
        for p in parts:
            place_local(p, a, ang); put(p, "Openings")

# cutaway walls (dollhouse view): same spans clipped at CUT height, window sills kept, doors/glass dropped
for w in PLAN["walls"]:
    ops = [o for o in PLAN["openings"] if o["wallId"] == w["id"]]
    spans, L = wall_spans(w, ops)
    a, ang, _ = wall_frame(w); t = w["thickness"]
    for (s_, e, z0, z1) in spans:
        if z0 >= CUT - 1e-6: continue
        z1 = min(z1, CUT)
        ext0 = t / 2 if s_ <= 1e-4 else 0; ext1 = t / 2 if e >= L - 1e-4 else 0
        x0, x1 = s_ - ext0, e + ext1
        o = box(f"WallCut_{w['id']}", (x1 - x0, t, z1 - z0), ((x0 + x1) / 2, 0, (z0 + z1) / 2))
        o.data.materials.append(M.wall); o.data.materials.append(M.wall_cut)
        if abs(z1 - CUT) < 1e-6: o.data.polygons[1].material_index = 1
        place_local(o, a, ang); put(o, "WallsCut")
    for op in ops:
        if op["kind"] == "window" and op["sill"] < CUT:
            c = op["t"] * L
            o = FL.rb("SillCut", (op["width"] + 0.06, t + 0.04, 0.025), (c, 0, op["sill"] - 0.0125), M.white, bev=0.004)
            place_local(o, a, ang); put(o, "WallsCut")

def union_walls(coll, prefix):
    """Join the wall boxes and boolean-union them (exact, self-intersection) so corners and T-junctions have no
    coplanar overlapping faces (those render as black seams in Cycles)."""
    objs = [o for o in COL[coll].objects if o.name.startswith(prefix) and o.type == "MESH"]
    if len(objs) < 2: return
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active; j.name = f"{prefix}Union"
    empty = bpy.data.collections.new(f"{prefix}_none")
    m = j.modifiers.new("Union", "BOOLEAN"); m.operation = "UNION"; m.solver = "EXACT"
    m.operand_type = "COLLECTION"; m.collection = empty; m.use_self = True
    bpy.ops.object.modifier_apply(modifier="Union")

for _c in ("Walls", "WallsCut"):
    for _o in COL[_c].objects: _o.select_set(False)
union_walls("Walls", "Wall_")
union_walls("WallsCut", "WallCut_")

# ------------------------------------------------------------------ floors + baseboards
FLOOR_TEX = {"wood": ("laminate_floor_02", 0.5), "tile": ("marble_01", 0.7), "stone": ("marble_01", 0.4),
             "concrete": ("granite_tile", 0.3), "carpet": (None, 1)}
fmats = {}
def floor_mat(kind):
    if kind in fmats: return fmats[kind]
    tex, sc_ = FLOOR_TEX[kind]
    if kind == "carpet":
        m = M.rug_mat("Carpet", (0.78, 0.74, 0.68), (0.78, 0.74, 0.68))
    elif kind == "wood":
        tex, sc_ = M.X["floor_wood"]
        m = pbr_material("Floor_wood", tex=tex, scale=sc_, hsv=M.S["floor_hsv"], rough=0.6, coat=0.04, rough_mul=1.35)
    else:
        m = pbr_material(f"Floor_{kind}", tex=tex, scale=sc_, rough=0.35, coat=0.1 if kind == "tile" else 0)
    fmats[kind] = m; return m

for r in PLAN["rooms"]:
    pts = [P(x, y, 0) for x, y in r["points"]]
    bm = bmesh.new()
    vs = [bm.verts.new((p.x, p.y, 0.0)) for p in pts]
    f = bm.faces.new(vs); bm.normal_update()
    if f.normal.z < 0: f.normal_flip()
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]: v.co.z = 0.012
    me = bpy.data.meshes.new(r["name"]); bm.to_mesh(me); bm.free()
    o = link(bpy.data.objects.new(f"Floor_{r['name']}", me)); put(o, "Floors")
    uvl = me.uv_layers.new(name="UVMap")
    for li, lp in enumerate(me.loops):
        co = me.vertices[lp.vertex_index].co; uvl.data[li].uv = (co.x, co.y)
    set_mat(o, floor_mat(r["floor"]))

# thresholds: where two rooms with different floors meet without a wall (open plan), lay a 30 mm oak/brass strip on the line
_edges = {}
for r in PLAN["rooms"]:
    pts_ = r["points"]
    for i in range(len(pts_)):
        a_, b_ = tuple(pts_[i]), tuple(pts_[(i + 1) % len(pts_)])
        _edges.setdefault(tuple(sorted((a_, b_))), []).append(r["floor"])

def seg_wall(p, q):
    """Wall that contains room edge p-q (collinear, overlapping)."""
    p, q = Vector(p), Vector(q)
    for w in PLAN["walls"]:
        a, b = Vector(w["a"]), Vector(w["b"]); d = b - a
        if d.length < 1e-6: continue
        n = Vector((-d.y, d.x)).normalized()
        if abs((p - a).dot(n)) < 0.02 and abs((q - a).dot(n)) < 0.02:
            tp = (p - a).dot(d) / d.length_squared; tq = (q - a).dot(d) / d.length_squared
            if max(tp, tq) > 0.01 and min(tp, tq) < 0.99: return w
    return None

for r in PLAN["rooms"]:
    pts = [Vector(p) for p in r["points"]]; n = len(pts)
    # polygon orientation (plan coords): inward normal
    area = sum(pts[i].x * pts[(i + 1) % n].y - pts[(i + 1) % n].x * pts[i].y for i in range(n)) / 2
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]; d = q - p; L = d.length
        if L < 0.05: continue
        w = seg_wall(p, q)
        if not w: continue
        t = w["thickness"]; u = d / L
        inward = Vector((-u.y, u.x)) if area > 0 else Vector((u.y, -u.x))
        # cut out door/slider openings
        a, b = Vector(w["a"]), Vector(w["b"]); WL = (b - a).length; wu = (b - a) / WL
        holes = []
        for op in PLAN["openings"]:
            if op["wallId"] != w["id"] or op["sill"] > 0.05: continue
            cpt = a + wu * op["t"] * WL; s = (cpt - p).dot(u)
            holes.append((s - op["width"] / 2, s + op["width"] / 2))
        cur = t / 2; spans = []
        for h0, h1 in sorted(holes):
            if h0 > cur: spans.append((cur, h0))
            cur = max(cur, h1)
        if cur < L - t / 2: spans.append((cur, L - t / 2))
        for s0, s1 in spans:
            if s1 - s0 < 0.05: continue
            mid = p + u * ((s0 + s1) / 2) + inward * (t / 2 + 0.006)
            ang = math.atan2(-u.y, u.x)
            bb = FL.rb("Baseboard", (s1 - s0, 0.012, 0.08), (0, 0, 0), M.white, bev=0.002)
            bb.location = P(mid.x, mid.y, 0.04); bb.rotation_euler = (0, 0, ang); put(bb, "Walls")

for (a_, b_), fl in _edges.items():
    if len(fl) == 2 and fl[0] != fl[1] and not seg_wall(a_, b_):
        A_, B_ = Vector(a_), Vector(b_); m_ = (A_ + B_) / 2; d_ = B_ - A_
        th = FL.rb("Threshold", (d_.length, 0.03, 0.004), (0, 0, 0), M.brass if STYLE == "modern" else M.wood, bev=0.001, uv=False)
        th.location = P(m_.x, m_.y, 0.014); th.rotation_euler = (0, 0, math.atan2(-d_.y, d_.x)); put(th, "Floors")

# ------------------------------------------------------------------ furniture
for it in PLAN["items"]:
    fdef = FOOT.get(it["type"]); bld = FL.BUILDERS.get(it["type"])
    if not fdef or not bld: print("skip item", it["type"]); continue
    objs = bld(M, fdef, it)
    root = bpy.data.objects.new(f"Item_{it['type']}_{it['id']}", None); put(root, "Furniture")
    for o in objs:
        put(o, "Furniture")
        if o.parent is None: o.parent = root
    nd = SHOTS.get("nudge", {}).get(it["id"], (0, 0))   # small layout fixes for footprints that overlap in the source plan
    root.location = P(it["x"] + nd[0], it["y"] + nd[1], 0.012); root.rotation_euler = (0, 0, -math.radians(it["rot"]))

# round-3 decor/fill items from shots.json (plan coords, own footprints), optionally per style
for k, it in enumerate(SHOTS.get("extra_items", [])):
    if it.get("styles") and STYLE not in it["styles"]: continue
    bld = FL.BUILDERS.get(it["type"])
    if not bld: print("skip extra", it["type"]); continue
    objs = bld(M, {"w": it["w"], "d": it["d"]}, {"id": f"x{k}"})
    root = bpy.data.objects.new(f"Extra_{it['type']}_{k}", None); put(root, "Furniture")
    for o in objs:
        put(o, "Furniture")
        if o.parent is None: o.parent = root
    root.location = P(it["x"], it["y"], 0.012 + it.get("z", 0)); root.rotation_euler = (0, 0, -math.radians(it.get("rot", 0)))

for k, a_ in enumerate(SHOTS.get("art", [])):
    root = bpy.data.objects.new(f"ArtX_{k}", None); put(root, "Furniture")
    for o in FL.wall_art(M, w=a_["w"], h=a_["h"], z=a_["z"], y=0.0, seed=k + 3):
        put(o, "Furniture"); o.parent = root
    root.location = P(a_["x"], a_["y"], 0); root.rotation_euler = (0, 0, -math.radians(a_.get("rot", 0)))

# curtains on the room side of every window / slider: two gathered panels + rod
H_ = max(w["height"] for w in PLAN["walls"])
xs0 = [p[0] for w in PLAN["walls"] for p in (w["a"], w["b"])]; ys0 = [p[1] for w in PLAN["walls"] for p in (w["a"], w["b"])]
def inside(x, y): return min(xs0) < x < max(xs0) and min(ys0) < y < max(ys0)
for op in PLAN["openings"]:
    if op["kind"] not in ("window", "slider") or op["width"] < 1.0: continue
    w = walls[op["wallId"]]; A, B = Vector(w["a"]), Vector(w["b"]); d = B - A; L = d.length; u = d / L
    nrm = Vector((-u.y, u.x)); c = A + u * op["t"] * L
    if not inside(*(c + nrm * 0.5)): nrm = -nrm
    off = w["thickness"] / 2 + 0.07
    pw_ = 0.42 if op["kind"] == "window" else 0.5; hc = H_ - 0.08
    for side in (-1, 1):
        x0 = op["width"] / 2 - 0.12 if side > 0 else -op["width"] / 2 - pw_ + 0.12
        cp = FL.curtain_panel(M, pw_, hc - 0.02, seed=side + 2)
        base = c + u * x0 + nrm * off
        cp.location = P(base.x, base.y, 0.02); cp.rotation_euler = (0, 0, math.atan2(-u.y, u.x)); put(cp, "Furniture")
    mid = c + nrm * off
    rod = FL.cyl("CurtainRod", 0.012, op["width"] + 1.0, (0, 0, 0), M.metal_black if STYLE != "scandinavian" else M.wood, segs=12, axis="X")
    rod.location = P(mid.x, mid.y, hc); rod.rotation_euler = (0, 0, math.atan2(-u.y, u.x)); rod["upper"] = True; put(rod, "Furniture")

# ceiling lights (pendants / downlights), visible + lit only in interior shots
for k, l_ in enumerate(SHOTS.get("lights", [])):
    kind = l_.get("kind", "pendant")
    objs = FL.pendant(M, drop=l_.get("drop", 0.7), ceiling=H_, size=l_.get("size", 1.0)) if kind == "pendant" else FL.downlight(M, H_, l_.get("power", 18))
    root = bpy.data.objects.new(f"Light_{k}", None); put(root, "Ceiling")
    for o in objs:
        put(o, "Ceiling"); o.parent = root
    root.location = P(l_["x"], l_["y"], 0)

# wall art above sofas that stand against a wall (decor, interior shots)
def wall_behind(px, py, tol=0.12):
    q = Vector((px, py))
    for w in PLAN["walls"]:
        a, b = Vector(w["a"]), Vector(w["b"]); d = b - a; L2 = d.length_squared
        if L2 < 1e-9: continue
        t = max(0, min(1, (q - a).dot(d) / L2))
        if (a + d * t - q).length < w["thickness"] / 2 + tol: return w, t
    return None, None

def opening_clash(w, t, half_w, z0, z1):
    L = (Vector(w["b"]) - Vector(w["a"])).length; c = t * L
    for op in PLAN["openings"]:
        if op["wallId"] != w["id"]: continue
        oc = op["t"] * L
        if abs(oc - c) < half_w + op["width"] / 2 + 0.1 and op["sill"] < z1 and op["sill"] + op["height"] > z0: return True
    return False

ART = {"sofa3": (1.1, 0.7, 1.55), "sofa2": (0.9, 0.6, 1.55), "bedDouble": (1.0, 0.6, 1.6), "bedSingle": (0.7, 0.5, 1.6)}
for it in PLAN["items"]:
    if it["type"] not in ART: continue
    f = FOOT[it["type"]]; r = math.radians(it["rot"]); aw, ah, az = ART[it["type"]]
    # the back of a piece is local -z in the app frame (front faces +z); rotation is clockwise in plan
    bx, by = it["x"] + math.sin(r) * (f["d"] / 2 + 0.05), it["y"] - math.cos(r) * (f["d"] / 2 + 0.05)
    w, t = wall_behind(bx, by)
    if not w or opening_clash(w, t, aw / 2, az - ah / 2, az + ah / 2): continue
    root = bpy.data.objects.new(f"Art_{it['id']}", None); put(root, "Furniture")
    for o in FL.wall_art(M, w=aw, h=ah, z=az, y=f["d"] / 2 + 0.015):
        put(o, "Furniture"); o.parent = root
    root.location = P(it["x"], it["y"], 0.012); root.rotation_euler = (0, 0, -math.radians(it["rot"]))

# ------------------------------------------------------------------ automated clash check (furniture vs furniture / walls)
def clash_check():
    bpy.context.view_layer.update()
    def top(o):
        while o.parent is not None and o.parent.name.split(".")[0] not in ("Chair",) and o.parent.parent is not None: o = o.parent
        return o
    def item_of(o):
        while o.parent is not None: o = o.parent
        return o
    def sub_of(o):   # chair root inside a dining set, else None
        while o.parent is not None:
            if o.parent.name.startswith("Chair"): return o.parent.name
            o = o.parent
        return None
    boxes = []
    for o in COL["Furniture"].objects:
        if o.type != "MESH" or o.get("upper") or o.name.startswith(("Rug", "Runner", "Curtain", "Throw")): continue
        it = item_of(o).name
        if it.startswith(("Item_rug", "Extra_rug", "Art")): continue
        ps = [o.matrix_world @ Vector(c) for c in o.bound_box]
        mn = Vector((min(p.x for p in ps), min(p.y for p in ps), min(p.z for p in ps))); mx = Vector((max(p.x for p in ps), max(p.y for p in ps), max(p.z for p in ps)))
        boxes.append((it, sub_of(o), o.name, mn, mx))
    objs = {o.name: o for o in COL["Furniture"].objects}
    def verts_in(o, bx, eps=0.002):
        """refine an AABB hit: does any real vertex of o lie inside the other part's box?"""
        mw = o.matrix_world; mn, mx = bx[3], bx[4]
        for v in o.data.vertices:
            p = mw @ v.co
            if all(mn[i] + eps < p[i] < mx[i] - eps for i in range(3)): return True
        return False
    def ov(a, b): return [min(a[4][i], b[4][i]) - max(a[3][i], b[3][i]) for i in range(3)]
    issues = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            same = a[0] == b[0]
            if same and not ((a[1] is None) != (b[1] is None) or (a[1] and b[1] and a[1] != b[1])): continue   # parts of one piece
            if same and "dining" not in a[0] and "bistro" not in a[0]: continue
            o3 = ov(a, b)
            if min(o3) > 0.01 and (verts_in(objs[a[2]], b) or verts_in(objs[b[2]], a)):
                # chairs tucked under a table top are fine: only flag real volume overlap below the top
                issues.append({"a": f"{a[0]}/{a[2]}", "b": f"{b[0]}/{b[2]}", "overlap_m": [round(v, 3) for v in o3]})
    # furniture footprint vs wall solids (2D, plan walls as rectangles)
    for it in PLAN["items"]:
        f = FOOT.get(it["type"])
        if not f or it["type"] in ("rug", "rugRound"): continue
        r = math.radians(it["rot"]); hw, hd = f["w"] / 2 - 0.01, f["d"] / 2 - 0.01
        cs = [(it["x"] + dx * math.cos(r) - dy * math.sin(r), it["y"] + dx * math.sin(r) + dy * math.cos(r)) for dx in (-hw, hw) for dy in (-hd, hd)]
        for w in PLAN["walls"]:
            A, B = Vector(w["a"]), Vector(w["b"]); d = B - A; L = d.length; u = d / L; n = Vector((-u.y, u.x))
            ts = [(Vector(c) - A).dot(u) for c in cs]; ns_ = [(Vector(c) - A).dot(n) for c in cs]
            if max(ts) > 0.02 and min(ts) < L - 0.02 and min(ns_) < w["thickness"] / 2 - 0.005 and max(ns_) > -w["thickness"] / 2 + 0.005:
                issues.append({"a": f"item {it['id']} {it['type']}", "b": f"wall {w['id']}", "overlap_m": None})
    return issues

CLASH = clash_check()
print("CLASH", len(CLASH), json.dumps(CLASH[:40]))

# ------------------------------------------------------------------ ceiling (interior shots only)
xs = [p[0] for w in PLAN["walls"] for p in (w["a"], w["b"])]; ys = [p[1] for w in PLAN["walls"] for p in (w["a"], w["b"])]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
H = max(w["height"] for w in PLAN["walls"])
ceil = box("Ceiling", (maxx - minx + 0.4, maxy - miny + 0.4, 0.05), P((minx + maxx) / 2, (miny + maxy) / 2, H + 0.025))
set_mat(ceil, pbr_material("CeilingPaint", color=(0.85, 0.85, 0.84), rough=0.9)); put(ceil, "Ceiling")

# ------------------------------------------------------------------ environment
ground = box("Ground", (80, 80, 0.02), (0, 0, -0.011))
set_mat(ground, pbr_material("Ground", color=(0.78, 0.78, 0.76), rough=0.95)); put(ground, "Env")
W_SKY = world_hdri(os.path.join(ASSETS, "hdris/kloofendal_48d_partly_cloudy_puresky/kloofendal_48d_partly_cloudy_puresky_2k.hdr"),
                   strength=1.0, rot_z=math.radians(float(SHOTS.get("hdri_rot", 120))))

def interior_world(name, strength, view_strength, rot):
    """Garden HDRI seen through the windows: full strength for lighting, dimmed for camera/transmission rays so the
    view outside is not blown out."""
    w = bpy.data.worlds.new("WorldInterior"); w.use_nodes = True
    nt = w.node_tree; N = nt.nodes; L = nt.links; N.clear()
    out = N.new("ShaderNodeOutputWorld"); tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value[2] = rot
    env = N.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(os.path.join(ASSETS, f"hdris/{name}/{name}_2k.hdr"))
    L.new(tc.outputs["Generated"], mp.inputs["Vector"]); L.new(mp.outputs["Vector"], env.inputs["Vector"])
    lp = N.new("ShaderNodeLightPath"); mx = N.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
    L.new(lp.outputs["Is Camera Ray"], mx.inputs[0]); L.new(lp.outputs["Is Transmission Ray"], mx.inputs[1])
    mr = N.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = strength; mr.inputs["To Max"].default_value = view_strength
    L.new(mx.outputs[0], mr.inputs["Value"])
    bg = N.new("ShaderNodeBackground"); L.new(env.outputs["Color"], bg.inputs["Color"]); L.new(mr.outputs["Result"], bg.inputs["Strength"])
    L.new(bg.outputs["Background"], out.inputs["Surface"])
    return w
W_INT = interior_world(SHOTS.get("int_hdri", "greenwich_park_02"), float(SHOTS.get("int_hdri_strength", 1.2)),
                       float(SHOTS.get("int_view_strength", 0.45)), math.radians(float(SHOTS.get("int_hdri_rot", 0))))
sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = float(SHOTS.get("sun", 3.2)); sun_d.angle = math.radians(3)
sun_d.color = (1.0, 0.95, 0.88)
sun = link(bpy.data.objects.new("Sun", sun_d)); put(sun, "Env")
sun.rotation_euler = (math.radians(SHOTS.get("sun_tilt", 38)), 0, math.radians(SHOTS.get("sun_az", 35)))

# ------------------------------------------------------------------ cameras / renders
cx, cy = (minx + maxx) / 2, (miny + maxy) / 2; pw, ph_ = maxx - minx, maxy - miny
cycles(sc, samples=SAMPLES, res=(1920, 1080), pct=PCT)
sc.cycles.max_bounces = 10; sc.cycles.diffuse_bounces = 6
times = {}

def vis(ceiling=False, uppers=True, cut=False):
    for o in COL["Ceiling"].objects: o.hide_render = not ceiling
    for o in COL["Env"].objects:
        if o.name.startswith("Ground"): o.hide_render = ceiling
    sc.world = W_INT if ceiling else W_SKY
    for k in ("Walls", "Openings"):
        for o in COL[k].objects: o.hide_render = cut
    for o in COL["WallsCut"].objects: o.hide_render = not cut
    for o in COL["Furniture"].objects:
        if o.get("tall") and cut: o.hide_render = True
        elif o.get("tall"): o.hide_render = False
    for o in COL["Furniture"].objects:
        if o.get("upper"): o.hide_render = not uppers

def res(hero):
    sc.render.resolution_x, sc.render.resolution_y = (2560, 1440) if hero else (1920, 1080)

for v in VIEWS:
    hero = v.endswith("_hero"); base = v.replace("_hero", ""); res(hero)
    sc.view_settings.exposure = 0.0; sc.cycles.samples = SAMPLES
    tilt = SHOTS.get("sun_tilt_top", 18) if base in ("top", "iso", "dollhouse") else SHOTS.get("sun_tilt", 38)
    sun.rotation_euler = (math.radians(tilt), 0, math.radians(SHOTS.get("sun_az", 35)))
    if base == "top":
        vis(False, uppers=False)
        sc.view_settings.exposure = float(SHOTS.get("top_exposure", 0.35))
        rot90 = ph_ > pw
        span_x, span_y = (ph_, pw) if rot90 else (pw, ph_)
        scale = max(span_x * 1.1, span_y * 1.1 * 16 / 9)
        cam = camera("CamTop", P(cx, cy, 40), P(cx, cy, 0), ortho=scale)
        cam.rotation_euler = (0, 0, math.radians(90) if rot90 else 0)
    elif base in ("iso", "dollhouse"):
        vis(False, uppers=base == "iso", cut=base == "dollhouse")
        az = math.radians(SHOTS.get("iso_az", -35)); el = math.radians(SHOTS.get("iso_el", 42))
        dist = 60
        tgt = P(cx, cy, 0.6)
        loc = tgt + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
        diag = math.hypot(pw, ph_)
        cam = camera("CamIso", loc, tgt, ortho=10)
        bpy.context.view_layer.update()
        inv = cam.matrix_world.inverted()
        zt = CUT if base == "dollhouse" else H
        cs = [inv @ P(x, y, z) for x in (minx - 0.2, maxx + 0.2) for y in (miny - 0.2, maxy + 0.2) for z in (0, zt)]
        x0, x1 = min(c.x for c in cs), max(c.x for c in cs); y0, y1 = min(c.y for c in cs), max(c.y for c in cs)
        cam.data.ortho_scale = max(x1 - x0, (y1 - y0) * 16 / 9) * float(SHOTS.get("iso_zoom", 1.06))
        cam.data.shift_x = ((x0 + x1) / 2) / cam.data.ortho_scale; cam.data.shift_y = ((y0 + y1) / 2) / cam.data.ortho_scale
    else:  # interior shots from shots.json
        s = SHOTS[base]; vis(True, uppers=True); sc.cycles.samples = SAMPLES_INT
        cam = camera(f"Cam_{base}", P(*s["pos"]), P(*s["look"]), lens=s.get("lens", 20))
        sc.view_settings.exposure = s.get("exposure", 0.6)
        # soft ceiling fill lights in the shot's rooms (not visible to camera)
        for i, (lx, ly, pw_, sz) in enumerate(s.get("fills", [])):
            ld = bpy.data.lights.new(f"Fill{i}", "AREA"); ld.energy = pw_; ld.size = sz; ld.color = (1.0, 0.92, 0.82)
            lo = link(bpy.data.objects.new(f"Fill{i}", ld)); lo.location = P(lx, ly, H - 0.05)
            lo.visible_camera = False; put(lo, "Env")
    times[v] = render_to(sc, cam, os.path.join(OUT, f"{PLAN['id']}{TAG}_{v}.png"))
    for o in list(COL["Env"].objects):
        if o.name.startswith("Fill"): bpy.data.objects.remove(o)

if "--save-blend" in argv:
    # deliverable layout: Architecture / Furniture / Lighting / Cameras / Environment, textures packed
    top = {k: bpy.data.collections.new(k) for k in ("Architecture", "Lighting", "Cameras", "Environment")}
    for k in top.values(): sc.collection.children.link(k)
    for k in ("Walls", "Openings", "WallsCut", "Floors", "Ceiling"):
        sc.collection.children.unlink(COL[k]); top["Architecture"].children.link(COL[k])
    sc.collection.children.unlink(COL["Env"]); top["Environment"].children.link(COL["Env"])
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            for c in list(o.users_collection): c.objects.unlink(o)
            top["Lighting"].objects.link(o)
        elif o.type == "CAMERA":
            for c in list(o.users_collection): c.objects.unlink(o)
            top["Cameras"].objects.link(o)
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("pack failed", e)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{PLAN['id']}{TAG}.blend"), compress=True)

# ------------------------------------------------------------------ dimension check vs plan labels
report = {"plan": PLAN["id"], "subtitle": PLAN.get("subtitle"), "outer_centreline_m": [round(pw, 3), round(ph_, 3)],
          "walls": {w["id"]: round((Vector(w["b"]) - Vector(w["a"])).length, 3) for w in PLAN["walls"]},
          "rooms": {}, "render_seconds": times, "style": STYLE, "clash_check": CLASH, "assets": sorted(FL.USED_ASSETS)}
for r in PLAN["rooms"]:
    xs_ = [p[0] for p in r["points"]]; ys_ = [p[1] for p in r["points"]]
    report["rooms"][r["name"]] = {"bbox_m": [round(max(xs_) - min(xs_), 3), round(max(ys_) - min(ys_), 3)]}
bpy.context.view_layer.update()
built = [o for o in COL["Walls"].objects if o.name.startswith("Wall_")]
bpts = [o.matrix_world @ Vector(c) for o in built for c in o.bound_box]
report["built_outer_m"] = [round(max(p.x for p in bpts) - min(p.x for p in bpts), 3), round(max(p.y for p in bpts) - min(p.y for p in bpts), 3)]
json.dump(report, open(os.path.join(OUT, f"{PLAN['id']}{TAG}_report.json"), "w"), indent=2)
print("DONE", json.dumps(times))
