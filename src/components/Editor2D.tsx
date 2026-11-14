import { useEffect, useMemo, useRef, useState } from 'react';
import { useStore } from '../store';
import { FURNITURE } from '../data/furniture';
import { STYLES } from '../data/styles';
import { centroid, len, nearestWall, planBounds, polygonArea, projectOnSegment, snap, uid } from '../geometry';
import type { Item, Opening, Plan, Vec2, Wall } from '../types';

const SNAP = 0.1;

function svgPoint(svg: SVGSVGElement, cx: number, cy: number): Vec2 {
  const pt = svg.createSVGPoint();
  pt.x = cx; pt.y = cy;
  const m = svg.getScreenCTM();
  if (!m) return [0, 0];
  const r = pt.matrixTransform(m.inverse());
  return [r.x, r.y];
}

function snapToEndpoints(p: Vec2, plan: Plan, r = 0.25): Vec2 {
  let best: Vec2 | null = null, bd = r;
  for (const w of plan.walls) for (const e of [w.a, w.b]) { const d = len(p, e); if (d < bd) { bd = d; best = e; } }
  return best ? [best[0], best[1]] : [snap(p[0], SNAP), snap(p[1], SNAP)];
}

function ItemSymbol({ item, style, selected }: { item: Item; style: string; selected: boolean }) {
  const def = FURNITURE[item.type];
  const st = STYLES[style as keyof typeof STYLES];
  if (!def) return null;
  const parts = [...def.parts].sort((a, b) => (a.pos[1] + a.size[1] / 2) - (b.pos[1] + b.size[1] / 2));
  return (
    <g transform={`translate(${item.x} ${item.y}) rotate(${item.rot})`} className="item">
      <rect x={-def.w / 2} y={-def.d / 2} width={def.w} height={def.d} fill="transparent" />
      {parts.map((p, i) => {
        const c = st.mats[p.mat]?.color ?? '#999';
        const common = { fill: c, fillOpacity: p.mat === 'glass' ? 0.25 : p.mat === 'rug' ? 0.55 : 0.92, stroke: '#3b3f48', strokeWidth: 0.012, strokeOpacity: 0.55 };
        if (p.shape === 'box') return <rect key={i} x={p.pos[0] - p.size[0] / 2} y={p.pos[2] - p.size[2] / 2} width={p.size[0]} height={p.size[2]} rx={0.02} {...common} />;
        const r = p.shape === 'sphere' ? p.size[0] : Math.max(p.size[0], p.size[2]);
        return <circle key={i} cx={p.pos[0]} cy={p.pos[2]} r={r} {...common} />;
      })}
      {selected && <rect x={-def.w / 2 - 0.05} y={-def.d / 2 - 0.05} width={def.w + 0.1} height={def.d + 0.1} fill="none" stroke="#0d9488" strokeWidth={0.03} strokeDasharray="0.08 0.05" />}
    </g>
  );
}

function OpeningSymbol({ o, wall, selected }: { o: Opening; wall: Wall; selected: boolean }) {
  const L = len(wall.a, wall.b);
  const ang = (Math.atan2(wall.b[1] - wall.a[1], wall.b[0] - wall.a[0]) * 180) / Math.PI;
  const cx = wall.a[0] + (wall.b[0] - wall.a[0]) * o.t, cy = wall.a[1] + (wall.b[1] - wall.a[1]) * o.t;
  const w = o.width, t = wall.thickness + 0.02;
  if (L <= 0) return null;
  const hl = selected ? '#0d9488' : '#1f2937';
  return (
    <g transform={`translate(${cx} ${cy}) rotate(${ang})`} className="opening">
      <rect x={-w / 2} y={-t / 2} width={w} height={t} fill="#fbfaf8" />
      {o.kind === 'window' && <>
        <rect x={-w / 2} y={-t / 2} width={w} height={t} fill="#e0f2fe" stroke={hl} strokeWidth={0.015} />
        <line x1={-w / 2} x2={w / 2} y1={0} y2={0} stroke={hl} strokeWidth={0.015} />
      </>}
      {o.kind === 'slider' && <>
        <line x1={-w / 2} x2={0.05} y1={-0.03} y2={-0.03} stroke={hl} strokeWidth={0.025} />
        <line x1={-0.05} x2={w / 2} y1={0.03} y2={0.03} stroke={hl} strokeWidth={0.025} />
      </>}
      {o.kind === 'door' && (() => {
        const s = o.flip ? -1 : 1;
        return <>
          <line x1={-w / 2} y1={0} x2={-w / 2} y2={s * w} stroke={hl} strokeWidth={0.03} />
          <path d={`M ${-w / 2} ${s * w} A ${w} ${w} 0 0 ${s > 0 ? 0 : 1} ${w / 2} 0`} fill="none" stroke={hl} strokeWidth={0.012} strokeDasharray="0.05 0.03" />
        </>;
      })()}
    </g>
  );
}

export default function Editor2D() {
  const { plan, tool, selection, select, update, showDims } = useStore();
  const svgRef = useRef<SVGSVGElement>(null);
  const b = useMemo(() => planBounds(plan), [plan]);
  const [vb, setVb] = useState<[number, number, number, number] | null>(null);
  const [draft, setDraft] = useState<Vec2[]>([]);
  const [hover, setHover] = useState<Vec2 | null>(null);
  const drag = useRef<null | { kind: string; id: string; off: Vec2; end?: 'a' | 'b'; pan?: [number, number, number, number]; start?: Vec2; moved?: boolean }>(null);
  const style = STYLES[plan.style];

  useEffect(() => { setVb(null); }, [plan.id]);
  const pad = 1.4;
  const view = vb ?? [b.minX - pad, b.minY - pad, b.w + pad * 2, b.h + pad * 2];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT') return;
      const st = useStore.getState();
      if (e.key === 'Escape') { setDraft([]); st.select(null); }
      if ((e.key === 'Delete' || e.key === 'Backspace') && st.selection) { removeSel(); }
      if (e.key.toLowerCase() === 'r' && st.selection?.kind === 'item') {
        st.update((p) => ({ ...p, items: p.items.map((it) => it.id === st.selection!.id ? { ...it, rot: (it.rot + (e.shiftKey ? -15 : 90)) % 360 } : it) }));
      }
      if (e.key === 'Enter' && st.tool === 'room') finishRoom();
      if ((e.metaKey || e.ctrlKey) && e.key === 'z') { e.preventDefault(); e.shiftKey ? st.redo() : st.undo(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  function removeSel() {
    const sel = useStore.getState().selection; if (!sel) return;
    update((p) => ({
      ...p,
      walls: sel.kind === 'wall' ? p.walls.filter((w) => w.id !== sel.id) : p.walls,
      openings: p.openings.filter((o) => !(sel.kind === 'opening' && o.id === sel.id) && !(sel.kind === 'wall' && o.wallId === sel.id)),
      rooms: sel.kind === 'room' ? p.rooms.filter((r) => r.id !== sel.id) : p.rooms,
      items: sel.kind === 'item' ? p.items.filter((i) => i.id !== sel.id) : p.items,
    }));
    select(null);
  }

  function finishRoom() {
    setDraft((d) => {
      if (d.length >= 3) {
        const nRooms = useStore.getState().plan.rooms.length + 1;
        update((p) => ({ ...p, rooms: [...p.rooms, { id: uid('room'), name: `Room ${nRooms}`, floor: 'wood', points: d }] }));
      }
      return [];
    });
  }

  const pt = (e: React.PointerEvent | React.DragEvent | React.WheelEvent) => svgPoint(svgRef.current!, e.clientX, e.clientY);

  function onDown(e: React.PointerEvent) {
    const p = pt(e);
    const target = (e.target as Element).closest('[data-k]') as HTMLElement | null;
    if (tool === 'wall') {
      const s = snapToEndpoints(p, plan);
      if (draft.length) {
        const a = draft[draft.length - 1];
        if (len(a, s) > 0.05) update((pl) => ({ ...pl, walls: [...pl.walls, { id: uid('w'), a, b: s, thickness: 0.12, height: pl.walls[0]?.height ?? 2.7 }] }));
        if (e.detail >= 2) { setDraft([]); return; }
      }
      setDraft([s]);
      return;
    }
    if (tool === 'room') {
      const s = snapToEndpoints(p, plan);
      if (draft.length >= 3 && len(s, draft[0]) < 0.2) { finishRoom(); return; }
      setDraft((d) => [...d, s]);
      return;
    }
    if (tool === 'door' || tool === 'window') {
      const nw = nearestWall(p, plan.walls, 0.5);
      if (nw) {
        const o: Opening = tool === 'door'
          ? { id: uid('o'), wallId: nw.wall.id, kind: 'door', t: nw.t, width: 0.85, height: 2.1, sill: 0 }
          : { id: uid('o'), wallId: nw.wall.id, kind: 'window', t: nw.t, width: 1.2, height: 1.3, sill: 0.9 };
        update((pl) => ({ ...pl, openings: [...pl.openings, o] }));
        select({ kind: 'opening', id: o.id });
      }
      return;
    }
    if (tool === 'erase') {
      if (target) { select({ kind: target.dataset.k as any, id: target.dataset.id! }); setTimeout(removeSel); }
      return;
    }
    // select tool
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    if (target) {
      const kind = target.dataset.k!, id = target.dataset.id!;
      select({ kind: kind as any, id });
      if (kind === 'item') { const it = plan.items.find((i) => i.id === id)!; drag.current = { kind, id, off: [p[0] - it.x, p[1] - it.y], start: p }; }
      else if (kind === 'handle') { drag.current = { kind, id, off: [0, 0], end: target.dataset.end as 'a' | 'b', start: p }; select({ kind: 'wall', id }); }
      else if (kind === 'opening') drag.current = { kind, id, off: [0, 0], start: p };
      else if (kind === 'room') drag.current = { kind: 'pan', id: '', off: [e.clientX, e.clientY], pan: view as any };
      else drag.current = null;
    } else {
      select(null);
      drag.current = { kind: 'pan', id: '', off: [e.clientX, e.clientY], pan: view as any };
    }
  }

  function onMove(e: React.PointerEvent) {
    const p = pt(e);
    setHover(tool === 'wall' || tool === 'room' ? snapToEndpoints(p, plan) : p);
    const d = drag.current;
    if (!d) return;
    if (d.kind === 'pan' && d.pan) {
      const svg = svgRef.current!;
      const k = d.pan[2] / svg.clientWidth;
      setVb([d.pan[0] - (e.clientX - d.off[0]) * k, d.pan[1] - (e.clientY - d.off[1]) * k, d.pan[2], d.pan[3]]);
      return;
    }
    const first = !d.moved; d.moved = true;
    if (d.kind === 'item') {
      update((pl) => ({ ...pl, items: pl.items.map((it) => it.id === d.id ? { ...it, x: snap(p[0] - d.off[0], 0.05), y: snap(p[1] - d.off[1], 0.05) } : it) }), first);
    } else if (d.kind === 'handle') {
      const s = snapToEndpoints(p, { ...plan, walls: plan.walls.filter((w) => w.id !== d.id) });
      update((pl) => ({ ...pl, walls: pl.walls.map((w) => w.id === d.id ? { ...w, [d.end!]: s } : w) }), first);
    } else if (d.kind === 'opening') {
      const o = plan.openings.find((x) => x.id === d.id); const w = o && plan.walls.find((x) => x.id === o.wallId);
      if (o && w) { const r = projectOnSegment(p, w.a, w.b); update((pl) => ({ ...pl, openings: pl.openings.map((x) => x.id === d.id ? { ...x, t: r.t } : x) }), first); }
    }
  }

  function onWheel(e: React.WheelEvent) {
    const p = pt(e);
    const k = Math.exp(e.deltaY * 0.0012);
    const [x, y, w, h] = view;
    setVb([p[0] - (p[0] - x) * k, p[1] - (p[1] - y) * k, w * k, h * k]);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    const type = e.dataTransfer.getData('text/furniture');
    if (!type || !FURNITURE[type]) return;
    const p = pt(e);
    const it: Item = { id: uid('it'), type, x: snap(p[0], 0.05), y: snap(p[1], 0.05), rot: 0 };
    update((pl) => ({ ...pl, items: [...pl.items, it] }));
    useStore.getState().setTool('select');
    select({ kind: 'item', id: it.id });
  }

  const grid = [];
  const ext = Math.max(view[2], view[3]);
  const gx0 = Math.floor(view[0] - ext), gx1 = Math.ceil(view[0] + view[2] + ext), gy0 = Math.floor(view[1] - ext), gy1 = Math.ceil(view[1] + view[3] + ext);
  for (let x = gx0; x <= gx1; x += 0.5) grid.push(<line key={`x${x}`} x1={x} x2={x} y1={gy0} y2={gy1} className={Number.isInteger(x) ? 'g1' : 'g0'} />);
  for (let y = gy0; y <= gy1; y += 0.5) grid.push(<line key={`y${y}`} y1={y} y2={y} x1={gx0} x2={gx1} className={Number.isInteger(y) ? 'g1' : 'g0'} />);
  const selWall = selection?.kind === 'wall' ? plan.walls.find((w) => w.id === selection.id) : null;
  const cx = b.cx, cy = b.cy;

  return (
    <svg ref={svgRef} className={`editor tool-${tool}`} viewBox={view.join(' ')} onPointerDown={onDown} onPointerMove={onMove}
      onPointerUp={() => (drag.current = null)} onWheel={onWheel} onDragOver={(e) => e.preventDefault()} onDrop={onDrop}
      onDoubleClick={() => tool === 'room' && finishRoom()} data-testid="editor2d">
      <rect x={gx0} y={gy0} width={gx1 - gx0} height={gy1 - gy0} fill="#f7f7f4" />
      {plan.background && <image href={plan.background.url} x={plan.background.x} y={plan.background.y} width={plan.background.scale} opacity={plan.background.opacity} preserveAspectRatio="xMinYMin meet" />}
      <g className="grid">{grid}</g>
      {plan.rooms.map((r) => {
        const f = style.floors[r.floor];
        const sel = selection?.kind === 'room' && selection.id === r.id;
        return (
          <g key={r.id} data-k="room" data-id={r.id}>
            <polygon points={r.points.map((p) => p.join(',')).join(' ')} fill={f.base} fillOpacity={0.38} stroke={sel ? '#0d9488' : 'none'} strokeWidth={0.04} />
          </g>
        );
      })}
      {plan.items.filter((i) => FURNITURE[i.type]?.category === 'Decor' && i.type.startsWith('rug')).concat(plan.items.filter((i) => !i.type.startsWith('rug'))).map((it) => (
        <g key={it.id} data-k="item" data-id={it.id}><ItemSymbol item={it} style={plan.style} selected={selection?.kind === 'item' && selection.id === it.id} /></g>
      ))}
      {plan.walls.map((w) => (
        <line key={w.id} data-k="wall" data-id={w.id} x1={w.a[0]} y1={w.a[1]} x2={w.b[0]} y2={w.b[1]} stroke={selection?.id === w.id ? '#0f766e' : '#2b2f36'}
          strokeWidth={w.thickness} strokeLinecap="square" />
      ))}
      {plan.openings.map((o) => {
        const w = plan.walls.find((x) => x.id === o.wallId);
        return w ? <g key={o.id} data-k="opening" data-id={o.id}><OpeningSymbol o={o} wall={w} selected={selection?.id === o.id} /></g> : null;
      })}
      {plan.rooms.map((r) => {
        const c = centroid(r.points);
        return (
          <g key={`l${r.id}`} className="roomlabel" pointerEvents="none">
            <text x={c[0]} y={c[1] - 0.06} textAnchor="middle" fontSize={0.24} fontWeight={700}>{r.name}</text>
            <text x={c[0]} y={c[1] + 0.24} textAnchor="middle" fontSize={0.18} fill="#5b6270">{polygonArea(r.points).toFixed(1)} m²</text>
          </g>
        );
      })}
      {showDims && plan.walls.filter((w) => len(w.a, w.b) >= 1 && w.thickness >= 0.18).map((w) => {
        const mx = (w.a[0] + w.b[0]) / 2, my = (w.a[1] + w.b[1]) / 2;
        const dx = w.b[0] - w.a[0], dy = w.b[1] - w.a[1], l = Math.hypot(dx, dy);
        let nx = -dy / l, ny = dx / l;
        if ((mx + nx - cx) ** 2 + (my + ny - cy) ** 2 < (mx - cx) ** 2 + (my - cy) ** 2) { nx = -nx; ny = -ny; }
        const off = 0.55;
        const a: Vec2 = [w.a[0] + nx * off, w.a[1] + ny * off], bb: Vec2 = [w.b[0] + nx * off, w.b[1] + ny * off];
        const ang = (Math.atan2(dy, dx) * 180) / Math.PI;
        const rot = ang > 90 || ang < -90 ? ang + 180 : ang;
        return (
          <g key={`d${w.id}`} className="dim" pointerEvents="none">
            <line x1={a[0]} y1={a[1]} x2={bb[0]} y2={bb[1]} />
            <line x1={a[0] - nx * 0.12} y1={a[1] - ny * 0.12} x2={a[0] + nx * 0.12} y2={a[1] + ny * 0.12} />
            <line x1={bb[0] - nx * 0.12} y1={bb[1] - ny * 0.12} x2={bb[0] + nx * 0.12} y2={bb[1] + ny * 0.12} />
            <text transform={`translate(${mx + nx * (off + 0.17)} ${my + ny * (off + 0.17) + 0.06}) rotate(${rot})`} textAnchor="middle" fontSize={0.2}>{l.toFixed(2)} m</text>
          </g>
        );
      })}
      {selWall && (['a', 'b'] as const).map((end) => (
        <circle key={end} data-k="handle" data-id={selWall.id} data-end={end} cx={selWall[end][0]} cy={selWall[end][1]} r={0.13} className="handle" />
      ))}
      {draft.length > 0 && hover && (
        <g className="draft" pointerEvents="none">
          <polyline points={[...draft, hover].map((p) => p.join(',')).join(' ')} />
          {tool === 'wall' && <text x={hover[0] + 0.15} y={hover[1] - 0.15} fontSize={0.22}>{len(draft[draft.length - 1], hover).toFixed(2)} m</text>}
          {draft.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={0.07} />)}
        </g>
      )}
      {(tool === 'wall' || tool === 'room') && hover && <circle cx={hover[0]} cy={hover[1]} r={0.06} className="cursor" pointerEvents="none" />}
    </svg>
  );
}
