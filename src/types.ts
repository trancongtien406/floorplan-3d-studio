export type Vec2 = [number, number];

export interface Wall {
  id: string;
  a: Vec2;
  b: Vec2;
  thickness: number; // metres
  height: number; // metres
}

export type OpeningKind = 'door' | 'window' | 'slider';

export interface Opening {
  id: string;
  wallId: string;
  kind: OpeningKind;
  t: number; // centre position along the wall, 0..1
  width: number;
  height: number;
  sill: number; // bottom of the opening above the floor
  flip?: boolean; // door swing side
}

export type FloorKind = 'wood' | 'tile' | 'carpet' | 'concrete' | 'stone';

export interface Room {
  id: string;
  name: string;
  points: Vec2[];
  floor: FloorKind;
}

export interface Item {
  id: string;
  type: string; // key in FURNITURE
  x: number;
  y: number;
  rot: number; // degrees, clockwise in plan
}

export interface Plan {
  id: string;
  name: string;
  subtitle?: string;
  walls: Wall[];
  openings: Opening[];
  rooms: Room[];
  items: Item[];
  style: StyleId;
  background?: { url: string; opacity: number; scale: number; x: number; y: number };
}

export type StyleId = 'modern' | 'scandinavian' | 'japandi' | 'industrial';
