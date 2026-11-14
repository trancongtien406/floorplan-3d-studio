import { create } from 'zustand';
import type { Plan, StyleId } from './types';
import { DEMO_PLANS } from './data/demoPlans';

export type Tool = 'select' | 'wall' | 'door' | 'window' | 'room' | 'erase';
export type View3D = 'top' | 'iso' | 'dollhouse' | 'walk';
export type Layout = '2d' | '3d' | 'split';
export type Selection = { kind: 'wall' | 'opening' | 'room' | 'item'; id: string } | null;

interface State {
  plans: Plan[];
  current: number;
  plan: Plan;
  tool: Tool;
  view: View3D;
  layout: Layout;
  selection: Selection;
  cutaway: boolean;
  showDims: boolean;
  past: Plan[];
  future: Plan[];
  setTool: (t: Tool) => void;
  setView: (v: View3D) => void;
  setLayout: (l: Layout) => void;
  select: (s: Selection) => void;
  loadPlan: (i: number) => void;
  importPlan: (p: Plan) => void;
  update: (fn: (p: Plan) => Plan, record?: boolean) => void;
  setStyle: (s: StyleId) => void;
  toggle: (k: 'cutaway' | 'showDims') => void;
  undo: () => void;
  redo: () => void;
}

const clone = (p: Plan): Plan => JSON.parse(JSON.stringify(p));

export const useStore = create<State>((set, get) => ({
  plans: DEMO_PLANS.map(clone),
  current: 1,
  plan: clone(DEMO_PLANS[1]),
  tool: 'select',
  view: 'dollhouse',
  layout: 'split',
  selection: null,
  cutaway: false,
  showDims: true,
  past: [],
  future: [],
  setTool: (tool) => set({ tool, selection: null }),
  setView: (view) => set({ view }),
  setLayout: (layout) => set({ layout }),
  select: (selection) => set({ selection }),
  loadPlan: (i) => {
    const { plans, plan, current } = get();
    const saved = plans.slice(); saved[current] = plan;
    set({ plans: saved, current: i, plan: clone(saved[i]), selection: null, past: [], future: [] });
  },
  importPlan: (p) => {
    const plans = [...get().plans, p];
    set({ plans, current: plans.length - 1, plan: clone(p), selection: null, past: [], future: [] });
  },
  update: (fn, record = true) => {
    const { plan, past } = get();
    const next = fn(clone(plan));
    set(record ? { plan: next, past: [...past.slice(-60), plan], future: [] } : { plan: next });
  },
  setStyle: (style) => get().update((p) => ({ ...p, style })),
  toggle: (k) => set({ [k]: !get()[k] } as Partial<State>),
  undo: () => {
    const { past, plan, future } = get();
    if (!past.length) return;
    set({ plan: past[past.length - 1], past: past.slice(0, -1), future: [plan, ...future], selection: null });
  },
  redo: () => {
    const { past, plan, future } = get();
    if (!future.length) return;
    set({ plan: future[0], future: future.slice(1), past: [...past, plan], selection: null });
  },
}));

// handy for automation / screenshots
(window as any).__store = useStore;
