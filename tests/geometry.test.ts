import { describe, expect, it } from 'vitest';
import { centroid, polygonArea, projectOnSegment, rectWalls, validatePlan, wallSpans } from '../src/geometry';
import { DEMO_PLANS } from '../src/data/demoPlans';
import { FURNITURE } from '../src/data/furniture';

describe('geometry', () => {
  it('computes polygon area and centroid', () => {
    const sq: [number, number][] = [[0, 0], [4, 0], [4, 3], [0, 3]];
    expect(polygonArea(sq)).toBeCloseTo(12);
    expect(centroid(sq)).toEqual([2, 1.5]);
  });

  it('projects a point onto a wall', () => {
    const r = projectOnSegment([2, 1], [0, 0], [4, 0]);
    expect(r.t).toBeCloseTo(0.5);
    expect(r.d).toBeCloseTo(1);
  });

  it('splits a wall around a window into below-sill, above-head and solid spans', () => {
    const [w] = rectWalls(0, 0, 4, 3, 0.2, 2.7);
    const spans = wallSpans(w, [{ id: 'o', wallId: w.id, kind: 'window', t: 0.5, width: 1, height: 1.2, sill: 0.9 }]);
    expect(spans).toHaveLength(4);
    expect(spans[0]).toMatchObject({ from: 0, to: 1.5, bottom: 0, top: 2.7 });
    expect(spans[1]).toMatchObject({ from: 1.5, to: 2.5, bottom: 0, top: 0.9 });
    expect(spans[2].bottom).toBeCloseTo(2.1);
    expect(spans[3]).toMatchObject({ from: 2.5, to: 4 });
  });

  it('rejects JSON that is not a plan', () => {
    expect(() => validatePlan({ foo: 1 })).toThrow();
    expect(validatePlan({ walls: [], rooms: [] }).openings).toEqual([]);
  });
});

describe('demo plans', () => {
  for (const plan of DEMO_PLANS) {
    it(`${plan.name}: openings reference real walls, items exist in the library`, () => {
      const ids = new Set(plan.walls.map((w) => w.id));
      for (const o of plan.openings) expect(ids.has(o.wallId)).toBe(true);
      for (const it of plan.items) expect(FURNITURE[it.type], it.type).toBeTruthy();
      expect(plan.rooms.reduce((s, r) => s + polygonArea(r.points), 0)).toBeGreaterThan(30);
    });
  }
});
