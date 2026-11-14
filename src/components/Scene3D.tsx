import { useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { useStore, type View3D } from '../store';
import { STYLES } from '../data/styles';
import { buildPlan, disposeGroup } from '../three/build';
import { planBounds } from '../geometry';
import type { Plan } from '../types';
import { SECONDS_PER_ROOM, tourPose, tourRooms } from '../three/tour';

function Environment() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = env;
    (scene as any).environmentIntensity = 0.55;
    return () => { env.dispose(); pmrem.dispose(); };
  }, [gl, scene]);
  return null;
}

function PlanModel({ plan, cutaway }: { plan: Plan; cutaway: number | null }) {
  const group = useMemo(() => buildPlan(plan, { cutaway }), [plan, cutaway]);
  useEffect(() => () => disposeGroup(group), [group]);
  return <primitive object={group} />;
}

function Lights({ plan }: { plan: Plan }) {
  const b = planBounds(plan);
  const style = STYLES[plan.style];
  const ref = useRef<THREE.DirectionalLight>(null);
  const size = Math.max(b.w, b.h) * 0.75 + 2;
  useEffect(() => {
    const l = ref.current; if (!l) return;
    l.target.position.set(b.cx, 0, b.cy); l.target.updateMatrixWorld();
    const cam = l.shadow.camera as THREE.OrthographicCamera;
    cam.left = -size; cam.right = size; cam.top = size; cam.bottom = -size; cam.near = 0.5; cam.far = 60; cam.updateProjectionMatrix();
  }, [b.cx, b.cy, size]);
  return (
    <>
      <hemisphereLight args={['#ffffff', '#d8d2c8', style.ambient]} />
      <directionalLight ref={ref} position={[b.cx - 6, 14, b.cy + 9]} intensity={2.1} color={style.sun} castShadow
        shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004} shadow-normalBias={0.02} />
      <directionalLight position={[b.cx + 8, 10, b.cy - 6]} intensity={0.45} color="#e6eeff" />
    </>
  );
}

/** Camera position that frames the whole plan (bounding circle radius r) for the given aspect. */
function dollhousePos(b: { cx: number; cy: number }, r: number, aspect: number, deg: number) {
  const vHalf = (40 / 2) * (Math.PI / 180);
  const hHalf = Math.atan(Math.tan(vHalf) * aspect);
  const d = (r / Math.sin(Math.min(vHalf, hHalf))) * 1.12;
  const elev = 0.82; // ~47° above the horizon
  const az = Math.atan2(0.55, 1.05) + (deg * Math.PI) / 180;
  return new THREE.Vector3(b.cx + Math.sin(az) * Math.cos(elev) * d, Math.sin(elev) * d, b.cy + Math.cos(az) * Math.cos(elev) * d);
}

/** Puts the right camera in place for each render mode and exposes a capture API for exports. */
function CameraRig({ plan, view }: { plan: Plan; view: View3D }) {
  const { camera, gl, scene, size, set, invalidate } = useThree();
  const controls = useRef<any>(null);
  const walk = useRef({ yaw: 0, pitch: -0.08, pos: new THREE.Vector3(), keys: new Set<string>() });
  const b = planBounds(plan);
  const persp = useMemo(() => new THREE.PerspectiveCamera(45, 1, 0.05, 200), []);
  const ortho = useMemo(() => new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 200), []);

  useEffect(() => {
    const aspect = size.width / Math.max(1, size.height);
    const span = Math.max(b.w, b.h) + 2.2;
    const r = 0.5 * Math.hypot(b.w, b.h) + 0.4;
    if (view === 'top' || view === 'iso') {
      const half = view === 'top' ? Math.max((b.w + 1.8) / aspect, b.h + 2.8) / 2 : (r * 0.92) / Math.min(1, aspect);
      ortho.left = -half * aspect; ortho.right = half * aspect; ortho.top = half; ortho.bottom = -half;
      ortho.zoom = 1;
      if (view === 'top') { ortho.position.set(b.cx, 30, b.cy + 0.0001); ortho.up.set(0, 0, -1); }
      else { ortho.position.set(b.cx + span, span * 0.95, b.cy + span); ortho.up.set(0, 1, 0); }
      ortho.lookAt(b.cx, 0, b.cy);
      ortho.updateProjectionMatrix();
      set({ camera: ortho });
    } else {
      persp.aspect = aspect;
      persp.fov = view === 'walk' ? 70 : 40;
      persp.updateProjectionMatrix();
      if (view === 'dollhouse') {
        const p = dollhousePos(b, r, aspect, 0);
        persp.position.copy(p);
        persp.lookAt(b.cx, 0, b.cy);
      } else {
        const idx = Math.max(0, tourRooms(plan).findIndex((x) => /living/i.test(x.name)));
        const pose = tourPose(plan, idx * SECONDS_PER_ROOM + 0.2);
        walk.current.pos.copy(pose.pos);
        const dir = pose.look.clone().sub(pose.pos);
        walk.current.yaw = Math.atan2(-dir.x, -dir.z);
        walk.current.pitch = Math.atan2(dir.y, Math.hypot(dir.x, dir.z));
      }
      set({ camera: persp });
    }
    if (controls.current) { controls.current.target.set(b.cx, 0, b.cy); controls.current.update(); }
  }, [view, plan.id, size.width, size.height]); // eslint-disable-line react-hooks/exhaustive-deps

  // walkthrough: drag to look, WASD / arrows to move
  useEffect(() => {
    if (view !== 'walk') return;
    const el = gl.domElement;
    let down = false, lx = 0, ly = 0;
    const pd = (e: PointerEvent) => { down = true; lx = e.clientX; ly = e.clientY; };
    const pu = () => { down = false; };
    let raf = 0;
    const loop = () => { invalidate(); raf = walk.current.keys.size ? requestAnimationFrame(loop) : 0; };
    const pm = (e: PointerEvent) => {
      if (!down) return;
      invalidate();
      walk.current.yaw -= (e.clientX - lx) * 0.004; walk.current.pitch = Math.max(-0.9, Math.min(0.6, walk.current.pitch - (e.clientY - ly) * 0.003));
      lx = e.clientX; ly = e.clientY;
    };
    const kd = (e: KeyboardEvent) => { walk.current.keys.add(e.key.toLowerCase()); if (!raf) loop(); };
    const ku = (e: KeyboardEvent) => walk.current.keys.delete(e.key.toLowerCase());
    el.addEventListener('pointerdown', pd); window.addEventListener('pointerup', pu); el.addEventListener('pointermove', pm);
    window.addEventListener('keydown', kd); window.addEventListener('keyup', ku);
    return () => { el.removeEventListener('pointerdown', pd); window.removeEventListener('pointerup', pu); el.removeEventListener('pointermove', pm); window.removeEventListener('keydown', kd); window.removeEventListener('keyup', ku); cancelAnimationFrame(raf); };
  }, [view, gl, invalidate]);

  const tourT = useRef<number | null>(null);
  useFrame((_, dt0) => {
    if (view !== 'walk') return;
    const dt = Math.min(dt0, 0.05);
    const w = walk.current;
    if (tourT.current !== null) {
      const pose = tourPose(plan, tourT.current);
      persp.position.copy(pose.pos); persp.lookAt(pose.look);
      return;
    }
    const k = w.keys, sp = 2.2 * dt;
    const fwd = new THREE.Vector3(-Math.sin(w.yaw), 0, -Math.cos(w.yaw));
    const right = new THREE.Vector3(-fwd.z, 0, fwd.x);
    if (k.has('w') || k.has('arrowup')) w.pos.addScaledVector(fwd, sp);
    if (k.has('s') || k.has('arrowdown')) w.pos.addScaledVector(fwd, -sp);
    if (k.has('a') || k.has('arrowleft')) w.pos.addScaledVector(right, -sp);
    if (k.has('d') || k.has('arrowright')) w.pos.addScaledVector(right, sp);
    persp.position.copy(w.pos);
    persp.rotation.set(w.pitch, w.yaw, 0, 'YXZ');
  });

  // capture API used by the export buttons and by the screenshot / video scripts
  useEffect(() => {
    (window as any).__three = {
      gl, scene,
      camera,
      tourLength: () => tourRooms(plan).length * SECONDS_PER_ROOM,
      setTour(t: number | null) { tourT.current = t; invalidate(); },
      invalidate,
      orbit(deg: number) {
        if (view !== 'dollhouse') return;
        const r = 0.5 * Math.hypot(b.w, b.h) + 0.4;
        persp.position.copy(dollhousePos(b, r, persp.aspect, deg));
        persp.lookAt(b.cx, 0, b.cy);
        if (controls.current) { controls.current.target.set(b.cx, 0, b.cy); controls.current.update(); }
        invalidate();
      },
    };
  });
  return view === 'walk' ? null : <OrbitControls ref={controls} makeDefault enableRotate={view !== 'top'} enableDamping={false} target={[b.cx, 0, b.cy]} maxPolarAngle={Math.PI / 2.05} />;
}

function Ground({ plan }: { plan: Plan }) {
  const b = planBounds(plan);
  return (
    <mesh rotation-x={-Math.PI / 2} position={[b.cx, -0.01, b.cy]} receiveShadow>
      <planeGeometry args={[200, 200]} />
      <meshStandardMaterial color="#d9d5cc" roughness={1} />
    </mesh>
  );
}

export default function Scene3D() {
  const { plan, view, cutaway } = useStore();
  const cut = view === 'walk' ? null : cutaway || view === 'iso' ? 1.15 : null;
  return (
    <Canvas shadows gl={{ preserveDrawingBuffer: true, antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.05 }}
      frameloop="demand" dpr={[1, 2]} data-testid="scene3d" className="scene3d">
      <color attach="background" args={['#e6e3dc']} />
      <fog attach="fog" args={['#e6e3dc', 35, 80]} />
      <Environment />
      <Lights plan={plan} />
      <Ground plan={plan} />
      <PlanModel plan={plan} cutaway={cut} />
      <CameraRig plan={plan} view={view} />
    </Canvas>
  );
}
