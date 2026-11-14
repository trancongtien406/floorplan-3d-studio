import type { FloorKind, StyleId } from '../types';
import type { Mat } from './furniture';

/** Deterministic style presets: each one swaps the wall paint, floor finishes and the furniture palette.
 *  (This is a rule-based restyle, not a generative AI model.) */
export interface StyleDef {
  id: StyleId;
  label: string;
  blurb: string;
  wall: string;
  wallTop: string; // cut colour on top of walls in top / dollhouse views
  floors: Record<FloorKind, { base: string; alt: string }>;
  mats: Record<Mat, { color: string; roughness?: number; metalness?: number; emissive?: string; opacity?: number }>;
  sun: string;
  ambient: number;
  swatch: string[];
}

const common = {
  glass: { color: '#cfe8f0', roughness: 0.05, opacity: 0.35 },
  screen: { color: '#15171c', roughness: 0.25 },
  plant: { color: '#3f7d4a', roughness: 0.9 },
  ceramic: { color: '#f5f6f7', roughness: 0.2 },
  lamp: { color: '#fff4d6', roughness: 0.6, emissive: '#5a4a24' },
};

export const STYLES: Record<StyleId, StyleDef> = {
  modern: {
    id: 'modern', label: 'Modern', blurb: 'Warm greys, walnut, brass accents', wall: '#ecebe8', wallTop: '#2b2d33',
    floors: { wood: { base: '#b08a64', alt: '#9c7754' }, tile: { base: '#d9dadc', alt: '#c9cacd' }, carpet: { base: '#c8c2b8', alt: '#bdb6ab' }, concrete: { base: '#bdbcb8', alt: '#b2b1ad' }, stone: { base: '#d6d0c6', alt: '#c7c0b4' } },
    mats: { ...common, fabric: { color: '#6b6f78' }, fabric2: { color: '#3d4047' }, wood: { color: '#7a5235', roughness: 0.55 }, woodDark: { color: '#3b2a20' }, metal: { color: '#b89a5e', metalness: 0.7, roughness: 0.35 }, accent: { color: '#c8693f' }, white: { color: '#f2f1ee', roughness: 0.4 }, pot: { color: '#e8e4dc' }, rug: { color: '#cfc6b8', roughness: 1 }, mattress: { color: '#f4f2ee' }, pillow: { color: '#e9e2d6' }, counter: { color: '#2f3136', roughness: 0.3 }, book: { color: '#9a6b4f' } },
    sun: '#fff1de', ambient: 0.7, swatch: ['#ecebe8', '#6b6f78', '#7a5235', '#c8693f', '#b89a5e'],
  },
  scandinavian: {
    id: 'scandinavian', label: 'Scandinavian', blurb: 'White walls, pale oak, soft textiles', wall: '#f7f6f2', wallTop: '#3a3f47',
    floors: { wood: { base: '#dcc4a0', alt: '#d1b78f' }, tile: { base: '#eceae6', alt: '#e1dfda' }, carpet: { base: '#e4ded3', alt: '#dbd4c8' }, concrete: { base: '#d7d6d2', alt: '#cdccc8' }, stone: { base: '#e6e1d8', alt: '#dcd6cb' } },
    mats: { ...common, fabric: { color: '#c9ccd1' }, fabric2: { color: '#8e9aa6' }, wood: { color: '#d2b48a', roughness: 0.6 }, woodDark: { color: '#b8956a' }, metal: { color: '#2d2f33', metalness: 0.3, roughness: 0.5 }, accent: { color: '#7fa3b8' }, white: { color: '#fbfbf9', roughness: 0.5 }, pot: { color: '#f2efe9' }, rug: { color: '#efebe4', roughness: 1 }, mattress: { color: '#ffffff' }, pillow: { color: '#dfe6ec' }, counter: { color: '#f0eeea', roughness: 0.3 }, book: { color: '#c7b49a' } },
    sun: '#fffaf0', ambient: 0.8, swatch: ['#f7f6f2', '#c9ccd1', '#d2b48a', '#7fa3b8', '#2d2f33'],
  },
  japandi: {
    id: 'japandi', label: 'Japandi', blurb: 'Clay & sand tones, ash wood, low lines', wall: '#ede6db', wallTop: '#3b342d',
    floors: { wood: { base: '#c9a77e', alt: '#bd9a70' }, tile: { base: '#d8cfc2', alt: '#ccc2b4' }, carpet: { base: '#d3c6b2', alt: '#c8baa5' }, concrete: { base: '#c9c1b5', alt: '#bfb7aa' }, stone: { base: '#cfc4b3', alt: '#c3b7a5' } },
    mats: { ...common, fabric: { color: '#b9a88f' }, fabric2: { color: '#6e6255' }, wood: { color: '#a98058', roughness: 0.65 }, woodDark: { color: '#4a3a2c' }, metal: { color: '#3a3530', metalness: 0.2, roughness: 0.6 }, accent: { color: '#7d8a6a' }, white: { color: '#efe9df', roughness: 0.6 }, pot: { color: '#8c6f55' }, rug: { color: '#d9ccb8', roughness: 1 }, mattress: { color: '#f1ece3' }, pillow: { color: '#c9b9a0' }, counter: { color: '#d8cfc2', roughness: 0.4 }, book: { color: '#8a7058' } },
    sun: '#fff0dc', ambient: 0.72, swatch: ['#ede6db', '#b9a88f', '#a98058', '#7d8a6a', '#4a3a2c'],
  },
  industrial: {
    id: 'industrial', label: 'Industrial', blurb: 'Concrete, black steel, leather & brick', wall: '#d9d4cf', wallTop: '#1f2023',
    floors: { wood: { base: '#7d5a3f', alt: '#6e4f37' }, tile: { base: '#9a9894', alt: '#8c8a86' }, carpet: { base: '#8f8780', alt: '#857d76' }, concrete: { base: '#a3a19d', alt: '#999793' }, stone: { base: '#9b948b', alt: '#8f887f' } },
    mats: { ...common, fabric: { color: '#7b4a2e', roughness: 0.5 }, fabric2: { color: '#2c2d30' }, wood: { color: '#5e4330', roughness: 0.7 }, woodDark: { color: '#1e1e20', metalness: 0.4 }, metal: { color: '#26272a', metalness: 0.6, roughness: 0.45 }, accent: { color: '#b5543a' }, white: { color: '#cfcac4', roughness: 0.6 }, pot: { color: '#4a4b4e' }, rug: { color: '#6f655d', roughness: 1 }, mattress: { color: '#e6e1da' }, pillow: { color: '#9a8f84' }, counter: { color: '#6d6c69', roughness: 0.5 }, book: { color: '#6b4a35' } },
    sun: '#ffe6c8', ambient: 0.65, swatch: ['#d9d4cf', '#7b4a2e', '#5e4330', '#b5543a', '#26272a'],
  },
};
