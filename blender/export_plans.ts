// Dumps the demo plans + furniture footprints to JSON for the Blender render worker.
// Run: npx vite-node blender/export_plans.ts
import { writeFileSync } from 'node:fs';
import { DEMO_PLANS } from '../src/data/demoPlans';
import { FURNITURE } from '../src/data/furniture';
for (const p of DEMO_PLANS) writeFileSync(`blender/plans/${p.id}.json`, JSON.stringify(p, null, 2));
const fp: Record<string, { label: string; w: number; d: number; h: number }> = {};
for (const [k, v] of Object.entries(FURNITURE)) {
  const h = Math.max(...v.parts.map((pt) => pt.pos[1] + (pt.shape === 'sphere' ? pt.size[0] : pt.size[1] / 2)));
  fp[k] = { label: v.label, w: v.w, d: v.d, h: +h.toFixed(3) };
}
writeFileSync('blender/plans/furniture_footprints.json', JSON.stringify(fp, null, 2));
console.log('ok', DEMO_PLANS.map((p) => p.id));
