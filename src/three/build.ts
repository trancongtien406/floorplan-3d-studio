import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { FURNITURE, type Mat } from '../data/furniture';
import { STYLES } from '../data/styles';
import { len, wallSpans } from '../geometry';
import type { Opening, Plan, Wall } from '../types';
import { floorTexture } from './textures';

export interface BuildOptions {
  cutaway?: number | null; // wall height override for dollhouse cut-away views
}

const geoCache = new Map<string, THREE.BufferGeometry>();
function boxGeo(w: number, h: number, d: number, round = true) {
  const key = `${w.toFixed(3)}_${h.toFixed(3)}_${d.toFixed(3)}_${round}`;
  let g = geoCache.get(key);
  if (!g) {
    const r = Math.min(0.02, w / 4, h / 4, d / 4);
    g = round && r > 0.004 ? new RoundedBoxGeometry(w, h, d, 2, r) : new THREE.BoxGeometry(w, h, d);
    geoCache.set(key, g);
  }
  return g;
}

function std(color: string, o: { roughness?: number; metalness?: number; emissive?: string; opacity?: number } = {}) {
  const m = new THREE.MeshStandardMaterial({ color, roughness: o.roughness ?? 0.8, metalness: o.metalness ?? 0 });
  if (o.emissive) m.emissive = new THREE.Color(o.emissive);
  if (o.opacity !== undefined) { m.transparent = true; m.opacity = o.opacity; m.depthWrite = false; }
  return m;
}

export function buildPlan(plan: Plan, opts: BuildOptions = {}): THREE.Group {
  const style = STYLES[plan.style];
  const root = new THREE.Group();
  root.name = plan.name;
  const mats = new Map<Mat, THREE.MeshStandardMaterial>();
  const mat = (m: Mat) => {
    let x = mats.get(m);
    if (!x) { x = std(style.mats[m].color, style.mats[m]); x.name = m; mats.set(m, x); }
    return x;
  };
  const wallMat = std(style.wall, { roughness: 0.92 }); wallMat.name = 'wall_paint';
  const capMat = std(style.wallTop, { roughness: 0.7 }); capMat.name = 'wall_cut';
  const frameMat = std('#f4f4f2', { roughness: 0.4 }); frameMat.name = 'frame';
  const glassMat = std('#bfe3ef', { roughness: 0.05, opacity: 0.28 }); glassMat.name = 'glass';
  const doorMat = mat('wood');

  // floors
  const floors = new THREE.Group(); floors.name = 'floors';
  for (const room of plan.rooms) {
    const shape = new THREE.Shape(room.points.map(([x, y]) => new THREE.Vector2(x, -y)));
    const geo = new THREE.ShapeGeometry(shape);
    geo.rotateX(-Math.PI / 2);
    const f = style.floors[room.floor];
    const m = new THREE.MeshStandardMaterial({ map: floorTexture(room.floor, f.base, f.alt), roughness: room.floor === 'tile' ? 0.35 : 0.75 });
    m.name = `floor_${room.floor}`;
    const mesh = new THREE.Mesh(geo, m);
    mesh.name = room.name;
    mesh.receiveShadow = true;
    mesh.position.y = 0.002;
    floors.add(mesh);
  }
  root.add(floors);

  // walls
  const walls = new THREE.Group(); walls.name = 'walls';
  for (const w0 of plan.walls) {
    const w: Wall = opts.cutaway ? { ...w0, height: Math.min(w0.height, opts.cutaway) } : w0;
    const L = len(w.a, w.b);
    if (L < 1e-3) continue;
    const ang = Math.atan2(w.b[1] - w.a[1], w.b[0] - w.a[0]);
    const g = new THREE.Group();
    g.position.set(w.a[0], 0, w.a[1]);
    g.rotation.y = -ang;
    g.name = `wall_${w.id}`;
    const ops = plan.openings.filter((o) => o.wallId === w.id);
    for (const sp of wallSpans(w, ops)) {
      const ext0 = sp.from <= 1e-4 ? w.thickness / 2 : 0;
      const ext1 = sp.to >= L - 1e-4 ? w.thickness / 2 : 0;
      const sl = sp.to - sp.from + ext0 + ext1;
      const geo = boxGeo(sl, sp.top - sp.bottom, w.thickness, false);
      // +y face (index 2) gets the dark "cut" colour so the plan reads clearly from above
      const mesh = new THREE.Mesh(geo, [wallMat, wallMat, capMat, wallMat, wallMat, wallMat]);
      mesh.position.set(sp.from - ext0 + sl / 2, (sp.top + sp.bottom) / 2, 0);
      mesh.castShadow = true; mesh.receiveShadow = true;
      g.add(mesh);
    }
    for (const o of ops) g.add(buildOpening(o, w, L, { frameMat, glassMat, doorMat, cut: opts.cutaway ?? null }));
    walls.add(g);
  }
  root.add(walls);

  // furniture
  const furn = new THREE.Group(); furn.name = 'furniture';
  for (const it of plan.items) {
    const def = FURNITURE[it.type];
    if (!def) continue;
    const g = new THREE.Group();
    g.name = `${def.label}`;
    g.position.set(it.x, 0, it.y);
    g.rotation.y = (-it.rot * Math.PI) / 180;
    for (const p of def.parts) {
      let geo: THREE.BufferGeometry;
      if (p.shape === 'box') geo = boxGeo(p.size[0], p.size[1], p.size[2], p.mat !== 'rug');
      else if (p.shape === 'cyl') geo = new THREE.CylinderGeometry(p.size[0], p.size[2], p.size[1], 28);
      else geo = new THREE.SphereGeometry(p.size[0], 20, 14);
      const mesh = new THREE.Mesh(geo, mat(p.mat));
      mesh.position.set(...p.pos);
      if (p.shape === 'sphere') mesh.scale.set(1, 0.9, 1);
      mesh.castShadow = p.mat !== 'rug' && p.mat !== 'glass';
      mesh.receiveShadow = true;
      g.add(mesh);
    }
    furn.add(g);
  }
  root.add(furn);
  return root;
}

function buildOpening(o: Opening, w: Wall, L: number, m: { frameMat: THREE.Material; glassMat: THREE.Material; doorMat: THREE.Material; cut: number | null }) {
  const g = new THREE.Group();
  g.name = `${o.kind}_${o.id}`;
  const c = o.t * L;
  const top = Math.min(w.height, o.sill + o.height);
  const h = top - o.sill;
  if (h <= 0.02) return g;
  const ft = 0.05;
  const add = (geo: THREE.BufferGeometry, mat: THREE.Material, x: number, y: number, z = 0) => {
    const mesh = new THREE.Mesh(geo, mat); mesh.position.set(x, y, z); mesh.castShadow = mat !== m.glassMat; g.add(mesh); return mesh;
  };
  const depth = w.thickness + 0.01;
  if (o.kind === 'window' || o.kind === 'slider') {
    // frame
    add(boxGeo(o.width, ft, depth, false), m.frameMat, c, o.sill + ft / 2);
    if (!m.cut || top < m.cut) add(boxGeo(o.width, ft, depth, false), m.frameMat, c, top - ft / 2);
    add(boxGeo(ft, h, depth, false), m.frameMat, c - o.width / 2 + ft / 2, o.sill + h / 2);
    add(boxGeo(ft, h, depth, false), m.frameMat, c + o.width / 2 - ft / 2, o.sill + h / 2);
    if (o.width > 1.0) add(boxGeo(ft * 0.8, h, depth * 0.6, false), m.frameMat, c, o.sill + h / 2);
    add(boxGeo(o.width - ft * 2, h - ft * 2, 0.012, false), m.glassMat, c, o.sill + h / 2);
    if (o.kind === 'window' && o.sill > 0.3) add(boxGeo(o.width + 0.08, 0.03, w.thickness + 0.1, false), m.frameMat, c, o.sill - 0.015);
  } else {
    // door frame + leaf opened ~ 80°
    add(boxGeo(ft, h, depth, false), m.frameMat, c - o.width / 2 + ft / 2, h / 2);
    add(boxGeo(ft, h, depth, false), m.frameMat, c + o.width / 2 - ft / 2, h / 2);
    if (!m.cut || top < m.cut) add(boxGeo(o.width, ft, depth, false), m.frameMat, c, top - ft / 2);
    const leafH = Math.min(h - ft, 2.05);
    const leafW = o.width - ft * 2;
    const hinge = new THREE.Group();
    const s = o.flip ? -1 : 1;
    hinge.position.set(c - o.width / 2 + ft, 0, 0);
    hinge.rotation.y = -s * (Math.PI / 180) * 80;
    const leaf = new THREE.Mesh(boxGeo(leafW, leafH, 0.04), m.doorMat);
    leaf.position.set(leafW / 2, leafH / 2, 0);
    leaf.castShadow = true;
    hinge.add(leaf);
    g.add(hinge);
  }
  return g;
}

export function disposeGroup(g: THREE.Object3D) {
  const cached = new Set(geoCache.values());
  g.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.isMesh && !cached.has(mesh.geometry)) mesh.geometry.dispose();
  });
}
