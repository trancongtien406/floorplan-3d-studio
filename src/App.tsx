import { useRef, useState } from 'react';
import Editor2D from './components/Editor2D';
import Scene3D from './components/Scene3D';
import { useStore, type Tool, type View3D } from './store';
import { CATEGORIES, FURNITURE } from './data/furniture';
import { STYLES } from './data/styles';
import { len, planBounds, polygonArea, totalArea, uid, validatePlan } from './geometry';
import { exportGLB, exportJSON, exportPNG, recordVideo } from './three/exporters';
import type { FloorKind, StyleId } from './types';

const TOOLS: { id: Tool; label: string; key: string; icon: string }[] = [
  { id: 'select', label: 'Select / move', key: 'V', icon: 'M5 3l14 8-6 1.5L10 19z' },
  { id: 'wall', label: 'Draw walls', key: 'W', icon: 'M3 20V4h4v12h14v4z' },
  { id: 'door', label: 'Door', key: 'D', icon: 'M5 21V3h10v18M15 12h-2M5 21h14' },
  { id: 'window', label: 'Window', key: 'N', icon: 'M4 5h16v14H4zM12 5v14M4 12h16' },
  { id: 'room', label: 'Room outline', key: 'O', icon: 'M4 4h10l6 6v10H4z' },
  { id: 'erase', label: 'Erase', key: 'E', icon: 'M7 21h10M4 14l8-8 6 6-8 8H6z' },
];
const VIEWS: { id: View3D; label: string }[] = [
  { id: 'top', label: 'Top view' }, { id: 'iso', label: 'Isometric' }, { id: 'dollhouse', label: 'Dollhouse' }, { id: 'walk', label: 'Walkthrough' },
];
const FLOORS: FloorKind[] = ['wood', 'tile', 'carpet', 'concrete', 'stone'];

function Icon({ d }: { d: string }) {
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round"><path d={d} /></svg>;
}

function MiniSymbol({ type, style }: { type: string; style: StyleId }) {
  const def = FURNITURE[type];
  const st = STYLES[style];
  const s = Math.max(def.w, def.d) * 1.15;
  return (
    <svg viewBox={`${-s / 2} ${-s / 2} ${s} ${s}`} width="46" height="46">
      {[...def.parts].sort((a, b) => a.pos[1] + a.size[1] / 2 - (b.pos[1] + b.size[1] / 2)).map((p, i) =>
        p.shape === 'box'
          ? <rect key={i} x={p.pos[0] - p.size[0] / 2} y={p.pos[2] - p.size[2] / 2} width={p.size[0]} height={p.size[2]} rx={0.02} fill={st.mats[p.mat].color} fillOpacity={p.mat === 'glass' ? 0.3 : 0.95} stroke="#384050" strokeOpacity={0.5} strokeWidth={s / 120} />
          : <circle key={i} cx={p.pos[0]} cy={p.pos[2]} r={p.shape === 'sphere' ? p.size[0] : Math.max(p.size[0], p.size[2])} fill={st.mats[p.mat].color} stroke="#384050" strokeOpacity={0.5} strokeWidth={s / 120} />)}
    </svg>
  );
}

function Inspector() {
  const { plan, selection, update, select } = useStore();
  if (!selection) return <p className="muted small">Select a wall, door, window, room or furniture piece to edit it. <b>R</b> rotates, <b>Del</b> deletes, drag to move, scroll to zoom.</p>;
  const num = (v: number, on: (n: number) => void, step = 0.05, min = 0) => (
    <input type="number" step={step} min={min} value={+v.toFixed(2)} onChange={(e) => on(parseFloat(e.target.value) || 0)} />
  );
  if (selection.kind === 'wall') {
    const w = plan.walls.find((x) => x.id === selection.id); if (!w) return null;
    const set = (patch: object) => update((p) => ({ ...p, walls: p.walls.map((x) => x.id === w.id ? { ...x, ...patch } : x) }));
    return <div className="form"><div className="ftitle">Wall · {len(w.a, w.b).toFixed(2)} m</div>
      <label>Thickness (m){num(w.thickness, (v) => set({ thickness: v }), 0.01, 0.05)}</label>
      <label>Height (m){num(w.height, (v) => set({ height: v }), 0.05, 1)}</label></div>;
  }
  if (selection.kind === 'opening') {
    const o = plan.openings.find((x) => x.id === selection.id); if (!o) return null;
    const set = (patch: object) => update((p) => ({ ...p, openings: p.openings.map((x) => x.id === o.id ? { ...x, ...patch } : x) }));
    return <div className="form"><div className="ftitle">{o.kind === 'door' ? 'Door' : o.kind === 'slider' ? 'Sliding door' : 'Window'}</div>
      <label>Type<select value={o.kind} onChange={(e) => set({ kind: e.target.value, sill: e.target.value === 'window' ? 0.9 : 0, height: e.target.value === 'window' ? 1.3 : 2.1 })}><option value="door">Door</option><option value="window">Window</option><option value="slider">Sliding door</option></select></label>
      <label>Width (m){num(o.width, (v) => set({ width: v }))}</label>
      <label>Height (m){num(o.height, (v) => set({ height: v }))}</label>
      {o.kind === 'window' && <label>Sill (m){num(o.sill, (v) => set({ sill: v }))}</label>}
      {o.kind === 'door' && <button className="ghost" onClick={() => set({ flip: !o.flip })}>Flip swing</button>}</div>;
  }
  if (selection.kind === 'room') {
    const r = plan.rooms.find((x) => x.id === selection.id); if (!r) return null;
    const set = (patch: object) => update((p) => ({ ...p, rooms: p.rooms.map((x) => x.id === r.id ? { ...x, ...patch } : x) }));
    return <div className="form"><div className="ftitle">Room · {polygonArea(r.points).toFixed(1)} m²</div>
      <label>Name<input value={r.name} onChange={(e) => set({ name: e.target.value })} /></label>
      <label>Floor<select value={r.floor} onChange={(e) => set({ floor: e.target.value })}>{FLOORS.map((f) => <option key={f}>{f}</option>)}</select></label></div>;
  }
  const it = plan.items.find((x) => x.id === selection.id); if (!it) return null;
  const def = FURNITURE[it.type];
  const set = (patch: object) => update((p) => ({ ...p, items: p.items.map((x) => x.id === it.id ? { ...x, ...patch } : x) }));
  return <div className="form"><div className="ftitle">{def.label} · {def.w.toFixed(2)} × {def.d.toFixed(2)} m</div>
    <label>Rotation (°){num(it.rot, (v) => set({ rot: v }), 15, -360)}</label>
    <div className="row2"><button className="ghost" onClick={() => set({ rot: (it.rot + 90) % 360 })}>Rotate 90°</button>
      <button className="ghost" onClick={() => { update((p) => ({ ...p, items: [...p.items, { ...it, id: uid('it'), x: it.x + 0.3, y: it.y + 0.3 }] })); }}>Duplicate</button>
      <button className="ghost danger" onClick={() => { update((p) => ({ ...p, items: p.items.filter((x) => x.id !== it.id) })); select(null); }}>Delete</button></div></div>;
}

export default function App() {
  const st = useStore();
  const { plan, plans, current, tool, view, layout, cutaway } = st;
  const [busy, setBusy] = useState<string | null>(null);
  const [cat, setCat] = useState<string>('Living');
  const fileRef = useRef<HTMLInputElement>(null);
  const traceRef = useRef<HTMLInputElement>(null);
  const b = planBounds(plan);

  const run = async (label: string, fn: () => Promise<unknown> | void) => {
    setBusy(label);
    try { await fn(); } catch (e) { alert((e as Error).message); } finally { setBusy(null); }
  };

  const importJSON = async (f: File) => {
    try { st.importPlan(validatePlan(JSON.parse(await f.text()))); } catch (e) { alert((e as Error).message); }
  };
  const trace = (f: File) => {
    const url = URL.createObjectURL(f);
    st.update((p) => ({ ...p, background: { url, opacity: 0.45, scale: Math.max(b.w, 8), x: b.minX, y: b.minY } }));
  };

  return (
    <div className="app">
      <header>
        <div className="brand"><div className="logo"><svg viewBox="0 0 24 24" width="18" height="18" fill="#fff"><path d="M3 21V10l9-7 9 7v11h-7v-7h-4v7z" /></svg></div>
          <div><b>Floorplan 3D Studio</b><span>2D plan → furnished 3D</span></div></div>
        <nav className="plans">
          {plans.map((p, i) => <button key={p.id + i} className={i === current ? 'on' : ''} onClick={() => st.loadPlan(i)}>{i === current ? plan.name : p.name}<small>{p.subtitle ?? 'Imported'}</small></button>)}
        </nav>
        <div className="hactions">
          <button className="ghost" title="Undo (Ctrl+Z)" onClick={st.undo} disabled={!st.past.length}>↶</button>
          <button className="ghost" title="Redo (Ctrl+Shift+Z)" onClick={st.redo} disabled={!st.future.length}>↷</button>
          <button className="ghost" onClick={() => fileRef.current?.click()}>Import JSON</button>
          <button className="ghost" onClick={() => traceRef.current?.click()}>Trace image</button>
          <input ref={fileRef} type="file" accept=".json,application/json" hidden onChange={(e) => e.target.files?.[0] && importJSON(e.target.files[0])} />
          <input ref={traceRef} type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && trace(e.target.files[0])} />
        </div>
      </header>

      <aside className="left">
        <h4>Tools</h4>
        <div className="tools">
          {TOOLS.map((t) => <button key={t.id} className={tool === t.id ? 'on' : ''} onClick={() => st.setTool(t.id)} title={`${t.label} (${t.key})`}><Icon d={t.icon} /><span>{t.label}</span></button>)}
        </div>
        <p className="hint">{tool === 'wall' ? 'Click to start, click to add corners, double-click or Esc to finish. Snaps to 10 cm grid and wall ends.'
          : tool === 'room' ? 'Click corners, click the first point (or Enter) to close the room.'
          : tool === 'door' || tool === 'window' ? 'Click on a wall to place it, then drag it along the wall.'
          : tool === 'erase' ? 'Click anything to delete it.' : 'Drag furniture onto the plan. Drag to move, R to rotate.'}</p>
        <h4>Furniture library</h4>
        <div className="cats">{CATEGORIES.map((c) => <button key={c} className={cat === c ? 'on' : ''} onClick={() => setCat(c)}>{c}</button>)}</div>
        <div className="lib">
          {Object.entries(FURNITURE).filter(([, d]) => d.category === cat).map(([k, d]) => (
            <div key={k} className="libitem" draggable onDragStart={(e) => e.dataTransfer.setData('text/furniture', k)}
              onDoubleClick={() => st.update((p) => ({ ...p, items: [...p.items, { id: uid('it'), type: k, x: b.cx, y: b.cy, rot: 0 }] }))} title="Drag onto the plan (or double-click)">
              <MiniSymbol type={k} style={plan.style} /><div><b>{d.label}</b><small>{d.w.toFixed(2)} × {d.d.toFixed(2)} m</small></div>
            </div>))}
        </div>
      </aside>

      <main className={`stage layout-${layout}`}>
        <div className="layoutbar">
          {(['2d', 'split', '3d'] as const).map((l) => <button key={l} className={layout === l ? 'on' : ''} onClick={() => st.setLayout(l)}>{l === '2d' ? '2D plan' : l === '3d' ? '3D' : 'Split'}</button>)}
        </div>
        {layout !== '3d' && <section className="pane pane2d"><Editor2D /><div className="pane-tag">2D plan · {totalArea(plan).toFixed(1)} m²</div></section>}
        {layout !== '2d' && (
          <section className="pane pane3d">
            <Scene3D />
            <div className="viewbar">
              {VIEWS.map((v) => <button key={v.id} className={view === v.id ? 'on' : ''} onClick={() => st.setView(v.id)}>{v.label}</button>)}
              <span className="sep" />
              <button className={cutaway || view === 'iso' ? 'on' : ''} onClick={() => st.toggle('cutaway')} disabled={view === 'walk' || view === 'iso'}>Cutaway walls</button>
            </div>
            {view === 'walk' && <div className="walkhint">Drag to look around · W A S D to walk</div>}
            <div className="pane-tag">{STYLES[plan.style].label} preset · {VIEWS.find((v) => v.id === view)?.label}</div>
          </section>
        )}
      </main>

      <aside className="right">
        <div className="summary">
          <div><small>Total floor area</small><b>{totalArea(plan).toFixed(1)} m²</b></div>
          <div><small>Footprint</small><b>{b.w.toFixed(1)} × {b.h.toFixed(1)} m</b></div>
          <div><small>Rooms</small><b>{plan.rooms.length}</b></div>
          <div><small>Furniture</small><b>{plan.items.length}</b></div>
        </div>
        <h4>Style presets</h4>
        <div className="styles">
          {Object.values(STYLES).map((s) => (
            <button key={s.id} className={plan.style === s.id ? 'on' : ''} onClick={() => st.setStyle(s.id)}>
              <div className="sw">{s.swatch.map((c) => <i key={c} style={{ background: c }} />)}</div>
              <b>{s.label}</b><small>{s.blurb}</small>
            </button>))}
        </div>
        <p className="muted tiny">Presets are deterministic material &amp; colour palettes, not generative AI.</p>
        <h4>Inspector</h4>
        <Inspector />
        <h4>Rooms</h4>
        <div className="rooms">{plan.rooms.map((r) => <div key={r.id} onClick={() => st.select({ kind: 'room', id: r.id })}><span>{r.name}</span><small>{r.floor}</small><b>{polygonArea(r.points).toFixed(1)} m²</b></div>)}</div>
        <h4>Export</h4>
        <div className="exports">
          <button disabled={layout === '2d' || !!busy} onClick={() => run('png', () => exportPNG(plan, view, 2))}>PNG render · 2×</button>
          <button disabled={layout === '2d' || !!busy} onClick={() => run('png4', () => exportPNG(plan, view, 4))}>PNG render · 4×</button>
          <button disabled={!!busy} onClick={() => run('glb', () => exportGLB(plan))}>GLB 3D model</button>
          <button disabled={!!busy} onClick={() => exportJSON(plan)}>Plan JSON</button>
          <button disabled={layout === '2d' || !!busy} onClick={() => { st.setView('walk'); setBusy('walk'); setTimeout(() => recordVideo(plan, 'walk', () => setBusy(null)), 400); }}>Walkthrough video</button>
          <button disabled={layout === '2d' || !!busy} onClick={() => { st.setView('dollhouse'); setBusy('orbit'); setTimeout(() => recordVideo(plan, 'orbit', () => setBusy(null)), 400); }}>360° orbit video</button>
        </div>
        {busy && <p className="muted small">Working… ({busy})</p>}
        {plan.background && <>
          <h4>Tracing image</h4>
          <label className="slider">Opacity<input type="range" min={0} max={1} step={0.05} value={plan.background.opacity} onChange={(e) => st.update((p) => ({ ...p, background: { ...p.background!, opacity: +e.target.value } }), false)} /></label>
          <label className="slider">Width (m)<input type="range" min={2} max={40} step={0.1} value={plan.background.scale} onChange={(e) => st.update((p) => ({ ...p, background: { ...p.background!, scale: +e.target.value } }), false)} /></label>
          <button className="ghost" onClick={() => st.update((p) => ({ ...p, background: undefined }))}>Remove tracing image</button>
        </>}
        <footer>Demo plans are sample layouts · Built by Tran Cong Tien · fiverr.com/optimus2003</footer>
      </aside>
    </div>
  );
}
