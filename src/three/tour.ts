import * as THREE from 'three';
import { centroid, polygonArea } from '../geometry';
import type { Plan } from '../types';
import { FURNITURE } from '../data/furniture';

export const SECONDS_PER_ROOM = 3.6;

export function tourRooms(plan: Plan) {
  const big = plan.rooms.filter((r) => r.points.length >= 3 && polygonArea(r.points) >= 7);
  return big.length ? big : plan.rooms;
}

/** Deterministic walkthrough: for each room, stand near one corner at eye height and slowly dolly + pan toward the
 *  opposite corner. Used both for the live "Play walkthrough" button and for frame-exact video export. */
export function tourPose(plan: Plan, t: number) {
  // small rooms (bath, WC, hall < 7 m²) make poor eye-level shots; the tour visits the main rooms
  const big = plan.rooms.filter((r) => r.points.length >= 3 && polygonArea(r.points) >= 7);
  const rooms = big.length ? big : plan.rooms;
  const total = rooms.length * SECONDS_PER_ROOM;
  const tt = ((t % total) + total) % total;
  const i = Math.min(rooms.length - 1, Math.floor(tt / SECONDS_PER_ROOM));
  const u = (tt - i * SECONDS_PER_ROOM) / SECONDS_PER_ROOM;
  const e = u * u * (3 - 2 * u);
  const r = rooms[i];
  const xs = r.points.map((p) => p[0]), ys = r.points.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const c = centroid(r.points);
  // pick the corner whose standing spot is farthest from furniture, then look toward the opposite corner
  const ins = 0.45;
  const corners: [number, number][] = [[minX + ins, minY + ins], [maxX - ins, minY + ins], [maxX - ins, maxY - ins], [minX + ins, maxY - ins]];
  const stand = (k: [number, number]): [number, number] => [k[0] * 0.75 + c[0] * 0.25, k[1] * 0.75 + c[1] * 0.25];
  const clearance = (p: [number, number]) => plan.items.filter((it) => !it.type.startsWith('rug'))
    .reduce((m, it) => Math.min(m, Math.hypot(it.x - p[0], it.y - p[1]) - Math.max(FURNITURE[it.type]?.w ?? 0, FURNITURE[it.type]?.d ?? 0) / 2), 99);
  let ci = 0;
  corners.forEach((k, j) => { if (clearance(stand(k)) > clearance(stand(corners[ci])) + 0.05) ci = j; });
  const corner = corners[ci];
  const opp = corners[(ci + 2) % 4];
  const s0 = stand(corner);
  const start = new THREE.Vector3(s0[0], 1.55, s0[1]);
  const end = new THREE.Vector3(corner[0] * 0.5 + c[0] * 0.5, 1.5, corner[1] * 0.5 + c[1] * 0.5);
  const pos = start.lerp(end, e);
  const far = new THREE.Vector3(opp[0], 0.9, opp[1]);
  const look = far.clone();
  const side = new THREE.Vector3(c[0], 0.9, c[1]);
  look.lerp(side, 0.35 - 0.35 * e);
  return { pos, look, room: r.name, total };
}
