"""Download the Poly Haven (CC0) assets this worker uses, via the public API https://api.polyhaven.com.

    python3 blender/fetch_assets.py            # everything in REQUIRED -> blender/assets/
    python3 blender/fetch_assets.py models sofa_02 1k
"""
import json, os, sys, urllib.request
UA = {"User-Agent": "floorplan-3d-studio-blender-worker/1.0"}
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
def dl(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0: return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(get(url))
REQUIRED = [
    ("hdris", "kloofendal_48d_partly_cloudy_puresky", "2k"),
    ("hdris", "greenwich_park_02", "2k"),
    ("textures", "herringbone_parquet", "2k"),
    ("textures", "laminate_floor_02", "2k"),
    ("textures", "oak_wood_planks", "2k"),
    ("textures", "marble_01", "2k"),
    ("textures", "dark_wood", "2k"),
    ("textures", "white_oak_veneer", "2k"),
    ("textures", "ash_veneer", "2k"),
    ("textures", "long_white_tiles", "2k"),
    ("textures", "velour_velvet", "2k"),
    ("textures", "wool_boucle", "2k"),
    ("textures", "rough_linen", "2k"),
    ("textures", "knitted_fleece", "2k"),
    ("textures", "poly_wool_herringbone", "2k"),
    ("textures", "oak_veneer_01", "2k"),
    ("textures", "granite_tile", "2k"),
    ("textures", "brown_leather", "2k"),
    ("models", "Ottoman_01", "1k"),
    ("models", "bananas", "1k"),
    ("models", "ceramic_vase_01", "1k"),
    ("models", "ceramic_vase_02", "1k"),
    ("models", "ceramic_vase_03", "1k"),
    ("models", "ceramic_vase_04", "1k"),
    ("models", "coffee_table_round_01", "1k"),
    ("models", "desk_lamp_arm_01", "1k"),
    ("models", "dining_chair_02", "1k"),
    ("models", "food_apple_01", "1k"),
    ("models", "modern_arm_chair_01", "1k"),
    ("models", "modern_coffee_table_01", "1k"),
    ("models", "modern_wooden_cabinet", "1k"),
    ("models", "planter_pot_clay", "1k"),
    ("models", "pot_enamel_01", "1k"),
    ("models", "potted_plant_01", "1k"),
    ("models", "potted_plant_02", "1k"),
    ("models", "potted_plant_04", "1k"),
    ("models", "side_table_01", "1k"),
    ("models", "standing_picture_frame_01", "1k"),
    ("models", "wicker_basket_02", "1k"),
    ("models", "wooden_bowl_01", "1k"),
    ("models", "wooden_cutting_board", "1k"),
    ("models", "wooden_display_shelves_01", "1k"),
]
BASE = os.environ.get("BLENDER_ASSETS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))


def fetch(kind, aid, res):
    files = json.loads(get(f"https://api.polyhaven.com/files/{aid}"))
    root = os.path.join(BASE, kind, aid)
    _fetch(files, kind, aid, res, root)


def _fetch(files, kind, aid, res, root):
    if kind == "hdris":
        f = files["hdri"][res]["hdr"]; dl(f["url"], os.path.join(root, f"{aid}_{res}.hdr"))
    elif kind == "models":
        g = files["gltf"][res]["gltf"]; dl(g["url"], os.path.join(root, f"{aid}.gltf"))
        for rel, inc in g.get("include", {}).items(): dl(inc["url"], os.path.join(root, rel))
    elif kind == "textures":
        for m in ["Diffuse", "nor_gl", "Rough"]:
            if m in files and res in files[m]:
                fm = files[m][res]; fmt = "jpg" if "jpg" in fm else ("png" if "png" in fm else list(fm)[0])
                dl(fm[fmt]["url"], os.path.join(root, f"{aid}_{m}_{res}.{fmt}"))
    print("ok", kind, aid)


if __name__ == "__main__":
    if len(sys.argv) == 4:
        fetch(*sys.argv[1:4])
    else:
        for k, a, r in REQUIRED: fetch(k, a, r)
