import type { Item, Opening, Plan, Room, Vec2, Wall } from '../types';
import { rectWalls } from '../geometry';

/** Three demo plans (sample layouts drawn for this portfolio project, not client work). */
const W = (id: string, a: Vec2, b: Vec2, t = 0.12, h = 2.7): Wall => ({ id, a, b, thickness: t, height: h });
const door = (id: string, wallId: string, t: number, width = 0.85, flip = false): Opening => ({ id, wallId, kind: 'door', t, width, height: 2.1, sill: 0, flip });
const win = (id: string, wallId: string, t: number, width = 1.4, sill = 0.9, height = 1.35): Opening => ({ id, wallId, kind: 'window', t, width, height, sill });
const slider = (id: string, wallId: string, t: number, width = 2.4): Opening => ({ id, wallId, kind: 'slider', t, width, height: 2.25, sill: 0 });
const R = (id: string, name: string, floor: Room['floor'], ...points: Vec2[]): Room => ({ id, name, floor, points });
let n = 0;
const I = (type: string, x: number, y: number, rot = 0): Item => ({ id: `it${++n}`, type, x, y, rot });

export const studio: Plan = {
  id: 'studio', name: 'Studio apartment', subtitle: '7.0 × 5.6 m · 1 room + bath', style: 'scandinavian',
  walls: [...rectWalls(0, 0, 7, 5.6, 0.2, 2.7, 's'), W('s4', [4.8, 0], [4.8, 2.4]), W('s5', [4.8, 2.4], [7, 2.4])],
  openings: [
    win('o1', 's0', 0.25, 1.6, 0.8, 1.45), win('o2', 's3', 0.42, 1.4), win('o3', 's1', 0.2, 0.6, 1.45, 0.65),
    door('o4', 's1', 0.857, 0.95), door('o5', 's5', 0.32, 0.8),
  ],
  rooms: [
    R('r1', 'Living / sleeping', 'wood', [0, 0], [4.8, 0], [4.8, 2.4], [7, 2.4], [7, 5.6], [0, 5.6]),
    R('r2', 'Bath', 'tile', [4.8, 0], [7, 0], [7, 2.4], [4.8, 2.4]),
  ],
  items: [
    I('bedDouble', 1.25, 1.17), I('nightstand', 2.42, 0.34), I('nightstand', 0.08 + 0.26, 2.45, -90),
    I('wardrobe', 0.41, 3.35, -90), I('tv', 2.3, 2.95), I('rug', 2.4, 4.25), I('sofa2', 2.4, 5.04, 180), I('coffee', 2.4, 4.05),
    I('floorLamp', 3.6, 5.22), I('plant', 0.45, 5.12), I('kitchenShort', 5.9, 5.19, 180), I('bistro', 5.85, 3.55),
    I('shower', 6.45, 0.55), I('toilet', 6.56, 1.75, 90), I('vanity', 5.4, 0.34),
  ],
};

export const twoBed: Plan = {
  id: 'twobed', name: '2-bedroom apartment', subtitle: '10 × 8 m · 2 bed · open living', style: 'modern',
  walls: [
    ...rectWalls(0, 0, 10, 8, 0.2, 2.7, 'a'),
    W('a4', [0, 4], [4, 4]), W('a5', [6, 4], [10, 4]), W('a6', [4, 0], [4, 4]), W('a7', [6, 0], [6, 4]), W('a8', [4, 2.6], [6, 2.6]),
  ],
  openings: [
    door('b1', 'a6', 0.83), door('b2', 'a7', 0.83, 0.85, true), door('b3', 'a8', 0.5, 0.8),
    win('b4', 'a0', 0.2, 1.6), win('b5', 'a0', 0.8, 1.6), win('b6', 'a0', 0.5, 0.6, 1.5, 0.6),
    slider('b7', 'a2', 0.75, 2.6), win('b8', 'a3', 0.37, 1.2), door('b9', 'a1', 0.625, 0.95),
  ],
  rooms: [
    R('q1', 'Bedroom 1', 'wood', [0, 0], [4, 0], [4, 4], [0, 4]),
    R('q2', 'Bath', 'tile', [4, 0], [6, 0], [6, 2.6], [4, 2.6]),
    R('q3', 'Bedroom 2', 'carpet', [6, 0], [10, 0], [10, 4], [6, 4]),
    R('q4', 'Hall', 'wood', [4, 2.6], [6, 2.6], [6, 4], [4, 4]),
    R('q5', 'Living & dining', 'wood', [0, 4], [7, 4], [7, 8], [0, 8]),
    R('q6', 'Kitchen', 'tile', [7, 4], [10, 4], [10, 8], [7, 8]),
  ],
  items: [
    I('bedDouble', 2.0, 1.17), I('nightstand', 0.86, 0.34), I('nightstand', 3.14, 0.34), I('wardrobe', 1.3, 3.6, 180), I('plant', 3.5, 3.45),
    I('bedSingle', 9.35, 1.14), I('desk', 7.3, 0.46), I('officeChair', 7.3, 1.1, 180), I('wardrobe', 8.5, 3.6, 180), I('bookshelf', 6.25, 1.9, -90),
    I('bathtub', 5.0, 0.48), I('toilet', 5.6, 1.85, 90), I('vanity', 4.3, 1.75, -90),
    I('tv', 0.32, 6.3, -90), I('rug', 1.75, 6.3, 90), I('sofa3', 2.85, 6.3, 90), I('coffee', 1.65, 6.3, 90), I('armchair', 1.6, 4.62),
    I('floorLamp', 2.95, 7.55), I('plant', 0.45, 7.55), I('dining6', 5.0, 6.1, 90),
    I('kitchen', 8.4, 7.59, 180), I('island', 8.05, 6.0), I('fridge', 9.56, 6.0, 90),
  ],
};

export const townhouse: Plan = {
  id: 'townhouse', name: 'Townhouse · ground floor', subtitle: '7 × 12 m · living, kitchen-dining, WC, stairs', style: 'japandi',
  walls: [
    ...rectWalls(0, 0, 7, 12, 0.2, 2.9, 't'),
    W('t4', [5.2, 4.5], [7, 4.5], 0.12, 2.9), W('t5', [5.2, 4.5], [5.2, 7.5], 0.12, 2.9), W('t6', [5.2, 7.5], [7, 7.5], 0.12, 2.9),
    W('t7', [0, 7.5], [3.4, 7.5], 0.12, 2.9), W('t8', [0, 4.5], [3.4, 4.5], 0.12, 2.9),
  ],
  openings: [
    slider('u1', 't0', 0.5, 3.0), door('u2', 't2', 0.143, 1.0), win('u3', 't2', 0.443, 2.0, 0.6, 1.6),
    door('u4', 't5', 0.77, 0.8), win('u5', 't1', 0.458, 0.6, 1.5, 0.6), win('u6', 't1', 0.125, 1.2, 1.0, 1.1), win('u7', 't3', 0.183, 1.4),
  ],
  rooms: [
    R('v1', 'Kitchen & dining', 'wood', [0, 0], [7, 0], [7, 4.5], [0, 4.5]),
    R('v2', 'Hall & stairs', 'stone', [0, 4.5], [5.2, 4.5], [5.2, 7.5], [0, 7.5]),
    R('v3', 'WC & laundry', 'tile', [5.2, 4.5], [7, 4.5], [7, 7.5], [5.2, 7.5]),
    R('v4', 'Living room', 'wood', [0, 7.5], [7, 7.5], [7, 12], [0, 12]),
  ],
  items: [
    I('kitchen', 0.41, 2.4, -90), I('fridge', 0.44, 0.48, -90), I('island', 2.5, 2.4, 90), I('dining6', 5.0, 2.3), I('plant', 6.5, 0.5),
    I('stairs', 0.65, 6.0), I('dresser', 2.4, 4.81), I('plant', 4.7, 7.05),
    I('toilet', 6.56, 5.3, 90), I('vanity', 6.66, 6.5, 90), I('washer', 5.65, 4.9),
    I('sofa3', 1.55, 8.03), I('tv', 1.55, 11.69, 180), I('rug', 1.7, 9.75), I('coffee', 1.55, 9.6), I('armchair', 3.35, 9.6, 90),
    I('floorLamp', 0.35, 9.0), I('bookshelf', 6.72, 9.3, 90), I('plant', 0.45, 11.5),
  ],
};

export const DEMO_PLANS: Plan[] = [studio, twoBed, townhouse];
