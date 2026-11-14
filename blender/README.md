# Blender render worker (photoreal output for Floorplan 3D Studio)

The web app is for drawing and previewing. This worker turns the app's **Plan JSON** export into
client-grade Cycles renders: real wall openings, PBR floors, baseboards, CC0 furniture sized to the plan,
sun + HDRI daylight.

```
plan JSON  ──►  render_plan.py (Blender 4.2, headless)  ──►  top / dollhouse / isometric / interior PNGs
```

| View | What it is |
|---|---|
| `top` | orthographic furnished 2D->3D plan (dark wall cuts, soft sun) |
| `dollhouse` | isometric cutaway, walls cut at 1.2 m (`--cut`) |
| `iso` | isometric, full-height walls |
| `living`, `kitchen`, `bedroom` (`interior1/2` for older plans) | eye-level shots defined in `shots.json` (camera, lens, fill lights, exposure) |
| `<view>_hero` | the same view at 2560x1440 |

## Run

```bash
python3 blender/fetch_assets.py                    # CC0 assets from Poly Haven -> blender/assets/
npx vite-node blender/export_plans.ts               # demo plans -> blender/plans/*.json (or use the app's "Plan JSON" button)
blender -b -P blender/render_plan.py -- --plan blender/plans/twobed.json --out blender/renders/twobed \
        --views top,dollhouse,iso,interior1,interior2 --samples 48 --samples-interior 96
```

Options: `--style modern|scandinavian|japandi` (furniture families + materials, not just colours),
`--tag _modern` (output suffix), `--pct 40` (preview size), `--cut 1.2` (dollhouse wall height),
`--save-blend` (scene organised into Architecture / Furniture / Lighting / Cameras / Environment, textures packed).
Every run also writes `<plan>_report.json` with wall lengths, room sizes, built outer size and render times,
so the 3D can be checked against the 2D dimension labels.

Measured on an 8-vCPU cloud box, CPU only (no GPU), Cycles + OpenImageDenoise, 1920x1080:
top ~1.5-2 min, dollhouse ~1 min, interiors ~4-8 min, 2560x1440 hero ~10 min (see the report files).

## Style presets (round 3)

| | Modern | Scandinavian | Japandi |
|---|---|---|---|
| Floor | herringbone parquet | light laminate | wide oak planks |
| Wood | walnut | white oak | ash |
| Sofa | boxy, thin arms, black metal legs, velvet | rounded boucle, tapered oak legs | low, on an ash frame, linen |
| Bed | channel-tufted headboard | oak slat headboard | low ash platform |
| Dining | CC0 upholstered chairs, steel sled table | round-seat oak chairs, tapered legs | ash chairs + trestle table |
| Kitchen | black handleless, marble | white with oak pulls | ash slat fronts |
| Pendants | black domes | opal globes | paper drums |

Also per scene: curtains (sheer, translucent) at every large window, pendants over dining + island and
downlights with real light sources (interior shots only), sideboard/books/vases/fruit/cutting board/pot decor,
tiled backsplash with LED strip, brass/oak threshold where two floors meet without a wall, garden HDRI seen
through the windows (dimmed for camera rays so it is not blown out, full strength for lighting).

## Checks

* `plan2d.py` draws the 2D plan (walls, openings, door swings in the app's handedness, room areas, dimension
  chains) and overlays the plan geometry on the orthographic top render, measuring the built outer size in
  pixels: twobed measures 10.193 x 8.195 m vs 10.20 x 8.20 m (1 px = 6.1 mm).
* Every run does an automated clash check (furniture vs furniture via bounding boxes refined to real vertices,
  dining chairs vs their table, furniture footprints vs walls) and writes it to `<plan>_report.json`
  (`clash_check`). Overlaps that exist in a source plan can be fixed per plan with `shots.json -> nudge`.

## Dimensions

Plan coordinates are metres on wall centre-lines, the same numbers the 2D editor labels
(`7.00 m`, `5.60 m` ...). Walls are built centred on those lines with their real thickness, so the outside
of a 7.0 x 5.6 m plan with 0.2 m walls measures 7.2 x 5.8 m.

## Blender MCP

`render_plan.py` is plain `bpy` and runs headless, which is what a server needs. For interactive work an
AI client can drive the same functions inside a Blender GUI through
[MCP for Blender](https://github.com/ahujasid/mcp-for-blender) (`uvx mcp-for-blender setup`, then enable the
addon); it is optional and not needed for these renders.

Asset licences: see [CREDITS.md](CREDITS.md).

## Sample output — round 4 (accuracy, artifacts, framing, presentation)

**Accuracy.** Room areas are now *net* (polygons offset to the inside wall faces, `plan2d.py --areas`):
Bedroom 1 14.75, Bath 4.59, Bedroom 2 14.75, Hall 2.52, Living & dining 26.50, Kitchen 11.14 = **74.25 m² net**;
80.00 m² is the gross area on wall centre-lines and 83.64 m² the gross external area. Each figure is labelled with its basis.
`present.py` reads the *built* geometry from Blender object coordinates (wall boxes, door/window jambs, door pivots
at 80° open), not from pixels, and compares it to the plan: 18/18 checks, max deviation 0.00 mm
(`previews/r4_geometry_proof.csv`). The clean overlay keeps its legend in the margin.

**Artifacts fixed.** Vertical "cables" were curtain rods with an overwritten rotation (now horizontal, with brackets and finials).
The hob glow came from a mirror-glossy hob reflecting the pot (now satin glass-ceramic with printed zones).
The white island block is now a wooden tray. The white block in the dollhouse was the wardrobe: tall furniture is now sectioned at the cut height with dark caps.
Circulation is about 0.9 m around the island, dining table and beds.

| | |
|---|---|
| ![](previews/r4_gallery_a_dollhouse.jpg) | ![](previews/r4_gallery_b_plan_vs_3d.jpg) |
| ![](previews/r4_gallery_c_interiors.jpg) | ![](previews/r4_gallery_d_styles.jpg) |
| ![](previews/r4_technical_top.jpg) labelled technical top view | ![](previews/r4_geometry_overlay.jpg) model-coordinate overlay |
| ![](previews/r4_twobed_modern_iso.jpg) isometric | ![](previews/r4_townhouse_dining.jpg) townhouse dining (stair shadows lifted) |

Styles differ in design language as well as colour: Modern uses black metal and dark walnut. Scandinavian uses light oak, warm white and linen.
Japandi is low-profile, with textured taupe plaster and minimal decor. Exposure is matched across the three (mean luminance 153 / 147 / 145).
Render times (8 vCPU shared, no GPU, 2560x1440): top 2.4 min, dollhouse 2.1, iso 2.2 at 48 spp. Interiors take 8.1-15.3 min at 80 spp.

## Sample output — round 3 (twobed, Modern apartment, 2560x1440, Cycles CPU + OIDN)

| | |
|---|---|
| ![](previews/r3_twobed_plan_2d.jpg) 2D plan | ![](previews/r3_twobed_modern_top.jpg) furnished top view |
| ![](previews/r3_twobed_modern_dollhouse.jpg) dollhouse | ![](previews/r3_twobed_modern_iso.jpg) isometric |
| ![](previews/r3_twobed_modern_living.jpg) living / dining | ![](previews/r3_twobed_modern_kitchen.jpg) kitchen |
| ![](previews/r3_twobed_modern_bedroom.jpg) master bedroom | ![](previews/r3_twobed_dimension_check.jpg) plan overlay on the top render |

Signature room in the three styles, same camera:

| Modern | Scandinavian | Japandi |
|---|---|---|
| ![](previews/r3_twobed_modern_living.jpg) | ![](previews/r3_twobed_scandinavian_living.jpg) | ![](previews/r3_twobed_japandi_living.jpg) |

Render times (8 vCPU, no GPU): top 2.5 min, dollhouse 2.1 min, iso 2.0 min at 48 spp; interiors 6.3-12.6 min at
80 spp (adaptive, denoised), all 2560x1440.

### Round 2 (for comparison)

| | |
|---|---|
| ![](previews/twobed_dollhouse.jpg) | ![](previews/townhouse_dollhouse.jpg) |
| ![](previews/twobed_top.jpg) | ![](previews/townhouse_interior2_hero.jpg) |
