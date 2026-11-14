import * as THREE from 'three';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import type { Plan } from '../types';
import { buildPlan } from './build';
import { SECONDS_PER_ROOM, tourRooms } from './tour';

function three() {
  const t = (window as any).__three;
  if (!t) throw new Error('3D view is not ready');
  return t as { gl: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.Camera; setTour: (t: number | null) => void; orbit: (deg: number) => void };
}

export function download(blob: Blob, name: string) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/** Re-render the current view at `scale`× the on-screen pixel size (e.g. 3 → ~4K from a 1300 px viewport). */
export function renderPNG(scale = 3): string {
  const { gl, scene, camera } = three();
  const prev = gl.getPixelRatio();
  gl.setPixelRatio(scale);
  gl.render(scene, camera);
  const url = gl.domElement.toDataURL('image/png');
  gl.setPixelRatio(prev);
  gl.render(scene, camera);
  return url;
}

export async function exportPNG(plan: Plan, view: string, scale = 3) {
  const url = renderPNG(scale);
  const blob = await (await fetch(url)).blob();
  download(blob, `${slug(plan.name)}-${view}-${scale}x.png`);
}

export async function exportGLB(plan: Plan) {
  const group = buildPlan(plan);
  const exporter = new GLTFExporter();
  const buf = (await exporter.parseAsync(group, { binary: true, onlyVisible: true })) as ArrayBuffer;
  download(new Blob([buf], { type: 'model/gltf-binary' }), `${slug(plan.name)}.glb`);
  return buf.byteLength;
}

export function exportJSON(plan: Plan) {
  download(new Blob([JSON.stringify(plan, null, 2)], { type: 'application/json' }), `${slug(plan.name)}.json`);
}

/** Record the live canvas with MediaRecorder (WebM) while a deterministic camera path plays. */
export function recordVideo(plan: Plan, kind: 'walk' | 'orbit', onDone?: () => void) {
  const { gl, setTour, orbit } = three();
  const stream = (gl.domElement as HTMLCanvasElement).captureStream(30);
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm';
  const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 10e6 });
  const chunks: Blob[] = [];
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec.onstop = () => { setTour(null); download(new Blob(chunks, { type: 'video/webm' }), `${slug(plan.name)}-${kind}.webm`); onDone?.(); };
  const dur = kind === 'walk' ? tourRooms(plan).length * SECONDS_PER_ROOM : 10;
  const t0 = performance.now();
  rec.start();
  const step = () => {
    const t = (performance.now() - t0) / 1000;
    if (kind === 'walk') setTour(Math.min(t, dur - 0.01)); else orbit((t / dur) * 360);
    if (t < dur) requestAnimationFrame(step); else rec.stop();
  };
  requestAnimationFrame(step);
}
