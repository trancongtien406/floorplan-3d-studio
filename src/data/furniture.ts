/** Procedural furniture library. Every piece is built from simple primitives so the app needs no model downloads,
 *  and the same parts are projected top-down to draw the 2D plan symbol. Units: metres. Local frame: x = width,
 *  y = up from the floor, z = depth (front of the piece faces +z). */
export type Mat =
  | 'fabric' | 'fabric2' | 'wood' | 'woodDark' | 'metal' | 'accent' | 'white' | 'ceramic' | 'glass' | 'plant' | 'pot'
  | 'rug' | 'mattress' | 'pillow' | 'counter' | 'screen' | 'lamp' | 'book';

export interface Part {
  shape: 'box' | 'cyl' | 'sphere';
  size: [number, number, number]; // box: w,h,d · cyl: radiusTop, h, radiusBottom · sphere: r,_,_
  pos: [number, number, number]; // centre of the part
  mat: Mat;
}

export interface FurnitureDef {
  label: string;
  category: 'Living' | 'Bedroom' | 'Kitchen & dining' | 'Bath' | 'Work' | 'Decor';
  w: number;
  d: number;
  parts: Part[];
}

const box = (w: number, h: number, d: number, x: number, y: number, z: number, mat: Mat): Part => ({ shape: 'box', size: [w, h, d], pos: [x, y, z], mat });
const cyl = (r: number, h: number, x: number, y: number, z: number, mat: Mat, r2 = r): Part => ({ shape: 'cyl', size: [r, h, r2], pos: [x, y, z], mat });
const legs = (w: number, d: number, h: number, inset = 0.05, mat: Mat = 'wood', r = 0.022): Part[] =>
  [[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([sx, sz]) => cyl(r, h, sx * (w / 2 - inset), h / 2, sz * (d / 2 - inset), mat, r * 0.8));

function cushions(w: number, d: number, seatH: number): Part[] {
  const n = Math.max(1, Math.round((w - 0.4) / 0.62));
  const cw = (w - 0.36) / n;
  return Array.from({ length: n }, (_, i: number) => box(cw - 0.02, 0.14, d - 0.3, -w / 2 + 0.18 + cw * (i + 0.5), seatH - 0.02, 0.1, 'fabric'));
}

function sofa(w: number, d = 0.92): Part[] {
  const seatH = 0.42;
  return [
    box(w, 0.2, d - 0.1, 0, 0.18, 0.04, 'fabric'),
    ...cushions(w, d, seatH),
    box(w, 0.5, 0.2, 0, 0.5, -d / 2 + 0.1, 'fabric'),
    box(0.18, 0.62, d, -w / 2 + 0.09, 0.31 + 0.02, 0, 'fabric'),
    box(0.18, 0.62, d, w / 2 - 0.09, 0.31 + 0.02, 0, 'fabric'),
    box(0.42, 0.36, 0.12, -w / 2 + 0.45, 0.58, -d / 2 + 0.26, 'pillow'),
    box(0.42, 0.36, 0.12, w / 2 - 0.45, 0.58, -d / 2 + 0.26, 'accent'),
    ...legs(w, d, 0.08, 0.06, 'woodDark', 0.025),
  ];
}

function bed(w: number, d: number): Part[] {
  return [
    box(w, 0.28, d, 0, 0.14 + 0.06, 0, 'wood'),
    box(w - 0.06, 0.22, d - 0.08, 0, 0.45, 0.02, 'mattress'),
    box(w + 0.04, 1.0, 0.08, 0, 0.5, -d / 2 + 0.04, 'wood'),
    box(w - 0.04, 0.06, d * 0.55, 0, 0.58, d * 0.2, 'fabric'),
    box(w * 0.4, 0.14, 0.34, -w * 0.23, 0.62, -d / 2 + 0.3, 'pillow'),
    box(w * 0.4, 0.14, 0.34, w * 0.23, 0.62, -d / 2 + 0.3, 'pillow'),
    ...legs(w, d, 0.06, 0.06, 'woodDark'),
  ];
}

function chair(): Part[] {
  return [box(0.44, 0.05, 0.44, 0, 0.45, 0, 'wood'), box(0.44, 0.42, 0.04, 0, 0.7, -0.2, 'wood'), ...legs(0.44, 0.44, 0.45, 0.04, 'woodDark', 0.018)];
}

function table(w: number, d: number, h = 0.75, round = false): Part[] {
  if (round) return [cyl(w / 2, 0.04, 0, h - 0.02, 0, 'wood'), cyl(0.05, h - 0.04, 0, (h - 0.04) / 2, 0, 'metal'), cyl(0.25, 0.03, 0, 0.015, 0, 'metal')];
  return [box(w, 0.04, d, 0, h - 0.02, 0, 'wood'), ...legs(w, d, h - 0.04, 0.06, 'woodDark', 0.025)];
}

function dining(w: number, d: number, seats: number): Part[] {
  const out = table(w, d);
  const per = Math.ceil(seats / 2);
  for (let side of [-1, 1]) {
    for (let i = 0; i < per; i++) {
      const x = -w / 2 + (w / per) * (i + 0.5);
      chair().forEach((p) => out.push({ ...p, pos: [p.pos[0] + x, p.pos[1], (p.pos[2] * -side) + side * (d / 2 + 0.12)] }));
    }
  }
  return out;
}

export const FURNITURE: Record<string, FurnitureDef> = {
  sofa3: { label: '3-seat sofa', category: 'Living', w: 2.2, d: 0.92, parts: sofa(2.2) },
  sofa2: { label: 'Loveseat', category: 'Living', w: 1.6, d: 0.88, parts: sofa(1.6, 0.88) },
  armchair: { label: 'Armchair', category: 'Living', w: 0.85, d: 0.85, parts: sofa(0.85, 0.85) },
  coffee: { label: 'Coffee table', category: 'Living', w: 1.1, d: 0.6, parts: [box(1.1, 0.05, 0.6, 0, 0.4, 0, 'wood'), box(1.0, 0.03, 0.5, 0, 0.12, 0, 'wood'), ...legs(1.1, 0.6, 0.38, 0.05, 'woodDark', 0.02)] },
  tv: { label: 'TV console', category: 'Living', w: 1.8, d: 0.42, parts: [box(1.8, 0.45, 0.42, 0, 0.3, 0, 'wood'), box(1.4, 0.8, 0.05, 0, 1.15, -0.12, 'screen'), box(0.3, 0.06, 0.2, 0, 0.56, -0.1, 'metal')] },
  rug: { label: 'Area rug', category: 'Decor', w: 2.4, d: 1.7, parts: [box(2.4, 0.012, 1.7, 0, 0.006, 0, 'rug')] },
  rugRound: { label: 'Round rug', category: 'Decor', w: 1.6, d: 1.6, parts: [cyl(0.8, 0.012, 0, 0.006, 0, 'rug')] },
  bookshelf: { label: 'Bookshelf', category: 'Living', w: 1.0, d: 0.35, parts: [box(1.0, 1.9, 0.35, 0, 0.95, 0, 'wood'), ...[0.35, 0.8, 1.25, 1.65].map((y, i) => box(0.86, 0.26, 0.22, (i % 2 ? 0.05 : -0.05), y, 0.05, 'book'))] },
  bedDouble: { label: 'Double bed 160', category: 'Bedroom', w: 1.7, d: 2.1, parts: bed(1.7, 2.1) },
  bedSingle: { label: 'Single bed 90', category: 'Bedroom', w: 1.0, d: 2.05, parts: bed(1.0, 2.05) },
  nightstand: { label: 'Nightstand', category: 'Bedroom', w: 0.48, d: 0.4, parts: [box(0.48, 0.5, 0.4, 0, 0.3, 0, 'wood'), ...legs(0.48, 0.4, 0.06, 0.04, 'woodDark'), cyl(0.07, 0.3, 0.08, 0.7, -0.05, 'lamp', 0.12)] },
  wardrobe: { label: 'Wardrobe', category: 'Bedroom', w: 1.6, d: 0.6, parts: [box(1.6, 2.2, 0.6, 0, 1.1, 0, 'white'), box(0.02, 2.1, 0.01, 0, 1.1, 0.305, 'woodDark'), box(0.02, 0.3, 0.03, -0.06, 1.1, 0.31, 'metal'), box(0.02, 0.3, 0.03, 0.06, 1.1, 0.31, 'metal')] },
  dresser: { label: 'Dresser', category: 'Bedroom', w: 1.2, d: 0.48, parts: [box(1.2, 0.8, 0.48, 0, 0.48, 0, 'wood'), ...legs(1.2, 0.48, 0.08, 0.05, 'woodDark')] },
  dining4: { label: 'Dining set (4)', category: 'Kitchen & dining', w: 1.4, d: 1.7, parts: dining(1.4, 0.85, 4) },
  dining6: { label: 'Dining set (6)', category: 'Kitchen & dining', w: 1.9, d: 1.8, parts: dining(1.9, 0.95, 6) },
  bistro: { label: 'Round bistro table', category: 'Kitchen & dining', w: 0.8, d: 0.8, parts: table(0.8, 0.8, 0.75, true) },
  kitchen: { label: 'Kitchen run 3 m', category: 'Kitchen & dining', w: 3.0, d: 0.62, parts: [box(3.0, 0.86, 0.6, 0, 0.43, 0, 'white'), box(3.04, 0.04, 0.64, 0, 0.88, 0.01, 'counter'), box(3.0, 0.7, 0.35, 0, 1.85, -0.13, 'white'), box(0.6, 0.02, 0.45, -0.6, 0.905, 0.02, 'metal'), box(0.6, 0.02, 0.5, 0.75, 0.905, 0.02, 'screen')] },
  kitchenShort: { label: 'Kitchenette 1.8 m', category: 'Kitchen & dining', w: 1.8, d: 0.62, parts: [box(1.8, 0.86, 0.6, 0, 0.43, 0, 'white'), box(1.84, 0.04, 0.64, 0, 0.88, 0.01, 'counter'), box(1.8, 0.7, 0.35, 0, 1.85, -0.13, 'white'), box(0.45, 0.02, 0.4, -0.4, 0.905, 0.02, 'metal'), box(0.5, 0.02, 0.45, 0.45, 0.905, 0.02, 'screen')] },
  island: { label: 'Kitchen island', category: 'Kitchen & dining', w: 1.8, d: 0.9, parts: [box(1.7, 0.86, 0.8, 0, 0.43, 0, 'woodDark'), box(1.8, 0.04, 0.9, 0, 0.88, 0, 'counter'), ...[-0.5, 0, 0.5].map((x) => cyl(0.18, 0.04, x, 0.66, 0.62, 'fabric2')), ...[-0.5, 0, 0.5].map((x) => cyl(0.02, 0.64, x, 0.32, 0.62, 'metal'))] },
  fridge: { label: 'Fridge', category: 'Kitchen & dining', w: 0.7, d: 0.68, parts: [box(0.7, 1.9, 0.68, 0, 0.95, 0, 'white'), box(0.69, 0.01, 0.01, 0, 1.3, 0.345, 'counter'), box(0.03, 0.5, 0.03, 0.28, 1.6, 0.35, 'metal'), box(0.03, 0.35, 0.03, 0.28, 1.0, 0.35, 'metal')] },
  bathtub: { label: 'Bathtub', category: 'Bath', w: 1.7, d: 0.75, parts: [box(1.7, 0.56, 0.75, 0, 0.28, 0, 'ceramic'), box(1.5, 0.05, 0.58, 0, 0.55, 0, 'glass')] },
  shower: { label: 'Shower 90', category: 'Bath', w: 0.9, d: 0.9, parts: [box(0.9, 0.05, 0.9, 0, 0.025, 0, 'ceramic'), box(0.9, 2.0, 0.01, 0, 1.0, 0.445, 'glass'), box(0.01, 2.0, 0.9, 0.445, 1.0, 0, 'glass'), cyl(0.1, 0.02, -0.2, 1.9, -0.2, 'metal')] },
  toilet: { label: 'Toilet', category: 'Bath', w: 0.4, d: 0.68, parts: [box(0.38, 0.4, 0.18, 0, 0.6, -0.25, 'ceramic'), cyl(0.18, 0.4, 0, 0.2, 0.08, 'ceramic', 0.15)] },
  vanity: { label: 'Vanity + sink', category: 'Bath', w: 0.9, d: 0.48, parts: [box(0.9, 0.5, 0.46, 0, 0.55, 0, 'wood'), box(0.92, 0.04, 0.48, 0, 0.82, 0, 'counter'), cyl(0.17, 0.12, 0, 0.9, 0.03, 'ceramic', 0.14), box(0.7, 0.8, 0.02, 0, 1.45, -0.23, 'glass')] },
  desk: { label: 'Desk', category: 'Work', w: 1.4, d: 0.7, parts: [...table(1.4, 0.7), box(0.55, 0.32, 0.03, 0, 0.96, -0.2, 'screen'), box(0.08, 0.16, 0.08, 0, 0.8, -0.2, 'metal')] },
  officeChair: { label: 'Office chair', category: 'Work', w: 0.62, d: 0.62, parts: [cyl(0.26, 0.06, 0, 0.47, 0, 'fabric2'), box(0.46, 0.5, 0.06, 0, 0.8, -0.22, 'fabric2'), cyl(0.03, 0.4, 0, 0.25, 0, 'metal'), cyl(0.3, 0.04, 0, 0.04, 0, 'metal')] },
  plant: { label: 'Floor plant', category: 'Decor', w: 0.5, d: 0.5, parts: [cyl(0.18, 0.4, 0, 0.2, 0, 'pot', 0.14), { shape: 'sphere', size: [0.32, 0, 0], pos: [0, 0.75, 0], mat: 'plant' }, { shape: 'sphere', size: [0.22, 0, 0], pos: [0.12, 1.0, 0.05], mat: 'plant' }] },
  floorLamp: { label: 'Floor lamp', category: 'Decor', w: 0.4, d: 0.4, parts: [cyl(0.16, 0.03, 0, 0.015, 0, 'metal'), cyl(0.015, 1.45, 0, 0.75, 0, 'metal'), cyl(0.13, 0.28, 0, 1.55, 0, 'lamp', 0.2)] },
  stairs: { label: 'Straight stairs', category: 'Living', w: 1.0, d: 2.8, parts: [
    ...Array.from({ length: 14 }, (_, i) => box(1.0, 0.045, 0.27, 0, 0.19 * (i + 1) - 0.02, 1.4 - 0.2 - i * 0.185, 'wood')),
    ...Array.from({ length: 14 }, (_, i) => box(1.0, 0.19 * (i + 1), 0.02, 0, (0.19 * (i + 1)) / 2, 1.4 - 0.06 - i * 0.185, 'white')),
  ] },
  washer: { label: 'Washer', category: 'Bath', w: 0.6, d: 0.6, parts: [box(0.6, 0.85, 0.6, 0, 0.425, 0, 'white'), cyl(0.2, 0.02, 0, 0.45, 0.3, 'glass')] },
};

export const CATEGORIES = ['Living', 'Bedroom', 'Kitchen & dining', 'Bath', 'Work', 'Decor'] as const;
