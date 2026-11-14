import type { Opening, Plan, Vec2, Wall } from './types';

export const uid = (p = 'id') => `${p}_${Math.random().toString(36).slice(2, 9)}`;

export const len = (a: Vec2, b: Vec2) => Math.hypot(b[0] - a[0], b[1] - a[1]);

export const snap = (v: number, step = 0.1) => Math.round(v / step) * step;

/** Shoelace area in m² (absolute). */
export function polygonArea(pts: Vec2[]): number {
  let s = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i];
    const [x2, y2] = pts[(i + 1) % pts.length];
    s += x1 * y2 - x2 * y1;
  }
  return Math.abs(s) / 2;
}

export function centroid(pts: Vec2[]): Vec2 {
  let x = 0, y = 0, a = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i];
    const [x2, y2] = pts[(i + 1) % pts.length];
    const f = x1 * y2 - x2 * y1;
    x += (x1 + x2) * f; y += (y1 + y2) * f; a += f;
  }
  if (Math.abs(a) < 1e-9) return pts[0] ?? [0, 0];
  return [x / (3 * a), y / (3 * a)];
}

/** Closest point on segment ab to p, returns t in 0..1 and the distance. */
export function projectOnSegment(p: Vec2, a: Vec2, b: Vec2): { t: number; d: number; q: Vec2 } {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy || 1e-9;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2));
  const q: Vec2 = [a[0] + t * dx, a[1] + t * dy];
  return { t, d: len(p, q), q };
}

export function nearestWall(p: Vec2, walls: Wall[], max = 0.4) {
  let best: { wall: Wall; t: number; d: number } | null = null;
  for (const w of walls) {
    const r = projectOnSegment(p, w.a, w.b);
    if (r.d <= max && (!best || r.d < best.d)) best = { wall: w, t: r.t, d: r.d };
  }
  return best;
}

/** Wall pieces between openings, in metres along the wall: solid spans and openings with their sill/head. */
export interface WallSpan { from: number; to: number; bottom: number; top: number }

export function wallSpans(wall: Wall, openings: Opening[]): WallSpan[] {
  const L = len(wall.a, wall.b);
  const ops = openings
    .filter((o) => o.wallId === wall.id)
    .map((o) => ({ s: Math.max(0, o.t * L - o.width / 2), e: Math.min(L, o.t * L + o.width / 2), o }))
    .sort((p, q) => p.s - q.s);
  const out: WallSpan[] = [];
  let cur = 0;
  for (const { s, e, o } of ops) {
    if (s > cur) out.push({ from: cur, to: s, bottom: 0, top: wall.height });
    if (o.sill > 0) out.push({ from: s, to: e, bottom: 0, top: o.sill });
    const head = Math.min(wall.height, o.sill + o.height);
    if (head < wall.height) out.push({ from: s, to: e, bottom: head, top: wall.height });
    cur = Math.max(cur, e);
  }
  if (cur < L) out.push({ from: cur, to: L, bottom: 0, top: wall.height });
  return out.filter((sp) => sp.to - sp.from > 1e-4 && sp.top - sp.bottom > 1e-4);
}

export function planBounds(plan: Plan) {
  const xs: number[] = [], ys: number[] = [];
  for (const w of plan.walls) { xs.push(w.a[0], w.b[0]); ys.push(w.a[1], w.b[1]); }
  for (const r of plan.rooms) for (const p of r.points) { xs.push(p[0]); ys.push(p[1]); }
  if (!xs.length) return { minX: 0, minY: 0, maxX: 10, maxY: 8, w: 10, h: 8, cx: 5, cy: 4 };
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  return { minX, minY, maxX, maxY, w: maxX - minX, h: maxY - minY, cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 };
}

export function totalArea(plan: Plan) {
  return plan.rooms.reduce((s, r) => s + polygonArea(r.points), 0);
}

/** Make a closed rectangular wall loop helper used by the demo plans. */
export function rectWalls(x: number, y: number, w: number, h: number, t = 0.2, height = 2.7, prefix = 'w'): Wall[] {
  const p: Vec2[] = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
  return p.map((a, i) => ({ id: `${prefix}${i}`, a, b: p[(i + 1) % 4], thickness: t, height }));
}

export function validatePlan(raw: unknown): Plan {
  const p = raw as Plan;
  if (!p || !Array.isArray(p.walls) || !Array.isArray(p.rooms)) throw new Error('Not a floor plan JSON (needs walls[] and rooms[])');
  return {
    id: p.id || uid('plan'), name: p.name || 'Imported plan', subtitle: p.subtitle,
    walls: p.walls, openings: p.openings || [], rooms: p.rooms, items: p.items || [], style: p.style || 'modern',
  };
}
