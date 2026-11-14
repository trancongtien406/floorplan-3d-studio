"""Furniture for the Blender render worker.

Each builder returns a list of objects in the item's local frame: origin = footprint centre on the floor,
+X = width, front of the piece faces -Y (Blender) == +z in the web app, Z up. Units: metres.
Pieces come from two sources:
  * Poly Haven CC0 models (glTF, imported once and instanced), scaled to the plan footprint;
  * procedural models (bevelled / subdivided primitives with PBR materials) for items Poly Haven
    has no modern equivalent of (beds, sofas, kitchens, sanitary ware, wardrobes, lights, curtains ...).

Style presets change the furniture itself (silhouettes, leg types, fronts, lamps, chosen CC0 models),
not only the colours: see STYLE_SPECS.
"""
import math, os, random
import bpy
from mathutils import Vector
from common import box, cylinder, link, mesh_obj, bevel, shade_smooth, set_mat, pbr_material, uv_box, ASSETS

USED_ASSETS = set()
RND = random.Random(11)


def hex2rgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


STYLE_PALETTES = {
    "modern": dict(wall="#e9e7e3", wallTop="#2b2d33", fabric="#4a4d55", fabric2="#2f3237", accent="#b5653e", duvet="#e7e4df",
                   rug="#8d8a85", rug2="#3d3c3a", cabinet="#1f2023", counter="#efede9", oak_hsv=(0.5, 0.9, 0.85),
                   floor_hsv=(0.5, 0.62, 0.78), curtain="#8f8a83", lamp="black"),
    "scandinavian": dict(wall="#f6f5f1", wallTop="#3a3f47", fabric="#d9d6cf", fabric2="#9aa3ad", accent="#7f9fb3", duvet="#ffffff",
                         rug="#ece7dd", rug2="#b9b2a5", cabinet="#f1f0ec", counter="#f3f2ee", oak_hsv=(0.5, 0.75, 1.15),
                         floor_hsv=(0.5, 0.7, 1.12), curtain="#f2efe8", lamp="globe"),
    "japandi": dict(wall="#e7e4dd", wallTop="#3b342d", fabric="#c4b8a4", fabric2="#5e5548", accent="#6f7d5c", duvet="#e9e5dc",
                    rug="#cdbf9f", rug2="#8f7a5c", cabinet="#cfc7b8", counter="#d9d4ca", oak_hsv=(0.5, 0.7, 1.0),
                    floor_hsv=(0.5, 0.62, 0.92), curtain="#e3d8c6", lamp="paper"),
    "industrial": dict(wall="#d9d4cf", wallTop="#1f2023", fabric="#7b4a2e", fabric2="#2c2d30", accent="#b5543a", duvet="#cfcac4",
                       rug="#6f655d", rug2="#3a3530", cabinet="#26272a", counter="#9a9894", oak_hsv=(0.5, 1.0, 0.6),
                       floor_hsv=(0.5, 1.0, 0.6), curtain="#8a847c", lamp="black"),
}

# per-style choices of floors / woods / fabrics / furniture families
STYLE_SPECS = {
    "modern": dict(floor_wood=("herringbone_parquet", 0.55), wood=("dark_wood", (0.5, 0.65, 0.6)), sofa="boxy", bed="channel",
                   chair="metal", coffee="modern_coffee_table_01", armchair="modern_arm_chair_01", kitchen="handleless",
                   fabric_n="velour_velvet", rug_n="poly_wool_herringbone", leg="metal", tile=("marble_01", 0.6)),
    "scandinavian": dict(floor_wood=("laminate_floor_02", 0.5), wood=("white_oak_veneer", (0.5, 0.75, 1.1)), sofa="round", bed="slat",
                         chair="oak_round", coffee="coffee_table_round_01", armchair="round_boucle", kitchen="white_oak",
                         fabric_n="wool_boucle", rug_n="knitted_fleece", leg="taper", tile=("marble_01", 0.6)),
    "japandi": dict(floor_wood=("oak_wood_planks", 0.45), wood=("ash_veneer", (0.5, 0.65, 0.95)), sofa="low_frame", bed="platform",
                    chair="ash_low", coffee="low_ash", armchair="modern_arm_chair_01", kitchen="ash_slat",
                    fabric_n="rough_linen", rug_n="knitted_fleece", leg="block", tile=("marble_01", 0.6)),
    "industrial": dict(floor_wood=("laminate_floor_02", 0.5), wood=("dark_wood", (0.5, 0.8, 0.7)), sofa="boxy", bed="channel",
                       chair="metal", coffee="modern_coffee_table_01", armchair="modern_arm_chair_01", kitchen="handleless",
                       fabric_n="brown_leather", rug_n="poly_wool_herringbone", leg="metal", tile=("marble_01", 0.6)),
}


def tex_file(name, kind, res="2k"):
    for ext in ("jpg", "png"):
        p = os.path.join(ASSETS, "textures", name, f"{name}_{kind}_{res}.{ext}")
        if os.path.exists(p): return p
    return None


class Mats:
    """Material palette for a style preset."""

    def __init__(self, style):
        S = STYLE_PALETTES[style]; X = STYLE_SPECS[style]
        self.S, self.X, self.style = S, X, style
        f = lambda n, **k: pbr_material(n, **k)
        self.wall = f("WallPaint", color=hex2rgb(S["wall"]), rough=0.88, bump=0.04)
        self.wall_cut = f("WallCut", color=hex2rgb(S["wallTop"]), rough=0.7)
        fn = X["fabric_n"]
        self.fabric = self.fabric_mat("Fabric", hex2rgb(S["fabric"]), fn)
        self.fabric2 = self.fabric_mat("Fabric2", hex2rgb(S["fabric2"]), fn)
        self.accent = self.fabric_mat("Accent", hex2rgb(S["accent"]), "knitted_fleece")
        self.linen = self.fabric_mat("Linen", (0.80, 0.78, 0.74), "rough_linen")
        self.duvet = self.fabric_mat("Duvet", hex2rgb(S["duvet"]), "rough_linen")
        self.curtain = self.curtain_mat(hex2rgb(S["curtain"]))
        wt, whsv = X["wood"]
        self.wood = f("Wood", tex=wt, hsv=whsv, rough=0.5, scale=1.0)
        self.wood_dark = f("Walnut", tex="dark_wood", hsv=(0.5, 0.6, 0.5), rough=0.5)
        self.cabinet = f("CabinetPaint", color=hex2rgb(S["cabinet"]), rough=0.5, coat=0.15)
        self.white = f("WhiteLacquer", color=(0.82, 0.82, 0.81), rough=0.35, coat=0.3)
        self.metal_black = f("BlackMetal", color=(0.015, 0.015, 0.017), rough=0.38, metal=0.9)
        self.brass = f("Brass", color=(0.75, 0.55, 0.28), rough=0.3, metal=1.0)
        self.steel = f("BrushedSteel", color=(0.62, 0.62, 0.63), rough=0.28, metal=1.0)
        self.chrome = f("Chrome", color=(0.9, 0.9, 0.9), rough=0.06, metal=1.0)
        self.ceramic = f("Ceramic", color=(0.9, 0.9, 0.89), rough=0.08, coat=0.5)
        self.counter = self.stone_mat("Counter", hex2rgb(S["counter"]))
        self.screen = f("Screen", color=(0.004, 0.004, 0.006), rough=0.06)
        self.rug = self.rug_mat("Rug", hex2rgb(S["rug"]), hex2rgb(S["rug2"]), X["rug_n"])
        self.glass = self.glass_mat()
        self.mirror = f("Mirror", color=(0.95, 0.95, 0.95), rough=0.02, metal=1.0)
        self.dark = f("DarkPlastic", color=(0.03, 0.03, 0.035), rough=0.5)
        self.shade = self.emit_mat("LampShade", (0.95, 0.9, 0.8), (1.0, 0.78, 0.5), 3.0)
        self.paper = self.emit_mat("PaperShade", (0.93, 0.88, 0.78), (1.0, 0.75, 0.45), 6.0)
        self.bulb = self.emit_mat("Bulb", (1, 1, 1), (1.0, 0.82, 0.6), 25.0)
        self.backsplash = f("Backsplash", tex="long_white_tiles", scale=1.0, rough=0.2, coat=0.3, mapping="OBJ")
        self.book_mats = [f(f"Book{i}", color=c, rough=0.6) for i, c in enumerate(
            [hex2rgb(h) for h in ("#2f3b4a", "#b8a58a", "#7a2e2a", "#e8e2d6", "#3e5243", "#c9a24a", "#1d1d1f")])]
        CUR_M[0] = self

    def fabric_mat(self, name, col, ntex=None):
        m = pbr_material(name, color=col, rough=0.85)
        nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
        if "Sheen Weight" in b.inputs:
            b.inputs["Sheen Weight"].default_value = 0.7; b.inputs["Sheen Roughness"].default_value = 0.45
        tc = N.new("ShaderNodeTexCoord")
        no = N.new("ShaderNodeTexNoise"); no.inputs["Scale"].default_value = 18
        L.new(tc.outputs["Object"], no.inputs["Vector"])
        cr = N.new("ShaderNodeMix"); cr.data_type = "RGBA"; cr.inputs[6].default_value = (*col, 1)
        cr.inputs[7].default_value = (col[0] * 0.82, col[1] * 0.82, col[2] * 0.82, 1)
        L.new(no.outputs["Fac"], cr.inputs[0]); L.new(cr.outputs[2], b.inputs["Base Color"])
        p = tex_file(ntex, "nor_gl") if ntex else None
        if p:
            mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (2.5, 2.5, 2.5)
            L.new(tc.outputs["Object"], mp.inputs["Vector"])
            t = N.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(p, check_existing=True)
            t.image.colorspace_settings.name = "Non-Color"; t.projection = "BOX"; t.projection_blend = 0.3
            L.new(mp.outputs["Vector"], t.inputs["Vector"])
            nn = N.new("ShaderNodeNormalMap"); nn.inputs["Strength"].default_value = 1.2
            L.new(t.outputs["Color"], nn.inputs["Color"]); L.new(nn.outputs["Normal"], b.inputs["Normal"])
        return m

    def curtain_mat(self, col):
        m = self.fabric_mat("Curtain", col, "rough_linen")
        nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]; out = N["Material Output"]
        tl = N.new("ShaderNodeBsdfTranslucent"); tl.inputs["Color"].default_value = (*col, 1)
        mx = N.new("ShaderNodeMixShader"); mx.inputs["Fac"].default_value = 0.35
        L.new(b.outputs["BSDF"], mx.inputs[1]); L.new(tl.outputs["BSDF"], mx.inputs[2]); L.new(mx.outputs["Shader"], out.inputs["Surface"])
        return m

    def stone_mat(self, name, col):
        """Quartz/marble: soft procedural veins, glossy."""
        m = pbr_material(name, color=col, rough=0.18, coat=0.4)
        nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
        tc = N.new("ShaderNodeTexCoord"); wv = N.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 3
        wv.inputs["Distortion"].default_value = 14; wv.inputs["Detail"].default_value = 6; wv.inputs["Detail Scale"].default_value = 2
        L.new(tc.outputs["Object"], wv.inputs["Vector"])
        cr = N.new("ShaderNodeValToRGB"); e = cr.color_ramp.elements
        e[0].position = 0.0; e[0].color = (col[0] * 0.72, col[1] * 0.72, col[2] * 0.74, 1); e[1].position = 0.12; e[1].color = (*col, 1)
        L.new(wv.outputs["Fac"], cr.inputs["Fac"]); L.new(cr.outputs["Color"], b.inputs["Base Color"])
        return m

    def rug_mat(self, name, c1, c2, ntex=None):
        m = pbr_material(name, color=c1, rough=1.0)
        nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
        tc = N.new("ShaderNodeTexCoord")
        sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Generated"], sep.inputs[0])
        def edge(o):
            a = N.new("ShaderNodeMath"); a.operation = "SUBTRACT"; a.inputs[0].default_value = 0.5; L.new(o, a.inputs[1])
            ab = N.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"; L.new(a.outputs[0], ab.inputs[0]); return ab.outputs[0]
        mxm = N.new("ShaderNodeMath"); mxm.operation = "MAXIMUM"; L.new(edge(sep.outputs[0]), mxm.inputs[0]); L.new(edge(sep.outputs[1]), mxm.inputs[1])
        g1 = N.new("ShaderNodeMath"); g1.operation = "GREATER_THAN"; g1.inputs[1].default_value = 0.42; L.new(mxm.outputs[0], g1.inputs[0])
        g2 = N.new("ShaderNodeMath"); g2.operation = "LESS_THAN"; g2.inputs[1].default_value = 0.46; L.new(mxm.outputs[0], g2.inputs[0])
        mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; L.new(g1.outputs[0], mul.inputs[0]); L.new(g2.outputs[0], mul.inputs[1])
        cr = N.new("ShaderNodeMix"); cr.data_type = "RGBA"; cr.inputs[6].default_value = (*c1, 1); cr.inputs[7].default_value = (*c2, 1)
        L.new(mul.outputs[0], cr.inputs[0]); L.new(cr.outputs[2], b.inputs["Base Color"])
        p = tex_file(ntex, "nor_gl") if ntex else None
        if p:
            mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (3, 3, 3)
            L.new(tc.outputs["Object"], mp.inputs["Vector"])
            t = N.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(p, check_existing=True)
            t.image.colorspace_settings.name = "Non-Color"; t.projection = "BOX"
            L.new(mp.outputs["Vector"], t.inputs["Vector"])
            nn = N.new("ShaderNodeNormalMap"); nn.inputs["Strength"].default_value = 1.5
            L.new(t.outputs["Color"], nn.inputs["Color"]); L.new(nn.outputs["Normal"], b.inputs["Normal"])
        return m

    def glass_mat(self):
        m = bpy.data.materials.new("Glass"); m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.92, 0.97, 0.98, 1); b.inputs["Roughness"].default_value = 0.0
        b.inputs["Transmission Weight"].default_value = 1.0; b.inputs["IOR"].default_value = 1.5
        nt = m.node_tree; N = nt.nodes; L = nt.links
        lp = N.new("ShaderNodeLightPath"); tr = N.new("ShaderNodeBsdfTransparent"); tr.inputs[0].default_value = (0.93, 0.97, 0.97, 1)
        mix = N.new("ShaderNodeMixShader"); out = N["Material Output"]
        mxx = N.new("ShaderNodeMath"); mxx.operation = "MAXIMUM"
        L.new(lp.outputs["Is Shadow Ray"], mxx.inputs[0]); L.new(lp.outputs["Is Diffuse Ray"], mxx.inputs[1])
        L.new(mxx.outputs[0], mix.inputs["Fac"]); L.new(b.outputs["BSDF"], mix.inputs[1]); L.new(tr.outputs["BSDF"], mix.inputs[2])
        L.new(mix.outputs["Shader"], out.inputs["Surface"])
        return m

    def emit_mat(self, name, col, ecol, strength):
        m = pbr_material(name, color=col, rough=0.8)
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Color"].default_value = (*ecol, 1); b.inputs["Emission Strength"].default_value = strength
        return m


CUR_M = [None]


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



# ------------------------------------------------------------------ style-specific builders

def at(objs, x, y, z, rz=None):
    """Move the pivots of a ph() instance list."""
    for p in objs:
        if p.parent is None:
            p.location = (x, y, z)
            if rz is not None: p.rotation_euler.z = rz
    return objs


def _legs_style(M, w, d, h, inset=0.07):
    k = M.X["leg"]
    if k == "metal":
        return [rb("LegM", (0.02, 0.02, h), (sx * (w / 2 - inset), sy * (d / 2 - inset), h / 2), M.metal_black, bev=0.003, uv=False)
                for sx in (-1, 1) for sy in (-1, 1)]
    if k == "block":
        return [rb("Plinth", (w - 0.1, d - 0.1, h), (0, 0, h / 2), M.wood, bev=0.004)]
    return legs(w, d, h, M.wood, inset=inset, r=0.022, taper=0.6)


def sofa(M, w, d=0.92):
    o = []; kind = M.X["sofa"]
    if kind == "boxy":        # modern: crisp, thin arms, metal legs, low back
        seatH, armW, legH, rad = 0.43, 0.12, 0.12, 0.025
    elif kind == "round":     # scandinavian: soft rounded boucle, tapered oak legs
        seatH, armW, legH, rad = 0.45, 0.2, 0.15, 0.08
    else:                     # japandi: low, wooden platform frame
        seatH, armW, legH, rad = 0.38, 0.1, 0.06, 0.04
    backD = 0.2
    base_top = seatH - 0.14
    if kind == "low_frame":
        o.append(rb("Frame", (w, d, 0.06), (0, 0, legH + 0.03), M.wood, bev=0.006))
        o.append(rb("FrameBase", (w - 0.12, d - 0.12, legH), (0, 0, legH / 2), M.wood, bev=0.003))
        for sx in (-1, 1):
            o.append(rb(f"ArmW{sx}", (armW, d, 0.24), (sx * (w / 2 - armW / 2), 0, legH + 0.06 + 0.12), M.wood, bev=0.008))
    else:
        o.append(soft("SofaBase", (w, d - 0.04, base_top - legH), (0, 0, legH + (base_top - legH) / 2), M.fabric, rad * 0.6))
        for sx in (-1, 1):
            o.append(soft(f"Arm{sx}", (armW, d, seatH + 0.2 - legH), (sx * (w / 2 - armW / 2), 0, legH + (seatH + 0.2 - legH) / 2), M.fabric, rad))
        o += _legs_style(M, w - 0.04, d - 0.08, legH, inset=0.06)
    n = max(1, round((w - 2 * armW) / 0.7)); cw = (w - 2 * armW) / n
    z_seat = (legH + 0.06 if kind == "low_frame" else base_top) + 0.08
    for i in range(n):
        x = -w / 2 + armW + cw * (i + 0.5)
        o.append(soft(f"Seat{i}", (cw - 0.012, d - backD - 0.02, 0.16), (x, -backD / 2 + 0.01, z_seat), M.fabric, rad + 0.02))
        o.append(soft(f"Back{i}", (cw - 0.02, 0.18, 0.42 if kind != "boxy" else 0.36), (x, d / 2 - backD / 2 - 0.04, z_seat + 0.26),
                      M.fabric, rad + 0.03, rot=(math.radians(-9), 0, 0)))
    if kind != "low_frame":
        o.append(soft("BackFrame", (w, backD - 0.08, seatH + 0.24 - base_top), (0, d / 2 - (backD - 0.08) / 2, base_top + (seatH + 0.24 - base_top) / 2), M.fabric, rad))
    else:
        o.append(rb("BackRail", (w, 0.05, 0.3), (0, d / 2 - 0.025, legH + 0.06 + 0.15), M.wood, bev=0.008))
    # pillows + throw
    o.append(soft("Pillow1", (0.45, 0.13, 0.43), (-w / 2 + armW + 0.32, d / 2 - backD - 0.06, z_seat + 0.26), M.accent, 0.07, rot=(math.radians(-14), 0, math.radians(8))))
    o.append(soft("Pillow2", (0.43, 0.13, 0.41), (w / 2 - armW - 0.32, d / 2 - backD - 0.06, z_seat + 0.26), M.linen, 0.07, rot=(math.radians(-14), 0, math.radians(-10))))
    o.append(soft("Pillow3", (0.40, 0.12, 0.38), (w / 2 - armW - 0.62, d / 2 - backD - 0.04, z_seat + 0.24), M.fabric2, 0.07, rot=(math.radians(-12), 0, math.radians(6))))
    o.append(soft("Throw", (0.5, d - 0.1, 0.03), (w / 2 - armW - 0.3, -0.02, z_seat + 0.095), M.accent, 0.012, rot=(0, 0, math.radians(4))))
    return o


def bed(M, w, d):
    o = []; kind = M.X["bed"]
    if kind == "platform":    # japandi: low ash platform wider than the mattress
        # stays inside the plan footprint (nightstands sit right beside it); low plinth recessed underneath
        o.append(rb("Platform", (w, d - 0.02, 0.12), (0, -0.01, 0.1), M.wood, bev=0.01, uv_long=1))
        o.append(rb("PlatformPlinth", (w - 0.2, d - 0.25, 0.05), (0, 0, 0.025), M.dark, bev=0.002))
        mz = 0.16 + 0.11
        o.append(rb("Headboard", (w, 0.05, 0.5), (0, d / 2 - 0.025, 0.39), M.wood, bev=0.01))
    else:
        o.append(rb("BedFrame", (w, d, 0.24), (0, 0, 0.12 + 0.07), M.wood, bev=0.012, uv_long=1))
        o += _legs_style(M, w, d, 0.07, inset=0.08)
        mz = 0.31 + 0.11
        if kind == "channel":  # modern: tall upholstered channel-tufted headboard
            n = max(5, int(w / 0.16))
            for i in range(n):
                x = -w / 2 - 0.03 + (w + 0.06) / n * (i + 0.5)
                o.append(soft(f"Channel{i}", ((w + 0.06) / n - 0.004, 0.1, 0.7), (x, d / 2 - 0.05, 0.52), M.fabric2, 0.04))
        else:                  # scandinavian: oak slatted headboard
            o.append(rb("HBRail", (w + 0.04, 0.04, 0.06), (0, d / 2 - 0.02, 0.84), M.wood, bev=0.008))
            n = max(6, int(w / 0.11))
            for i in range(n):
                x = -w / 2 + w / n * (i + 0.5)
                o.append(rb(f"Slat{i}", (0.045, 0.025, 0.5), (x, d / 2 - 0.02, 0.57), M.wood, bev=0.006, uv_long=2))
    o.append(soft("Mattress", (w - 0.04, d - 0.08, 0.22), (0, -0.02, mz), M.linen, 0.045))
    top = mz + 0.11
    o.append(soft("Duvet", (w + 0.06, d * 0.68, 0.07), (0, -d / 2 + d * 0.34 - 0.03, top + 0.02), M.duvet, 0.03))
    o.append(soft("DuvetFold", (w + 0.07, 0.25, 0.08), (0, -d / 2 + d * 0.68 - 0.15, top + 0.04), M.duvet, 0.035))
    o.append(soft("Throw", (w + 0.1, 0.45, 0.05), (0, -d / 2 + 0.3, top + 0.06), M.accent, 0.02))
    np_ = 2 if w > 1.2 else 1
    for i in range(np_):
        x = 0 if np_ == 1 else (-1 + 2 * i) * w * 0.23
        o.append(soft(f"Pillow{i}", (w * (0.42 if np_ == 2 else 0.7), 0.36, 0.15), (x, d / 2 - 0.3, top + 0.1), M.linen, 0.065, rot=(math.radians(-20), 0, 0)))
        o.append(soft(f"PillowF{i}", (w * (0.36 if np_ == 2 else 0.55), 0.14, 0.32), (x, d / 2 - 0.47, top + 0.12), M.fabric if M.style != "modern" else M.accent, 0.06, rot=(math.radians(-25), 0, 0)))
    if w > 1.2:
        r = rug(M, w + 0.9, 1.6)[0]; r.location = (0, -0.3, 0.006); o.append(r)
    return o


def table(M, w, d, h=0.75, top=None):
    kind = M.X["chair"]
    o = [rb("Top", (w, d, 0.035), (0, 0, h - 0.0175), top or M.wood, bev=0.006)]
    if kind == "metal":   # modern: sled base in black steel
        for sx in (-1, 1):
            o.append(rb("SledU", (0.04, d - 0.15, 0.03), (sx * (w / 2 - 0.12), 0, h - 0.05), M.metal_black, bev=0.004))
            o.append(rb("SledB", (0.04, d - 0.15, 0.03), (sx * (w / 2 - 0.12), 0, 0.015), M.metal_black, bev=0.004))
            for sy in (-1, 1):
                o.append(rb("SledV", (0.04, 0.03, h - 0.06), (sx * (w / 2 - 0.12), sy * (d / 2 - 0.09), h / 2 - 0.02), M.metal_black, bev=0.004))
    elif kind == "ash_low":  # japandi: trestle legs
        for sx in (-1, 1):
            o.append(rb("Trestle", (0.07, d - 0.2, h - 0.035), (sx * (w / 2 - 0.2), 0, (h - 0.035) / 2), M.wood, bev=0.01, uv_long=2))
        o.append(rb("Stretcher", (w - 0.4, 0.05, 0.05), (0, 0, 0.25), M.wood, bev=0.008))
    else:                    # scandinavian: round tapered legs
        o += legs(w, d, h - 0.035, M.wood, inset=0.1, r=0.026, taper=0.65)
    return o


def chair_proc(M):
    """Dining chair; front faces -Y. Style variants: metal / oak_round / ash_low."""
    kind = M.X["chair"]; o = []
    if kind == "metal" and os.path.exists(os.path.join(ASSETS, "models", "dining_chair_02")):
        return ph("dining_chair_02", h=0.9, mode="fit")   # CC0 upholstered dining chair, front faces -Y like ours
    if kind == "metal":
        o.append(soft("ChSeat", (0.45, 0.44, 0.07), (0, 0, 0.46), M.fabric, 0.03))
        o.append(soft("ChBack", (0.44, 0.07, 0.3), (0, 0.2, 0.8), M.fabric, 0.03, rot=(math.radians(-8), 0, 0)))
        for sx in (-1, 1):
            o.append(rb("ChLegF", (0.018, 0.018, 0.43), (sx * 0.2, -0.18, 0.215), M.metal_black, bev=0.003, uv=False))
            o.append(rb("ChLegB", (0.018, 0.018, 0.92), (sx * 0.2, 0.2, 0.46), M.metal_black, bev=0.003, uv=False, rot=(math.radians(-5), 0, 0)))
    elif kind == "oak_round":
        seat = cyl("ChSeat", 0.23, 0.05, (0, 0, 0.45), M.fabric, segs=40, bev=0.015); seat.scale = (1, 0.95, 1); o.append(seat)
        for sx in (-1, 1):
            o.append(cyl("ChLegF", 0.017, 0.43, (sx * 0.18, -0.16, 0.215), M.wood, segs=16, r2=0.013))
            o.append(cyl("ChLegB", 0.017, 0.78, (sx * 0.17, 0.17, 0.39), M.wood, segs=16, r2=0.013))
        o.append(rb("ChBack", (0.42, 0.06, 0.07), (0, 0.19, 0.76), M.wood, bev=0.025, uv_long=0))
    else:
        o.append(rb("ChSeatF", (0.46, 0.44, 0.04), (0, 0, 0.44), M.wood, bev=0.008))
        o.append(soft("ChCush", (0.42, 0.40, 0.04), (0, 0, 0.48), M.linen, 0.015))
        for sx in (-1, 1):
            for sy in (-1, 1):
                o.append(rb("ChLeg", (0.035, 0.035, 0.42), (sx * 0.195, sy * 0.18, 0.21), M.wood, bev=0.006, uv_long=2))
            o.append(rb("ChPost", (0.035, 0.035, 0.32), (sx * 0.195, 0.18, 0.62), M.wood, bev=0.006, uv_long=2))
        o.append(rb("ChBack", (0.42, 0.03, 0.09), (0, 0.18, 0.72), M.wood, bev=0.01))
    return o


def chair_ph(x, y, rotz):
    parts = chair_proc(CUR_M[0])
    root = bpy.data.objects.new("Chair", None)
    for p in parts:
        if p.parent is None: p.parent = root
    root.location = (x, y, 0); root.rotation_euler = (0, 0, rotz)
    return [root] + parts


def wall_art(M, w=0.9, h=0.65, z=1.5, y=0.0, seed=0):
    """Framed abstract print (procedural canvas in the style palette) with a passe-partout."""
    fr = rb("ArtFrame", (w, 0.03, h), (0, y, z), M.metal_black if M.style == "modern" else M.wood, bev=0.004)
    mat_ = box("ArtMat", (w - 0.04, 0.032, h - 0.04), (0, y, z)); set_mat(mat_, M.white)
    cv = box("ArtCanvas", (w - 0.16, 0.034, h - 0.16), (0, y, z))
    m = pbr_material(f"ArtPrint{seed}", color=(0.8, 0.78, 0.74), rough=0.8)
    nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping"); mp.inputs["Location"].default_value = (seed * 1.7, seed * 0.3, 0)
    wv = N.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 1.2 + 0.5 * (seed % 3)
    wv.inputs["Distortion"].default_value = 5 + seed; wv.inputs["Detail"].default_value = 1
    L.new(tc.outputs["Generated"], mp.inputs["Vector"]); L.new(mp.outputs["Vector"], wv.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB"); el = cr.color_ramp.elements
    el[0].color = (*hex2rgb("#efe9df"), 1); el[1].color = (*hex2rgb(M.S["accent"]), 1); el[1].position = 0.8
    e2 = el.new(0.5); e2.color = (*hex2rgb(M.S["fabric2"]), 1)
    L.new(wv.outputs["Fac"], cr.inputs["Fac"]); L.new(cr.outputs["Color"], b.inputs["Base Color"])
    set_mat(cv, m)
    for o in (fr, mat_, cv): o["upper"] = True
    return [fr, mat_, cv]


def books(M, n, x0, y, z, length_axis="X", seed=0):
    """Row of standing books (procedural)."""
    rnd = random.Random(seed); o = []; x = x0
    for i in range(n):
        t = rnd.uniform(0.025, 0.045); h = rnd.uniform(0.2, 0.28); dd = rnd.uniform(0.15, 0.2)
        o.append(rb("Book", (t, dd, h), (x + t / 2, y, z + h / 2), rnd.choice(M.book_mats), bev=0.002, uv=False)); x += t + 0.002
    return o


def book_stack(M, x, y, z, n=3, seed=0):
    rnd = random.Random(seed); o = []
    for i in range(n):
        w, d, t = rnd.uniform(0.2, 0.28), rnd.uniform(0.15, 0.21), rnd.uniform(0.02, 0.04)
        o.append(rb("BookS", (w, d, t), (x, y, z + t / 2), rnd.choice(M.book_mats), bev=0.002, uv=False, rot=(0, 0, rnd.uniform(-0.3, 0.3)))); z += t
    return o


def dining(M, w, d, seats):
    tw, td = (1.8 if seats >= 6 else 1.2), 0.9
    o = table(M, tw, td)
    per = math.ceil(seats / 2)
    pitch = min(0.6, (tw - 0.3) / per)     # even spacing, clear of the table legs at the ends
    for side in (-1, 1):
        for i in range(per):
            x = (i - (per - 1) / 2) * pitch
            # chair front faces -Y locally: the chair on the -Y side must turn 180 deg to face the table.
            # Seat front tucks ~5 cm under the table edge; backrest + rear legs on the far side.
            o += chair_ph(x, side * (td / 2 + 0.19), math.pi if side < 0 else 0.0)
    o += ph({"modern": "ceramic_vase_03", "scandinavian": "ceramic_vase_02", "japandi": "ceramic_vase_04"}.get(M.style, "ceramic_vase_01"), h=0.32, lift=0.75)
    for p in ph("wooden_bowl_01", w=0.3, lift=0.75):
        if p.parent is None: p.location = (0.45, 0.05, 0.75)
        o.append(p)
    for p in ph("bananas", w=0.2, lift=0.78):
        if p.parent is None: p.location = (0.45, 0.05, 0.78)
        o.append(p)
    # runner
    o.append(rb("Runner", (tw * 0.6, 0.32, 0.003), (0, 0, 0.752), M.linen, bev=0.0, uv=False))
    return o


def kitchen(M, w, d=0.62, uppers=True):
    o = []; kind = M.X["kitchen"]
    n = max(2, round(w / 0.6)); cw = w / n
    o.append(rb("Plinth", (w - 0.02, d - 0.08, 0.1), (0, 0.03, 0.05), M.dark, bev=0.002))
    front = M.wood if kind == "ash_slat" else M.cabinet
    for i in range(n):
        x = -w / 2 + cw * (i + 0.5)
        if i % 3 == 1:   # drawer stack
            for k, (z0, hh) in enumerate(((0.1, 0.25), (0.355, 0.25), (0.61, 0.25))):
                o.append(rb(f"Drawer{i}{k}", (cw - 0.006, 0.02, hh - 0.006), (x, -d / 2 + 0.03, z0 + hh / 2), front, bev=0.003))
                if kind == "white_oak":
                    o.append(rb("PullOak", (0.2, 0.025, 0.02), (x, -d / 2 + 0.012, z0 + hh - 0.03), M.wood, bev=0.006))
        else:
            o.append(rb(f"Door{i}", (cw - 0.006, 0.02, 0.76), (x, -d / 2 + 0.03, 0.1 + 0.38), front, bev=0.003))
            if kind == "white_oak":
                o.append(rb(f"Pull{i}", (0.025, 0.025, 0.16), (x + (cw / 2 - 0.05) * (1 if i % 2 else -1), -d / 2 + 0.012, 0.75), M.wood, bev=0.006))
            elif kind == "ash_slat":
                for s in range(int(cw / 0.05)):
                    o.append(rb("Slat", (0.012, 0.008, 0.7), (x - cw / 2 + 0.03 + s * 0.05, -d / 2 + 0.017, 0.48), M.wood, bev=0.002, uv=False))
    if kind == "handleless":
        o.append(rb("Groove", (w, 0.025, 0.025), (0, -d / 2 + 0.035, 0.86), M.metal_black, bev=0.002, uv=False))
    o.append(rb("Carcass", (w, d - 0.04, 0.76), (0, 0.02, 0.48), M.cabinet, bev=0.002))
    o.append(rb("Counter", (w, d, 0.03 if kind != "ash_slat" else 0.04), (0, 0, 0.88), M.counter, bev=0.003))
    o.append(rb("Splash", (w, 0.012, 0.56), (0, d / 2 - 0.006, 1.18), M.backsplash, bev=0.0, uv=False))
    sx = -w / 2 + w * 0.32 if w > 2 else -w / 2 + 0.45
    o.append(rb("Sink", (0.6, 0.42, 0.02), (sx, -0.02, 0.8985), M.steel, bev=0.01))
    o.append(rb("SinkHole", (0.54, 0.36, 0.02), (sx, -0.02, 0.9), M.dark, bev=0.02))
    o.append(cyl("Tap", 0.015, 0.32, (sx, 0.22, 1.06), M.metal_black if kind == "handleless" else M.chrome, segs=16))
    o.append(cyl("Spout", 0.012, 0.2, (sx, 0.13, 1.21), M.metal_black if kind == "handleless" else M.chrome, segs=16, axis="Y"))
    hx = w / 2 - 0.5 if w > 2 else w / 2 - 0.4
    o.append(rb("Hob", (0.6, 0.5, 0.008), (hx, -0.02, 0.9015), M.screen, bev=0.003))
    for (ax, ay, r) in ((-0.15, -0.1, 0.09), (0.15, -0.1, 0.07), (-0.15, 0.12, 0.07), (0.15, 0.12, 0.09)):
        o.append(cyl("Burner", r, 0.001, (hx + ax, -0.02 + ay, 0.906), M.dark, segs=32))
    # oven under hob
    o.append(rb("Oven", (0.58, 0.022, 0.56), (hx, -d / 2 + 0.032, 0.48), M.screen, bev=0.004))
    o.append(rb("OvenBar", (0.45, 0.03, 0.02), (hx, -d / 2 + 0.01, 0.73), M.steel, bev=0.006))
    # counter props
    for p in ph("wooden_cutting_board", w=0.4, rotz=0.15):
        if p.parent is None: p.location = (sx + 0.55 if w > 2 else sx + 0.4, 0.12, 0.895)
        o.append(p)
    for p in ph("pot_enamel_01", w=0.24):
        if p.parent is None: p.location = (hx + 0.15, 0.08, 0.906)
        o.append(p)
    if uppers:
        for i in range(n):
            x = -w / 2 + cw * (i + 0.5)
            if abs(x - hx) < cw / 2 and kind != "ash_slat":
                continue
            u = rb(f"Upper{i}", (cw - 0.006, 0.34, 0.72), (x, d / 2 - 0.17, 1.86), front, bev=0.003)
            u["upper"] = True; o.append(u)
        hood = rb("Hood", (0.6, 0.4, 0.06), (hx, d / 2 - 0.2, 1.52), M.steel if kind != "handleless" else M.metal_black, bev=0.004); hood["upper"] = True; o.append(hood)
        chim = rb("HoodChimney", (0.3, 0.25, 0.9), (hx, d / 2 - 0.125, 2.0), M.steel if kind != "handleless" else M.metal_black, bev=0.004); chim["upper"] = True; o.append(chim)
        # under-cabinet LED strip
        led = rb("LED", (w - 0.1, 0.02, 0.008), (0, d / 2 - 0.3, 1.495), M.bulb, bev=0, uv=False); led["upper"] = True; o.append(led)
    return o


def island(M, w, d):
    o = [rb("IslandBody", (w - 0.04, d - 0.2, 0.86), (0, 0.06, 0.43), M.wood if M.X["kitchen"] == "ash_slat" else M.cabinet, bev=0.003),
         rb("IslandTop", (w, d, 0.04), (0, 0, 0.9), M.counter, bev=0.005)]
    for i in range(3):
        x = -w / 2 + w / 3 * (i + 0.5)
        o.append(cyl("StoolSeat", 0.18, 0.05, (x, -d / 2 - 0.22, 0.66), M.fabric2 if M.style == "modern" else M.wood, segs=32, bev=0.012))
        if M.style == "modern":
            o.append(cyl("StoolPost", 0.02, 0.62, (x, -d / 2 - 0.22, 0.32), M.metal_black, segs=12))
            o.append(cyl("StoolBase", 0.17, 0.015, (x, -d / 2 - 0.22, 0.008), M.metal_black, segs=32))
        else:
            for k in range(4):
                a = math.pi / 4 + k * math.pi / 2
                o.append(cyl("StoolLeg", 0.015, 0.66, (x + 0.12 * math.cos(a), -d / 2 - 0.22 + 0.12 * math.sin(a), 0.32), M.wood, segs=12, r2=0.012))
        o.append(cyl("StoolRing", 0.14, 0.012, (x, -d / 2 - 0.22, 0.25), M.metal_black if M.style == "modern" else M.wood, segs=32))
    for p in ph("wooden_bowl_01", w=0.32):
        if p.parent is None: p.location = (0.25, 0.05, 0.92)
        o.append(p)
    for (ax, ay) in ((0.2, 0.08), (0.3, 0.02), (0.26, -0.02)):
        for p in ph("food_apple_01", w=0.08):
            if p.parent is None: p.location = (ax, ay, 0.95)
            o.append(p)
    o += book_stack(M, -0.55, 0.1, 0.92, 2, seed=3)
    return o


def coffee_table(M, w, d):
    k = M.X["coffee"]
    if k == "low_ash":
        o = [rb("CTop", (w, d, 0.05), (0, 0, 0.33), M.wood, bev=0.01),
             rb("CShelf", (w - 0.1, d - 0.1, 0.025), (0, 0, 0.1), M.wood, bev=0.006)]
        for sx in (-1, 1):
            o.append(rb("CSide", (0.05, d, 0.31), (sx * (w / 2 - 0.025), 0, 0.155), M.wood, bev=0.008, uv_long=2))
        top = 0.355
    elif k == "coffee_table_round_01":
        o = ph(k, w=min(w, d) * 1.4, mode="fit"); top = 0.49 * (min(w, d) * 1.4 / 1.3)
    else:
        o = ph(k, w=w, d=d, mode="stretch"); top = 0.39
    o += book_stack(M, -0.18, 0.02, top, 3, seed=7)
    o += at(ph({"modern": "ceramic_vase_03", "scandinavian": "ceramic_vase_02", "japandi": "ceramic_vase_04"}.get(M.style, "ceramic_vase_01"),
               h=0.22), 0.22, 0.0, top)
    return o


def armchair(M, w, d):
    k = M.X["armchair"]
    if k == "round_boucle":
        o = [soft("ACBase", (w * 0.95, d * 0.9, 0.3), (0, 0, 0.3), M.fabric, 0.1),
             soft("ACSeat", (w * 0.7, d * 0.65, 0.12), (0, -0.05, 0.5), M.fabric, 0.06),
             soft("ACBack", (w * 0.95, 0.22, 0.42), (0, d * 0.34, 0.62), M.fabric, 0.11, rot=(math.radians(-10), 0, 0))]
        for sx in (-1, 1):
            o.append(soft(f"ACArm{sx}", (0.17, d * 0.85, 0.3), (sx * (w * 0.4), 0, 0.55), M.fabric, 0.08))
        o += legs(w * 0.8, d * 0.75, 0.15, M.wood, inset=0.05, r=0.02, taper=0.6)
        return o
    return ph(k, w=w, d=d, mode="fit")


def pendant(M, kind=None, drop=0.6, ceiling=2.7, size=1.0):
    """Ceiling pendant (style specific) with a real light source. Origin on the floor below it."""
    kind = kind or M.S["lamp"]; o = []
    z = ceiling - drop
    o.append(cyl("Cord", 0.004, drop, (0, 0, ceiling - drop / 2), M.dark, segs=8))
    o.append(cyl("Canopy", 0.06, 0.02, (0, 0, ceiling - 0.01), M.metal_black if kind == "black" else M.white, segs=24))
    if kind == "black":
        sh = cyl("Dome", 0.05 * size, 0.18 * size, (0, 0, z - 0.09 * size), M.metal_black, segs=48, r2=0.2 * size)
        o.append(sh); o.append(cyl("Diffuser", 0.17 * size, 0.005, (0, 0, z - 0.17 * size), M.bulb, segs=32))
    elif kind == "globe":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.17 * size, location=(0, 0, z - 0.17 * size), segments=32, ring_count=16)
        g = bpy.context.active_object; set_mat(g, M.shade); shade_smooth(g, 180); o.append(g)
    else:  # japandi: wide paper drum with an ash rim
        o.append(cyl("Drum", 0.3 * size, 0.2 * size, (0, 0, z - 0.1 * size), M.paper, segs=64))
        o.append(cyl("DrumRimT", 0.305 * size, 0.012, (0, 0, z - 0.006), M.wood, segs=64))
        o.append(cyl("DrumRimB", 0.305 * size, 0.012, (0, 0, z - 0.2 * size + 0.006), M.wood, segs=64))
    ld = bpy.data.lights.new("PendantLight", "POINT"); ld.energy = 45 * size; ld.color = (1.0, 0.8, 0.58); ld.shadow_soft_size = 0.08
    lo = bpy.data.objects.new("PendantLight", ld); lo.location = (0, 0, z - 0.24 * size); o.append(lo)
    for x in o: x["ceil"] = True
    return o


def downlight(M, ceiling=2.7, power=18):
    o = [cyl("DLRing", 0.045, 0.006, (0, 0, ceiling - 0.003), M.white, segs=24),
         cyl("DLLens", 0.035, 0.002, (0, 0, ceiling - 0.007), M.bulb, segs=24)]
    ld = bpy.data.lights.new("Downlight", "SPOT"); ld.energy = power; ld.spot_size = math.radians(110); ld.spot_blend = 0.6
    ld.color = (1.0, 0.84, 0.66); ld.shadow_soft_size = 0.03
    lo = bpy.data.objects.new("Downlight", ld); lo.location = (0, 0, ceiling - 0.012); o.append(lo)
    for x in o: x["ceil"] = True
    return o


def curtain_panel(M, width, height, folds=None, seed=0):
    """Wavy curtain panel (grid mesh, sine pleats) hanging from z=height; spans x in [0,width], y depth +-amp."""
    import bmesh
    folds = folds or max(4, int(width / 0.11)); nx = folds * 6; nz = 12; amp = 0.035
    rnd = random.Random(seed)
    v, f = [], []
    for k in range(nz + 1):
        z = height * k / nz
        for i in range(nx + 1):
            x = width * i / nx
            ph_ = 2 * math.pi * folds * i / nx
            a = amp * (0.85 + 0.3 * (1 - k / nz))
            v.append((x, a * math.sin(ph_), z))
    for k in range(nz):
        for i in range(nx):
            a = k * (nx + 1) + i
            f.append((a, a + 1, a + nx + 2, a + nx + 1))
    o = mesh_obj("Curtain", v, f)
    so = o.modifiers.new("Solid", "SOLIDIFY"); so.thickness = 0.004
    set_mat(o, M.curtain); shade_smooth(o, 180); o["upper"] = True
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
        dm = {"modern": M.cabinet, "japandi": M.wood}.get(M.style, M.white if i % 2 else M.wood)
        o.append(rb(f"WDoor{i}", (dw - 0.006, 0.02, h - 0.04), (x, -d / 2 + 0.005, h / 2), dm, bev=0.003))
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
          cyl("LampShade", 0.12, 0.17, (0.05, 0.0, top + 0.3), M.shade if M.style != "japandi" else M.paper, segs=48, r2=0.1)]
    o += book_stack(M, -0.1, -0.05, top, 2, seed=int(w * 100))
    return o


def plant(M, w, d, variant=0):
    aid = ("potted_plant_02", "potted_plant_01")[variant % 2]
    return ph(aid, w=w * 1.4, d=d * 1.4, h=1.1 if variant % 2 else 0.95, mode="fit")


def bistro(M, w, d):
    o = ph("round_wooden_table_02", w=0.75, d=0.75, mode="fit")
    o += chair_ph(-0.55, 0, math.pi / 2) + chair_ph(0.55, 0, -math.pi / 2)   # both face the table
    return o




def sideboard(M, w, d, h=0.72):
    """Low credenza with books, vase, frame and a table lamp."""
    o = [rb("SBBody", (w, d, h - 0.12), (0, 0, 0.12 + (h - 0.12) / 2), M.wood, bev=0.006, uv_long=0)]
    n = max(2, round(w / 0.45)); cw = w / n
    for i in range(n):
        x = -w / 2 + cw * (i + 0.5)
        o.append(rb("SBDoor", (cw - 0.008, 0.015, h - 0.16), (x, -d / 2 - 0.004, 0.12 + (h - 0.12) / 2), M.cabinet if M.style == "modern" else M.wood, bev=0.003))
    o += _legs_style(M, w - 0.06, d - 0.06, 0.12, inset=0.03) if M.X["leg"] != "block" else [rb("SBPl", (w - 0.08, d - 0.08, 0.12), (0, 0, 0.06), M.dark, bev=0.002)]
    o += books(M, 7, -w / 2 + 0.08, 0.0, h, seed=5)
    o += at(ph("ceramic_vase_02" if M.style != "japandi" else "ceramic_vase_04", h=0.3), w / 2 - 0.22, 0.0, h)
    o += at(ph("standing_picture_frame_01", h=0.22), 0.05, 0.05, h, rz=0.2)
    return o


def bench(M, w, d):
    o = [rb("BenchTop", (w, d, 0.04), (0, 0, 0.43), M.wood, bev=0.006, uv_long=0)]
    o += _legs_style(M, w, d, 0.41, inset=0.05) if M.X["leg"] != "block" else [rb("BenchSide", (0.04, d, 0.41), (sx * (w / 2 - 0.06), 0, 0.205), M.wood, bev=0.004) for sx in (-1, 1)]
    return o


def bookshelf(M, w, d):
    o = ph("wooden_display_shelves_01", w=w, d=d, mode="fit")
    return o


BUILDERS = {
    "sofa3": lambda M, f, it: sofa(M, f["w"], f["d"]),
    "sofa2": lambda M, f, it: sofa(M, f["w"], f["d"]),
    "armchair": lambda M, f, it: armchair(M, f["w"], f["d"]),
    "coffee": lambda M, f, it: coffee_table(M, f["w"], f["d"]),
    "tv": lambda M, f, it: tv_unit(M, f["w"], f["d"]),
    "rug": lambda M, f, it: rug(M, f["w"], f["d"]),
    "rugRound": lambda M, f, it: rug(M, f["w"], f["d"], True),
    "bookshelf": lambda M, f, it: bookshelf(M, f["w"], f["d"]),
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
    # round-3 extras (shots.json "extra_items")
    "ottoman": lambda M, f, it: ph("Ottoman_01", w=f["w"], d=f["d"], mode="fit"),
    "lounge": lambda M, f, it: ph("mid_century_lounge_chair", w=f["w"], d=f["d"], mode="fit"),
    "sideboard": lambda M, f, it: sideboard(M, f["w"], f["d"]),
    "basket": lambda M, f, it: ph("wicker_basket_02", w=f["w"], d=f["d"], mode="fit"),
    "bigplant": lambda M, f, it: ph("potted_plant_04", w=f["w"], d=f["d"], mode="fit"),
    "planter": lambda M, f, it: ph("planter_pot_clay", w=f["w"], d=f["d"], mode="fit"),
    "bench": lambda M, f, it: bench(M, f["w"], f["d"]),
}
