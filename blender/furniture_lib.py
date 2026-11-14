"""Furniture for the Blender render worker.

Each builder returns a list of objects in the item's local frame: origin = footprint centre on the floor,
+X = width, front of the piece faces -Y (Blender) == +z in the web app, Z up. Units: metres.
Pieces come from two sources:
  * Poly Haven CC0 models (glTF, imported once and instanced), scaled to the plan footprint;
  * procedural models (bevelled / subdivided primitives with PBR materials) for items Poly Haven
    has no modern equivalent of (beds, kitchens, sanitary ware, wardrobes ...).
"""
import math, os
import bpy
from mathutils import Vector
from common import box, cylinder, link, mesh_obj, bevel, shade_smooth, set_mat, pbr_material, uv_box, ASSETS

USED_ASSETS = set()


def hex2rgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


class Mats:
    """Material palette for a style preset (colours follow src/data/styles.ts)."""

    def __init__(self, style):
        S = STYLE_PALETTES[style]
        self.S = S
        f = lambda n, **k: pbr_material(n, **k)
        self.wall = f("WallPaint", color=hex2rgb(S["wall"]), rough=0.88, bump=0.04)
        self.wall_cut = f("WallCut", color=hex2rgb(S["wallTop"]), rough=0.7)
        self.fabric = self.fabric_mat("Fabric", hex2rgb(S["fabric"]))
        self.fabric2 = self.fabric_mat("Fabric2", hex2rgb(S["fabric2"]))
        self.accent = self.fabric_mat("Accent", hex2rgb(S["accent"]))
        self.linen = self.fabric_mat("Linen", (0.86, 0.84, 0.80))
        self.duvet = self.fabric_mat("Duvet", hex2rgb(S["duvet"]))
        self.wood = f("Oak", tex="oak_veneer_01", hsv=S["oak_hsv"], rough=0.55, scale=1.0)
        self.wood_dark = f("Walnut", tex="dark_wood", hsv=(0.5, 0.6, 0.55), rough=0.5)
        self.cabinet = f("CabinetPaint", color=hex2rgb(S["cabinet"]), rough=0.45, coat=0.2)
        self.white = f("WhiteLacquer", color=(0.86, 0.86, 0.85), rough=0.35, coat=0.3)
        self.metal_black = f("BlackMetal", color=(0.02, 0.02, 0.022), rough=0.4, metal=0.9)
        self.brass = f("Brass", color=(0.75, 0.55, 0.28), rough=0.3, metal=1.0)
        self.steel = f("BrushedSteel", color=(0.62, 0.62, 0.63), rough=0.28, metal=1.0)
        self.chrome = f("Chrome", color=(0.9, 0.9, 0.9), rough=0.06, metal=1.0)
        self.ceramic = f("Ceramic", color=(0.92, 0.92, 0.91), rough=0.08, coat=0.5)
        self.counter = f("Quartz", tex="marble_01", hsv=(0.5, 0.25, 1.15), rough=0.25, scale=0.5) if False else f("Quartz", color=hex2rgb(S["counter"]), rough=0.22, coat=0.4, bump=0.02)
        self.screen = f("Screen", color=(0.005, 0.005, 0.007), rough=0.08)
        self.rug = self.rug_mat("Rug", hex2rgb(S["rug"]), hex2rgb(S["rug2"]))
        self.glass = self.glass_mat()
        self.mirror = f("Mirror", color=(0.95, 0.95, 0.95), rough=0.02, metal=1.0)
        self.dark = f("DarkPlastic", color=(0.03, 0.03, 0.035), rough=0.5)
        self.shade = self.lamp_shade()
        CUR_M[0] = self

    def fabric_mat(self, name, col):
        m = pbr_material(name, color=col, rough=0.85)
        nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
        if "Sheen Weight" in b.inputs:
            b.inputs["Sheen Weight"].default_value = 0.6; b.inputs["Sheen Roughness"].default_value = 0.5
        tc = N.new("ShaderNodeTexCoord"); wv = N.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 400
        wv.inputs["Distortion"].default_value = 2; wv.inputs["Detail"].default_value = 2
        no = N.new("ShaderNodeTexNoise"); no.inputs["Scale"].default_value = 30
        L.new(tc.outputs["Object"], wv.inputs["Vector"]); L.new(tc.outputs["Object"], no.inputs["Vector"])
        mx = N.new("ShaderNodeMath"); mx.operation = "ADD"; L.new(wv.outputs["Fac"], mx.inputs[0]); L.new(no.outputs["Fac"], mx.inputs[1])
        bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.15; bp.inputs["Distance"].default_value = 0.001
        L.new(mx.outputs[0], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
        # subtle colour variation
        cr = N.new("ShaderNodeMix"); cr.data_type = "RGBA"; cr.inputs[6].default_value = (*col, 1)
        cr.inputs[7].default_value = (col[0] * 0.8, col[1] * 0.8, col[2] * 0.8, 1)
        L.new(no.outputs["Fac"], cr.inputs[0]); L.new(cr.outputs[2], b.inputs["Base Color"])
        return m

    def rug_mat(self, name, c1, c2):
        m = pbr_material(name, color=c1, rough=1.0)
        nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
        tc = N.new("ShaderNodeTexCoord"); no = N.new("ShaderNodeTexNoise"); no.inputs["Scale"].default_value = 900; no.inputs["Detail"].default_value = 4
        L.new(tc.outputs["Object"], no.inputs["Vector"])
        bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.4; bp.inputs["Distance"].default_value = 0.002
        L.new(no.outputs["Fac"], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
        # border stripe pattern from local coords (generated)
        sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Generated"], sep.inputs[0])
        def edge(o):
            a = N.new("ShaderNodeMath"); a.operation = "SUBTRACT"; a.inputs[0].default_value = 0.5; L.new(o, a.inputs[1])
            ab = N.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"; L.new(a.outputs[0], ab.inputs[0]); return ab.outputs[0]
        mxm = N.new("ShaderNodeMath"); mxm.operation = "MAXIMUM"; L.new(edge(sep.outputs[0]), mxm.inputs[0]); L.new(edge(sep.outputs[1]), mxm.inputs[1])
        g1 = N.new("ShaderNodeMath"); g1.operation = "GREATER_THAN"; g1.inputs[1].default_value = 0.43; L.new(mxm.outputs[0], g1.inputs[0])
        g2 = N.new("ShaderNodeMath"); g2.operation = "LESS_THAN"; g2.inputs[1].default_value = 0.465; L.new(mxm.outputs[0], g2.inputs[0])
        mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; L.new(g1.outputs[0], mul.inputs[0]); L.new(g2.outputs[0], mul.inputs[1])
        cr = N.new("ShaderNodeMix"); cr.data_type = "RGBA"; cr.inputs[6].default_value = (*c1, 1); cr.inputs[7].default_value = (*c2, 1)
        L.new(mul.outputs[0], cr.inputs[0]); L.new(cr.outputs[2], b.inputs["Base Color"])
        return m

    def glass_mat(self):
        m = bpy.data.materials.new("Glass"); m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.9, 0.97, 1.0, 1); b.inputs["Roughness"].default_value = 0.0
        b.inputs["Transmission Weight"].default_value = 1.0; b.inputs["IOR"].default_value = 1.45
        # thin glass: treat as transparent for shadows
        nt = m.node_tree; N = nt.nodes; L = nt.links
        lp = N.new("ShaderNodeLightPath"); tr = N.new("ShaderNodeBsdfTransparent"); mix = N.new("ShaderNodeMixShader")
        out = N["Material Output"]
        mxx = N.new("ShaderNodeMath"); mxx.operation = "MAXIMUM"
        L.new(lp.outputs["Is Shadow Ray"], mxx.inputs[0]); L.new(lp.outputs["Is Diffuse Ray"], mxx.inputs[1])
        L.new(mxx.outputs[0], mix.inputs["Fac"]); L.new(b.outputs["BSDF"], mix.inputs[1]); L.new(tr.outputs["BSDF"], mix.inputs[2])
        L.new(mix.outputs["Shader"], out.inputs["Surface"])
        return m

    def lamp_shade(self):
        m = pbr_material("LampShade", color=(0.95, 0.9, 0.8), rough=0.8)
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Color"].default_value = (1.0, 0.8, 0.55, 1); b.inputs["Emission Strength"].default_value = 2.0
        if "Subsurface Weight" in b.inputs: pass
        return m


STYLE_PALETTES = {
    "modern": dict(wall="#ecebe8", wallTop="#2b2d33", fabric="#6b6f78", fabric2="#3d4047", accent="#c8693f", duvet="#e9e6e1",
                   rug="#cfc6b8", rug2="#8a8174", cabinet="#3a3d42", counter="#e8e6e1", oak_hsv=(0.5, 0.9, 0.85),
                   floor_hsv=(0.5, 0.95, 0.9)),
    "japandi": dict(wall="#ede6db", wallTop="#3b342d", fabric="#b9a88f", fabric2="#6e6255", accent="#7d8a6a", duvet="#efe8dc",
                    rug="#d9ccb8", rug2="#9a8a72", cabinet="#d8cfc1", counter="#e6dfd3", oak_hsv=(0.5, 0.8, 1.0),
                    floor_hsv=(0.5, 0.85, 1.0)),
    "scandinavian": dict(wall="#f7f6f2", wallTop="#3a3f47", fabric="#c9ccd1", fabric2="#8e9aa6", accent="#7fa3b8", duvet="#ffffff",
                         rug="#efebe4", rug2="#9aa6b2", cabinet="#f2f1ee", counter="#efeeea", oak_hsv=(0.5, 0.7, 1.1),
                         floor_hsv=(0.5, 0.7, 1.1)),
    "industrial": dict(wall="#d9d4cf", wallTop="#1f2023", fabric="#7b4a2e", fabric2="#2c2d30", accent="#b5543a", duvet="#cfcac4",
                       rug="#6f655d", rug2="#3a3530", cabinet="#26272a", counter="#9a9894", oak_hsv=(0.5, 1.0, 0.6),
                       floor_hsv=(0.5, 1.0, 0.6)),
}

# ------------------------------------------------------------------ primitives

def rb(name, size, loc, mat, bev=0.006, segs=3, rot=(0, 0, 0), uv_long=0, uv=True):
    """Bevelled box. loc = centre."""
    o = box(name, size, loc, rot)
    if uv: uv_box(o, scale=1.0, long_axis=uv_long)
    set_mat(o, mat)
    if bev: bevel(o, min(bev, min(size) / 2.05), segs, limit="NONE")
    return o


def soft(name, size, loc, mat, rad=0.04, rot=(0, 0, 0)):
    """Cushion-like soft box: bevel + subdivision, smooth shaded."""
    o = box(name, size, loc, rot)
    set_mat(o, mat)
    bevel(o, min(rad, min(size) / 2.1), 4, limit="NONE")
    s = o.modifiers.new("Sub", "SUBSURF"); s.levels = 1; s.render_levels = 2
    shade_smooth(o, 180)
    return o


def cyl(name, r, h, loc, mat, segs=32, r2=None, axis="Z", bev=0.0):
    o = cylinder(name, r, h, loc, segs=segs, axis=axis, r2=r2)
    set_mat(o, mat); shade_smooth(o, 45)
    if bev: bevel(o, bev, 2)
    return o


def legs(w, d, h, mat, inset=0.05, r=0.018, taper=0.75):
    return [cyl("Leg", r, h, (sx * (w / 2 - inset), sy * (d / 2 - inset), h / 2), mat, segs=16, r2=r * taper)
            for sx in (-1, 1) for sy in (-1, 1)]

# ------------------------------------------------------------------ Poly Haven models

_cache = {}


def ph_model(aid):
    """Import a Poly Haven glTF once; returns (objects, bbox_min, bbox_max) of a hidden template."""
    if aid in _cache: return _cache[aid]
    path = os.path.join(ASSETS, "models", aid, f"{aid}.gltf")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in objs if o.type == "MESH"]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    tpl = bpy.data.collections.new(f"tpl_{aid}")
    for o in meshes:
        mw = o.matrix_world.copy()
        for c in o.users_collection: c.objects.unlink(o)
        tpl.objects.link(o); o.parent = None; o.matrix_world = mw
    for o in objs:
        if o.type != "MESH": bpy.data.objects.remove(o)
    _cache[aid] = (meshes, mn, mx)
    USED_ASSETS.add(aid)
    return _cache[aid]


def ph(aid, w=None, d=None, h=None, mode="fit", lift=0.0, rotz=0.0):
    """Instance of a Poly Haven model scaled to the footprint (w x d) and/or height h, centred on the origin."""
    meshes, mn, mx = ph_model(aid)
    size = mx - mn
    if rotz:  # model's own front differs: swap extents for 90deg
        size = Vector((size.y, size.x, size.z)) if abs(math.sin(rotz)) > 0.5 else size
    sx = (w / size.x) if w else None; sy = (d / size.y) if d else None; sz = (h / size.z) if h else None
    if mode == "fit":
        k = min(s for s in (sx, sy, sz) if s)
        scl = Vector((k, k, k))
    else:  # stretch to the given dims, keep proportions on unspecified axes
        k = [s for s in (sx, sy, sz) if s]; avg = sum(k) / len(k)
        scl = Vector((sx or avg, sy or avg, sz or avg))
    centre = (mn + mx) / 2
    out = []
    for m in meshes:
        o = m.copy()  # linked mesh data
        o.matrix_world = m.matrix_world.copy()
        root = bpy.data.objects.new(f"{aid}_pivot", None)
        o.parent = root; o.matrix_parent_inverse.identity()
        o.matrix_basis = m.matrix_world.copy()
        o.location = o.location - Vector((centre.x, centre.y, mn.z))
        root.rotation_euler = (0, 0, rotz); root.scale = scl; root.location = (0, 0, lift)
        out += [root, o]
    return out

# ------------------------------------------------------------------ procedural builders


def sofa(M, w, d=0.92):
    o = []
    seatH = 0.44; armW = 0.16; backD = 0.2
    o.append(rb("SofaBase", (w, d - 0.04, 0.2), (0, 0.0, 0.17), M.fabric2 if False else M.fabric, bev=0.03))
    n = max(1, round((w - 2 * armW) / 0.7)); cw = (w - 2 * armW) / n
    for i in range(n):
        x = -w / 2 + armW + cw * (i + 0.5)
        o.append(soft(f"Seat{i}", (cw - 0.01, d - backD - 0.04, 0.16), (x, -backD / 2 + 0.0, seatH - 0.06), M.fabric, 0.05))
        o.append(soft(f"Back{i}", (cw - 0.02, 0.2, 0.42), (x, d / 2 - backD / 2 - 0.05, seatH + 0.17), M.fabric, 0.07, rot=(math.radians(-10), 0, 0)))
    o.append(rb("BackFrame", (w, backD - 0.06, 0.5), (0, d / 2 - (backD - 0.06) / 2, 0.47), M.fabric, bev=0.035))
    for sx in (-1, 1):
        o.append(soft(f"Arm{sx}", (armW, d, 0.36), (sx * (w / 2 - armW / 2), 0, 0.42), M.fabric, 0.05))
    o += legs(w, d - 0.04, 0.07, M.wood_dark, inset=0.08, r=0.02)
    # throw pillows
    o.append(soft("Pillow1", (0.44, 0.13, 0.42), (-w / 2 + armW + 0.3, d / 2 - backD - 0.08, seatH + 0.2), M.accent, 0.06, rot=(math.radians(-15), 0, math.radians(8))))
    o.append(soft("Pillow2", (0.42, 0.13, 0.40), (w / 2 - armW - 0.3, d / 2 - backD - 0.08, seatH + 0.2), M.linen, 0.06, rot=(math.radians(-15), 0, math.radians(-10))))
    return o


def bed(M, w, d):
    o = []
    o.append(rb("BedFrame", (w, d, 0.24), (0, 0, 0.12 + 0.06), M.wood, bev=0.012, uv_long=1))
    o.append(soft("Headboard", (w + 0.06, 0.1, 0.9), (0, d / 2 - 0.05, 0.6), M.fabric2, 0.03))
    o.append(soft("Mattress", (w - 0.06, d - 0.12, 0.22), (0, -0.03, 0.4), M.linen, 0.04))
    o.append(soft("Duvet", (w + 0.02, d * 0.66, 0.08), (0, -d / 2 + d * 0.33 - 0.02, 0.53), M.duvet, 0.035))
    o.append(soft("Throw", (w + 0.04, 0.42, 0.09), (0, -d / 2 + 0.33, 0.55), M.accent, 0.035))
    np_ = 2 if w > 1.2 else 1
    for i in range(np_):
        x = 0 if np_ == 1 else (-1 + 2 * i) * w * 0.23
        o.append(soft(f"Pillow{i}", (w * (0.42 if np_ == 2 else 0.7), 0.36, 0.14), (x, d / 2 - 0.32, 0.6), M.linen, 0.06, rot=(math.radians(-18), 0, 0)))
    o += legs(w, d, 0.06, M.wood_dark, inset=0.08, r=0.025, taper=1)
    if w > 1.2:  # rug under double beds only (single beds sit too close to walls)
        o += rug(M, w + 0.9, 1.5)[0:1]
        o[-1].location = (0, -0.25, 0.006)
    return o


def table(M, w, d, h=0.75, top=None):
    o = [rb("Top", (w, d, 0.035), (0, 0, h - 0.0175), top or M.wood, bev=0.006)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(rb("TLeg", (0.045, 0.045, h - 0.035), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), (h - 0.035) / 2), M.wood, bev=0.006, uv_long=2))
    return o


CUR_M = [None]


def chair_proc(M):
    """Modern dining chair: oak frame, upholstered seat, curved back rail. Front faces -Y."""
    o = [soft("ChSeat", (0.44, 0.42, 0.06), (0, 0, 0.45), M.fabric2, 0.025)]
    for sx in (-1, 1):
        o.append(cyl("ChLegF", 0.016, 0.42, (sx * 0.19, -0.17, 0.21), M.wood, segs=16, r2=0.012))
        o.append(cyl("ChLegB", 0.016, 0.82, (sx * 0.19, 0.18, 0.41), M.wood, segs=16, r2=0.013))
    o.append(rb("ChBack", (0.44, 0.03, 0.13), (0, 0.19, 0.76), M.wood, bev=0.012, uv_long=0))
    o.append(rb("ChRail", (0.38, 0.02, 0.03), (0, -0.17, 0.33), M.wood, bev=0.006))
    return o


def chair_ph(x, y, rotz):
    parts = chair_proc(CUR_M[0])
    root = bpy.data.objects.new("Chair", None)
    for p in parts: p.parent = root
    root.location = (x, y, 0); root.rotation_euler = (0, 0, rotz)
    return [root] + parts


def wall_art(M, w=0.9, h=0.65, z=1.5, y=0.0):
    """Framed abstract print (procedural canvas in the style palette)."""
    fr = rb("ArtFrame", (w, 0.03, h), (0, y, z), M.metal_black, bev=0.004)
    cv = box("ArtCanvas", (w - 0.06, 0.032, h - 0.06), (0, y, z))
    m = pbr_material("ArtPrint", color=(0.8, 0.78, 0.74), rough=0.8)
    nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord"); wv = N.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 1.6
    wv.inputs["Distortion"].default_value = 6; wv.inputs["Detail"].default_value = 1
    L.new(tc.outputs["Generated"], wv.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB"); el = cr.color_ramp.elements
    el[0].color = (*hex2rgb("#efe9df"), 1); el[1].color = (*hex2rgb(M.S["accent"]), 1); el[1].position = 0.75
    e2 = el.new(0.45); e2.color = (*hex2rgb(M.S["fabric"]), 1)
    L.new(wv.outputs["Fac"], cr.inputs["Fac"]); L.new(cr.outputs["Color"], b.inputs["Base Color"])
    set_mat(cv, m)
    for o in (fr, cv): o["upper"] = True
    return [fr, cv]


def dining(M, w, d, seats):
    tw, td = (1.8 if seats >= 6 else 1.2), 0.9
    o = table(M, tw, td)
    per = math.ceil(seats / 2)
    for side in (-1, 1):
        for i in range(per):
            x = -tw / 2 + tw / per * (i + 0.5)
            o += chair_ph(x, side * (td / 2 + 0.12), 0 if side < 0 else math.pi)
    o += ph("ceramic_vase_01", h=0.3, lift=0.75)
    return o


def kitchen(M, w, d=0.62, uppers=True):
    o = []
    n = max(2, round(w / 0.6)); cw = w / n
    o.append(rb("Plinth", (w - 0.02, d - 0.08, 0.1), (0, 0.03, 0.05), M.dark, bev=0.002))
    for i in range(n):
        x = -w / 2 + cw * (i + 0.5)
        o.append(rb(f"Door{i}", (cw - 0.006, 0.02, 0.76), (x, -d / 2 + 0.03, 0.1 + 0.38), M.cabinet, bev=0.003))
        o.append(rb(f"Pull{i}", (0.16 if cw > 0.4 else 0.1, 0.02, 0.012), (x, -d / 2 + 0.01, 0.82), M.metal_black, bev=0.003))
    o.append(rb("Carcass", (w, d - 0.04, 0.76), (0, 0.02, 0.48), M.cabinet, bev=0.002))
    o.append(rb("Counter", (w, d, 0.035), (0, 0, 0.88), M.counter, bev=0.004))
    # sink + tap, hob
    sx = -w / 2 + w * 0.32 if w > 2 else -w / 2 + 0.45
    o.append(rb("Sink", (0.55, 0.4, 0.02), (sx, -0.02, 0.8985), M.steel, bev=0.01))
    o.append(rb("SinkHole", (0.5, 0.35, 0.02), (sx, -0.02, 0.9), M.dark, bev=0.02))
    o.append(cyl("Tap", 0.015, 0.3, (sx, 0.22, 1.05), M.chrome, segs=16))
    o.append(cyl("Spout", 0.012, 0.18, (sx, 0.14, 1.19), M.chrome, segs=16, axis="Y"))
    hx = w / 2 - 0.5 if w > 2 else w / 2 - 0.4
    o.append(rb("Hob", (0.6, 0.5, 0.008), (hx, -0.02, 0.9015), M.screen, bev=0.003))
    for (ax, ay, r) in ((-0.15, -0.1, 0.09), (0.15, -0.1, 0.07), (-0.15, 0.12, 0.07), (0.15, 0.12, 0.09)):
        ring = cyl("Burner", r, 0.001, (hx + ax, -0.02 + ay, 0.906), M.dark, segs=32)
        o.append(ring)
    if uppers:
        for i in range(n):
            x = -w / 2 + cw * (i + 0.5)
            u = rb(f"Upper{i}", (cw - 0.006, 0.34, 0.72), (x, d / 2 - 0.17, 1.86), M.cabinet, bev=0.003)
            u["upper"] = True; o.append(u)
        hood = rb("Hood", (0.6, 0.36, 0.08), (hx, d / 2 - 0.2, 1.46), M.steel, bev=0.004); hood["upper"] = True; o.append(hood)
    return o


def island(M, w, d):
    o = [rb("IslandBody", (w - 0.04, d - 0.2, 0.86), (0, 0.06, 0.43), M.cabinet, bev=0.003),
         rb("IslandTop", (w, d, 0.04), (0, 0, 0.9), M.counter, bev=0.005)]
    for i in range(3):
        x = -w / 2 + w / 3 * (i + 0.5)
        o.append(cyl("StoolSeat", 0.18, 0.05, (x, -d / 2 - 0.2, 0.66), M.wood, segs=32, bev=0.01))
        o.append(cyl("StoolPost", 0.02, 0.62, (x, -d / 2 - 0.2, 0.32), M.metal_black, segs=12))
        o.append(cyl("StoolBase", 0.17, 0.015, (x, -d / 2 - 0.2, 0.008), M.metal_black, segs=32))
        o.append(cyl("StoolRing", 0.14, 0.012, (x, -d / 2 - 0.2, 0.28), M.metal_black, segs=32))
    o.append(cyl("Bowl", 0.14, 0.07, (0.2, 0.05, 0.955), M.ceramic, segs=32, r2=0.17))
    return o


def fridge(M, w, d):
    h = 1.9
    return [rb("FridgeBody", (w, d, h), (0, 0.0, h / 2), M.steel, bev=0.01),
            rb("FridgeSplit", (w - 0.01, 0.005, 0.006), (0, -d / 2, 1.2), M.dark, bev=0),
            rb("Handle1", (0.025, 0.03, 0.5), (w / 2 - 0.06, -d / 2 - 0.02, 1.5), M.chrome, bev=0.008),
            rb("Handle2", (0.025, 0.03, 0.5), (w / 2 - 0.06, -d / 2 - 0.02, 0.85), M.chrome, bev=0.008)]


def tub(M, w, d):
    outer = rb("TubOuter", (w, d, 0.56), (0, 0, 0.28), M.ceramic, bev=0.03)
    inner = box("TubCut", (w - 0.14, d - 0.14, 0.5), (0, 0, 0.56))
    bv = inner.modifiers.new("Bevel", "BEVEL"); bv.width = 0.12; bv.segments = 6; bv.limit_method = "NONE"
    inner.hide_render = True; inner.display_type = "WIRE"
    b = outer.modifiers.new("Bool", "BOOLEAN"); b.operation = "DIFFERENCE"; b.object = inner; b.solver = "EXACT"
    outer.modifiers.move(1, 0) if len(outer.modifiers) > 1 else None
    shade_smooth(outer, 40)
    return [outer, inner, cyl("TubTap", 0.02, 0.15, (-w / 2 + 0.05, 0, 0.62), M.chrome, segs=16)]


def shower(M, w, d):
    o = [rb("Tray", (w, d, 0.05), (0, 0, 0.025), M.ceramic, bev=0.01),
         rb("Drain", (0.1, 0.1, 0.002), (0, 0, 0.051), M.steel, bev=0.002),
         rb("GlassF", (w - 0.02, 0.008, 1.95), (0, -d / 2 + 0.01, 1.03), M.glass, bev=0),
         rb("GlassS", (0.008, d - 0.02, 1.95), (-w / 2 + 0.01, 0, 1.03), M.glass, bev=0),
         rb("Frame", (0.02, 0.02, 1.95), (-w / 2 + 0.01, -d / 2 + 0.01, 1.03), M.chrome, bev=0.003),
         cyl("Head", 0.11, 0.01, (0.0, d / 2 - 0.2, 2.05), M.chrome, segs=32),
         cyl("Arm", 0.012, 0.22, (0.0, d / 2 - 0.1, 2.08), M.chrome, segs=12, axis="Y")]
    return o


def toilet(M, w, d):
    o = []
    bowl = cyl("Bowl", 0.19, 0.38, (0, -0.07, 0.19), M.ceramic, segs=48, r2=0.2)
    bowl.scale = (1.0, 1.25, 1); o.append(bowl)
    seat = cyl("Seat", 0.2, 0.03, (0, -0.07, 0.395), M.ceramic, segs=48)
    seat.scale = (1.0, 1.28, 1); o.append(seat)
    o.append(rb("Tank", (0.38, 0.17, 0.36), (0, d / 2 - 0.1, 0.6), M.ceramic, bev=0.03))
    o.append(rb("Flush", (0.06, 0.03, 0.01), (0, d / 2 - 0.1, 0.785), M.chrome, bev=0.004))
    return o


def vanity(M, w, d):
    o = [rb("VanityBody", (w, d - 0.02, 0.45), (0, 0.01, 0.62), M.wood, bev=0.006),
         rb("Basin", (w, d, 0.06), (0, 0, 0.875), M.ceramic, bev=0.012),
         rb("BasinHole", (w - 0.25, d - 0.18, 0.004), (0, -0.02, 0.9055), M.ceramic, bev=0.04),
         cyl("Tap", 0.014, 0.2, (0, d / 2 - 0.06, 1.0), M.chrome, segs=16),
         cyl("Spout", 0.011, 0.12, (0, d / 2 - 0.12, 1.09), M.chrome, segs=16, axis="Y")]
    m = rb("Mirror", (w * 0.85, 0.02, 0.8), (0, d / 2 - 0.0, 1.55), M.mirror, bev=0.004); m["upper"] = True; o.append(m)
    return o


def wardrobe(M, w, d):
    h = 2.2; o = [rb("WardBody", (w, d - 0.02, h), (0, 0.01, h / 2), M.white, bev=0.004)]
    n = max(2, round(w / 0.55)); dw = w / n
    for i in range(n):
        x = -w / 2 + dw * (i + 0.5)
        o.append(rb(f"WDoor{i}", (dw - 0.006, 0.02, h - 0.04), (x, -d / 2 + 0.005, h / 2), M.white if i % 2 else M.wood, bev=0.003))
        o.append(rb(f"WPull{i}", (0.012, 0.02, 0.3), (x + (dw / 2 - 0.05) * (1 if i % 2 == 0 else -1), -d / 2 - 0.012, 1.05), M.metal_black, bev=0.004))
    return o


def dresser(M, w, d):
    o = [rb("DrBody", (w, d, 0.72), (0, 0, 0.12 + 0.36), M.wood, bev=0.006)]
    for r in range(3):
        for c_ in range(2):
            x = -w / 4 + c_ * w / 2; z = 0.12 + 0.12 + r * 0.24
            o.append(rb("Drawer", (w / 2 - 0.012, 0.012, 0.23), (x, -d / 2 - 0.004, z), M.wood, bev=0.003))
            o.append(rb("Knob", (0.1, 0.015, 0.012), (x, -d / 2 - 0.014, z + 0.06), M.brass, bev=0.004))
    o += legs(w, d, 0.12, M.wood_dark, inset=0.05, r=0.018)
    o += ph("ceramic_vase_01", h=0.32, lift=0.84)
    return o


def desk(M, w, d):
    o = [rb("DeskTop", (w, d, 0.03), (0, 0, 0.735), M.wood, bev=0.005)]
    for sx in (-1, 1):
        o.append(rb("DeskLegA", (0.03, d - 0.08, 0.03), (sx * (w / 2 - 0.06), 0, 0.015), M.metal_black, bev=0.003))
        o.append(rb("DeskLegB", (0.03, 0.03, 0.72), (sx * (w / 2 - 0.06), 0, 0.36), M.metal_black, bev=0.003))
    lap = rb("Laptop", (0.34, 0.24, 0.015), (0.1, -0.05, 0.758), M.steel, bev=0.004); o.append(lap)
    o.append(rb("LaptopScreen", (0.34, 0.012, 0.23), (0.1, 0.08, 0.87), M.screen, bev=0.004, rot=(math.radians(-12), 0, 0)))
    for p in ph("desk_lamp_arm_01", h=0.5, rotz=math.radians(180)):
        if p.parent is None: p.location = (-w / 2 + 0.2, 0.15, 0.75)
        o.append(p)
    return o


def office_chair(M, w, d):
    o = [soft("OCSeat", (0.48, 0.46, 0.08), (0, 0, 0.48), M.fabric2, 0.03),
         soft("OCBack", (0.46, 0.06, 0.5), (0, 0.24, 0.82), M.fabric2, 0.03, rot=(math.radians(-8), 0, 0)),
         cyl("OCPost", 0.025, 0.36, (0, 0, 0.26), M.chrome, segs=16)]
    for k in range(5):
        a = 2 * math.pi * k / 5
        o.append(rb("OCStar", (0.3, 0.035, 0.03), (0.15 * math.cos(a), 0.15 * math.sin(a), 0.06), M.metal_black, rot=(0, 0, a), bev=0.008))
        o.append(cyl("OCWheel", 0.025, 0.03, (0.29 * math.cos(a), 0.29 * math.sin(a), 0.025), M.dark, segs=12, axis="X"))
    return o


def floor_lamp(M, w, d):
    return [cyl("FLBase", 0.15, 0.025, (0, 0, 0.0125), M.metal_black, segs=32, bev=0.005),
            cyl("FLPole", 0.012, 1.45, (0, 0, 0.75), M.metal_black, segs=12),
            cyl("FLShade", 0.2, 0.3, (0, 0, 1.55), M.shade, segs=48, r2=0.17)]


def stairs(M, w, d, h=2.9):
    o = []; n = 15; run = d / n; rise = h / n
    for i in range(n):
        y = -d / 2 + run * (i + 0.5)
        o.append(rb(f"Tread{i}", (w - 0.06, run + 0.025, 0.04), (0, y, rise * (i + 1) - 0.02), M.wood, bev=0.004))
        o.append(rb(f"Riser{i}", (w - 0.08, 0.015, rise - 0.04), (0, y - run / 2 + 0.01, rise * i + (rise - 0.04) / 2 + 0.0), M.white, bev=0))
    import math as _m
    ang = _m.atan2(h, d); L = _m.hypot(h, d)
    for sx in (-1, 1):
        o.append(rb("Stringer", (0.03, L, 0.25), (sx * (w / 2 - 0.015), 0, h / 2 - 0.06), M.white, rot=(ang, 0, 0), bev=0.004))
    # glass balustrade on the open side + handrail
    o.append(rb("Balustrade", (0.012, L, 0.9), (w / 2 + 0.01, 0, h / 2 + 0.45), M.glass, rot=(ang, 0, 0), bev=0))
    o.append(rb("Handrail", (0.04, L, 0.04), (w / 2 + 0.01, 0, h / 2 + 0.92), M.wood, rot=(ang, 0, 0), bev=0.01))
    return o


def washer(M, w, d):
    return [rb("WBody", (w, d, 0.85), (0, 0, 0.425), M.white, bev=0.015),
            cyl("WDoor", 0.17, 0.03, (0, -d / 2 - 0.01, 0.45), M.chrome, segs=48, axis="Y"),
            cyl("WGlass", 0.13, 0.035, (0, -d / 2 - 0.012, 0.45), M.screen, segs=48, axis="Y"),
            rb("WPanel", (w - 0.04, 0.01, 0.1), (0, -d / 2, 0.77), M.dark, bev=0.003)]


def tv_unit(M, w, d):
    o = ph("modern_wooden_cabinet", w=w, d=d, h=0.5, mode="stretch")
    o.append(rb("TVScreen", (1.45, 0.03, 0.84), (0, d / 2 - 0.08, 1.2), M.screen, bev=0.004))
    o.append(rb("TVFrame", (1.47, 0.025, 0.86), (0, d / 2 - 0.06, 1.2), M.dark, bev=0.003))
    return o


def rug(M, w, d, round_=False):
    if round_:
        o = cyl("Rug", w / 2, 0.012, (0, 0, 0.006), M.rug, segs=96)
    else:
        o = rb("Rug", (w, d, 0.012), (0, 0, 0.006), M.rug, bev=0.004, uv=False)
    return [o]


def nightstand(M, w, d):
    o = ph("side_table_01", w=w, d=d, mode="fit")
    _, mn, mx = ph_model("side_table_01")
    k = min(w / (mx.x - mn.x), d / (mx.y - mn.y)); top = (mx.z - mn.z) * k
    o += [cyl("LampBase", 0.07, 0.22, (0.05, 0.0, top + 0.11), M.ceramic, segs=32, r2=0.05),
          cyl("LampShade", 0.12, 0.17, (0.05, 0.0, top + 0.3), M.shade, segs=48, r2=0.1)]
    return o


def plant(M, w, d, variant=0):
    aid = ("potted_plant_02", "potted_plant_01")[variant % 2]
    return ph(aid, w=w * 1.4, d=d * 1.4, h=1.1 if variant % 2 else 0.95, mode="fit")


def bistro(M, w, d):
    o = ph("round_wooden_table_02", w=0.75, d=0.75, mode="fit")
    o += chair_ph(-0.55, 0, -math.pi / 2) + chair_ph(0.55, 0, math.pi / 2)
    return o


BUILDERS = {
    "sofa3": lambda M, f, it: sofa(M, f["w"], f["d"]),
    "sofa2": lambda M, f, it: sofa(M, f["w"], f["d"]),
    "armchair": lambda M, f, it: ph("modern_arm_chair_01", w=f["w"], d=f["d"], mode="fit"),
    "coffee": lambda M, f, it: ph("modern_coffee_table_01", w=f["w"], d=f["d"], mode="stretch") + ph("ceramic_vase_01", h=0.25, lift=0.39),
    "tv": lambda M, f, it: tv_unit(M, f["w"], f["d"]),
    "rug": lambda M, f, it: rug(M, f["w"], f["d"]),
    "rugRound": lambda M, f, it: rug(M, f["w"], f["d"], True),
    "bookshelf": lambda M, f, it: ph("wooden_display_shelves_01", w=f["w"], d=f["d"], mode="fit"),
    "bedDouble": lambda M, f, it: bed(M, f["w"], f["d"]),
    "bedSingle": lambda M, f, it: bed(M, f["w"], f["d"]),
    "nightstand": lambda M, f, it: nightstand(M, f["w"], f["d"]),
    "wardrobe": lambda M, f, it: wardrobe(M, f["w"], f["d"]),
    "dresser": lambda M, f, it: dresser(M, f["w"], f["d"]),
    "dining4": lambda M, f, it: dining(M, f["w"], f["d"], 4),
    "dining6": lambda M, f, it: dining(M, f["w"], f["d"], 6),
    "bistro": lambda M, f, it: bistro(M, f["w"], f["d"]),
    "kitchen": lambda M, f, it: kitchen(M, f["w"], f["d"]),
    "kitchenShort": lambda M, f, it: kitchen(M, f["w"], f["d"]),
    "island": lambda M, f, it: island(M, f["w"], f["d"]),
    "fridge": lambda M, f, it: fridge(M, f["w"], f["d"]),
    "bathtub": lambda M, f, it: tub(M, f["w"], f["d"]),
    "shower": lambda M, f, it: shower(M, f["w"], f["d"]),
    "toilet": lambda M, f, it: toilet(M, f["w"], f["d"]),
    "vanity": lambda M, f, it: vanity(M, f["w"], f["d"]),
    "desk": lambda M, f, it: desk(M, f["w"], f["d"]),
    "officeChair": lambda M, f, it: office_chair(M, f["w"], f["d"]),
    "plant": lambda M, f, it: plant(M, f["w"], f["d"], int(it["id"].strip("it") or 0) if it["id"].strip("it").isdigit() else 0),
    "floorLamp": lambda M, f, it: floor_lamp(M, f["w"], f["d"]),
    "stairs": lambda M, f, it: stairs(M, f["w"], f["d"]),
    "washer": lambda M, f, it: washer(M, f["w"], f["d"]),
}
