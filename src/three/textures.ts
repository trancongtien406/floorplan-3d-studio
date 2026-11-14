import * as THREE from 'three';
import type { FloorKind } from '../types';

/** Procedural floor textures (canvas) so the app needs no image assets. 1 texture tile = `size` metres. */
const cache = new Map<string, THREE.CanvasTexture>();

function rand(seed: number) {
  let s = seed;
  return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
}

function shade(hex: string, k: number) {
  const c = new THREE.Color(hex);
  c.offsetHSL(0, 0, k);
  return `#${c.getHexString()}`;
}

export const TILE_SIZE: Record<FloorKind, number> = { wood: 2.4, tile: 1.2, carpet: 2, concrete: 3, stone: 1.8 };

export function floorTexture(kind: FloorKind, base: string, alt: string): THREE.CanvasTexture {
  const key = `${kind}${base}${alt}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const N = 512;
  const cv = document.createElement('canvas');
  cv.width = cv.height = N;
  const g = cv.getContext('2d')!;
  const r = rand(kind.length * 977 + base.charCodeAt(2));
  g.fillStyle = base;
  g.fillRect(0, 0, N, N);
  alt = `#${new THREE.Color(base).lerp(new THREE.Color(alt), 0.55).getHexString()}`;
  if (kind === 'wood') {
    const rows = 12; // 2.4 m / 12 = 20 cm planks
    const h = N / rows;
    for (let i = 0; i < rows; i++) {
      let x = -r() * N;
      while (x < N) {
        const w = N * (0.45 + r() * 0.5);
        g.fillStyle = r() > 0.5 ? base : alt;
        g.fillStyle = shade(g.fillStyle as string, (r() - 0.5) * 0.06);
        g.fillRect(x, i * h, w, h);
        g.strokeStyle = shade(alt, -0.07);
        g.globalAlpha = 0.25;
        for (let k = 0; k < 6; k++) { g.beginPath(); const yy = i * h + r() * h; g.moveTo(x, yy); g.bezierCurveTo(x + w / 3, yy + (r() - 0.5) * 6, x + (2 * w) / 3, yy + (r() - 0.5) * 6, x + w, yy); g.stroke(); }
        g.globalAlpha = 1;
        g.fillStyle = shade(alt, -0.18);
        g.fillRect(x, i * h, 1.5, h);
        x += w;
      }
      g.fillStyle = shade(alt, -0.16);
      g.fillRect(0, i * h, N, 1.5);
    }
  } else if (kind === 'tile' || kind === 'stone') {
    const n = kind === 'tile' ? 4 : 3;
    const s = N / n;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      g.fillStyle = shade(r() > 0.5 ? base : alt, (r() - 0.5) * 0.03);
      g.fillRect(i * s, j * s, s, s);
    }
    g.strokeStyle = shade(alt, -0.12);
    g.lineWidth = kind === 'tile' ? 3 : 4;
    for (let i = 0; i <= n; i++) { g.beginPath(); g.moveTo(i * s, 0); g.lineTo(i * s, N); g.stroke(); g.beginPath(); g.moveTo(0, i * s); g.lineTo(N, i * s); g.stroke(); }
  } else {
    const img = g.getImageData(0, 0, N, N);
    const amp = kind === 'carpet' ? 22 : 14;
    for (let i = 0; i < img.data.length; i += 4) {
      const v = (r() - 0.5) * amp;
      img.data[i] += v; img.data[i + 1] += v; img.data[i + 2] += v;
    }
    g.putImageData(img, 0, 0);
  }
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  tex.repeat.set(1 / TILE_SIZE[kind], 1 / TILE_SIZE[kind]);
  cache.set(key, tex);
  return tex;
}
