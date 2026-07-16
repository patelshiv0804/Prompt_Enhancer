"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Sparkles, BookOpen, Cpu, Layers, FileText, Search, TrendingUp, Terminal,
  type LucideIcon,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════════════
 * PromptIQUniverse — Unabyss-Style Gravity Wells & Light Theme
 *
 * All particles are simulated in 3D Grid Space (c, r) and project
 * onto the 3D wave grid, making them bob and warp with the waves.
 * Features:
 *   - Gravity Wells: Grid lines bend/sag downwards under the weight
 *     of the AI Engine, Feature Nodes, and Heavy Planets.
 *   - Light Theme: Clean white/violet aesthetic matching light page theme.
 *   - Visual Grid Height & Width Expansion: COLS=21, ROWS=25, SX=82, SY=72
 *     stretches the grid completely, eliminating bottom/side empty spaces.
 *   - Center AI Engine: Placed exactly at central intersection G[12][10].
 *   - 8 Symmetrical Grid Feature Nodes shifted inwards to clear vignettes.
 *   - Spread particles: 6 heavy planets spread widely across columns.
 * ═══════════════════════════════════════════════════════════════ */

// ── Types ────────────────────────────────────────────────────

interface HeavyPlanet {
  c: number; r: number;          // current grid column, row (fractional)
  vc: number; vr: number;        // velocity in grid space
  homeC: number; homeR: number;  // anchor grid coords
  mass: number; fric: number; springK: number;
  p1: number; p2: number;          // noise phases
  size: number; op: number;
  rgb: string; hoverHeight: number;
  trail: { x: number; y: number }[];
  glow: number;
}

interface MediumFlow {
  c: number; r: number;          // current grid column, row (fractional)
  path: { c: number; r: number }[];
  pathIndex: number;
  speed: number;
  size: number; op: number;
  rgb: string; hoverHeight: number;
  trail: { x: number; y: number }[];
}

interface TinyAmbient {
  c: number; r: number;          // grid coords
  homeC: number; homeR: number;  // home coords
  p1: number; p2: number;
  size: number; op: number;
  rgb: string; hoverHeight: number;
  trail: { x: number; y: number }[];
}

interface NPhys {
  x: number; y: number;
  vx: number; vy: number;
  sc: number; scV: number;
  entered: boolean;
}

interface FNode {
  id: string; title: string; shortDesc: string; fullDesc: string;
  icon: LucideIcon; color: string; glow: string;
  side: "left" | "right"; gridR: number; gridC: number; delay: number;
}

// ── Constants ────────────────────────────────────────────────

// 8 Symmetrical Feature Nodes placed on a 21x25 grid (center is c=10, r=12)
// Columns shifted inwards (from 2/18 to 3/17) to prevent vignette cutoff
const NODES: FNode[] = [
  { id: "opt", title: "Prompt Optimization", shortDesc: "AI-driven enhancement", fullDesc: "Refines instructions using contextual expansion and model-specific styling.", icon: Sparkles, color: "#8B5CF6", glow: "rgba(139,92,246,0.28)", side: "left", gridR: 8, gridC: 4, delay: 0 },
  { id: "cmp", title: "Prompt Comparison", shortDesc: "Side-by-side evaluation", fullDesc: "Compare models simultaneously with custom criteria and token cost details.", icon: Layers, color: "#6366F1", glow: "rgba(99,102,241,0.28)", side: "left", gridR: 10, gridC: 5, delay: 0.25 },
  { id: "lib", title: "Prompt Library", shortDesc: "Centralized repository", fullDesc: "Organize, tag, version, and deploy approved prompts with access control.", icon: BookOpen, color: "#A855F7", glow: "rgba(168,85,247,0.28)", side: "left", gridR: 14, gridC: 4, delay: 0.5 },
  { id: "anl", title: "Prompt Analytics", shortDesc: "Performance analytics", fullDesc: "Track token usage, cost optimization, latency, and request frequency across all models.", icon: TrendingUp, color: "#EC4899", glow: "rgba(236,72,153,0.28)", side: "left", gridR: 16, gridC: 5, delay: 0.75 },
  { id: "src", title: "Semantic Search", shortDesc: "AI vector search", fullDesc: "Find prompts conceptually using natural language queries and intent understanding.", icon: Search, color: "#8B5CF6", glow: "rgba(139,92,246,0.28)", side: "right", gridR: 8, gridC: 16, delay: 0.15 },
  { id: "tpl", title: "Variables & Templates", shortDesc: "Reusable setups", fullDesc: "Dynamic prompts using variable placeholders for context, profiles, or data.", icon: FileText, color: "#6366F1", glow: "rgba(99,102,241,0.28)", side: "right", gridR: 10, gridC: 15, delay: 0.65 },
  { id: "mdl", title: "AI Models", shortDesc: "Unified provider routing", fullDesc: "Test prompts across GPT-4o, Claude 3.5, Gemini 1.5, Llama 3 seamlessly.", icon: Cpu, color: "#60A5FA", glow: "rgba(96,165,250,0.28)", side: "right", gridR: 14, gridC: 16, delay: 1.0 },
  { id: "api", title: "API & SDK Access", shortDesc: "Direct integration", fullDesc: "Integrate prompts directly via modern REST APIs or lightweight SDKs in Python/TypeScript.", icon: Terminal, color: "#3B82F6", glow: "rgba(59,130,246,0.28)", side: "right", gridR: 16, gridC: 15, delay: 1.2 },
];

const COLORS = [
  "99,102,241", "139,92,246", "168,85,247",
  "236,72,153", "96,165,250", "244,114,182", "129,140,248",
];

// Expanded grid size: COLS=21, ROWS=25, SX=82, SY=72 stretches the mesh wide and tall to fill space
const TILT = 1.05, COST = Math.cos(TILT), SINT = Math.sin(TILT);
const CAM = 700, COLS = 21, ROWS = 25, SX = 82, SY = 72;

// Entrance Timings (seconds)
const ENT = {
  GRID: 0.0,
  ENGINE: 0.6,
  NODES: 1.2,
  AMBIENT: 1.8,
  MEDIUM: 2.2,
  HEAVY: 2.8,
  DUR: 1.0,
};

// ── Utilities ────────────────────────────────────────────────

const rr = (a: number, b: number) => a + Math.random() * (b - a);
const pk = <T,>(a: T[]): T => a[Math.floor(Math.random() * a.length)];
const c01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

// Multi-octave organic noise
function noise(t: number, p1: number, p2: number) {
  return {
    x:
      Math.sin(t * 0.5 + p1) * 0.45 +
      Math.sin(t * 1.1 + p1 * 2.1) * 0.35 +
      Math.sin(t * 2.5 + p1 * 0.7) * 0.15 +
      Math.sin(t * 4.5 + p1 * 3.2) * 0.05,
    y:
      Math.sin(t * 0.4 + p2) * 0.45 +
      Math.sin(t * 0.9 + p2 * 1.8) * 0.35 +
      Math.sin(t * 2.1 + p2 * 0.9) * 0.15 +
      Math.sin(t * 3.9 + p2 * 2.6) * 0.05,
  };
}

// ── Projection Helper ────────────────────────────────────────

function projectGrid(c: number, r: number, wz: number, mcx: number, mcy: number, hoverHeight: number = 0) {
  const u = (c - (COLS - 1) / 2) * SX;
  const v = (r - (ROWS - 1) / 2) * SY;
  const ry = v * COST - (wz + hoverHeight) * SINT;
  const rz = v * SINT + (wz + hoverHeight) * COST;
  const s = CAM / (CAM + rz + 80);
  return {
    x: mcx + u * s,
    y: mcy + ry * s,
    scale: s,
  };
}

// ── Drawing Helper ───────────────────────────────────────────

function drawDot(
  ctx: CanvasRenderingContext2D,
  x: number, y: number,
  sz: number, rgb: string, op: number, glow: number,
  trail: { x: number; y: number }[],
  parallaxX: number, parallaxY: number,
  vx: number = 0, vy: number = 0,
) {
  if (op < 0.005) return;

  const px = x + parallaxX;
  const py = y + parallaxY;
  const spd = Math.sqrt(vx * vx + vy * vy);

  // Draw faded trailing positions
  if (trail.length > 1) {
    ctx.beginPath();
    ctx.moveTo(trail[trail.length - 1].x + parallaxX, trail[trail.length - 1].y + parallaxY);
    for (let i = trail.length - 2; i >= 0; i--) {
      ctx.lineTo(trail[i].x + parallaxX, trail[i].y + parallaxY);
    }
    ctx.lineTo(px, py);
    ctx.lineWidth = sz * 0.8;
    ctx.strokeStyle = `rgba(${rgb}, ${op * 0.15})`;
    ctx.lineCap = "round";
    ctx.stroke();
  }

  // Motion blur stretch based on velocity
  if (spd > 0.5) {
    const stretch = Math.min(spd * 1.5, sz * 4);
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(Math.atan2(vy, vx));
    ctx.beginPath();
    ctx.ellipse(0, 0, sz + stretch, sz * 0.65, 0, 0, 6.283);
    ctx.fillStyle = `rgba(${rgb}, ${op * 0.08})`;
    ctx.fill();
    ctx.restore();
  }

  // Glow Halo
  if (glow > 0) {
    ctx.beginPath();
    ctx.arc(px, py, sz * (1 + glow), 0, 6.283);
    ctx.fillStyle = `rgba(${rgb}, ${op * 0.08})`;
    ctx.fill();
  }

  // Core Dot
  ctx.beginPath();
  ctx.arc(px, py, sz, 0, 6.283);
  ctx.fillStyle = `rgba(${rgb}, ${op * 0.95})`;
  ctx.fill();

  // White highlight
  if (sz > 2.5) {
    ctx.beginPath();
    ctx.arc(px - sz * 0.2, py - sz * 0.2, sz * 0.2, 0, 6.283);
    ctx.fillStyle = `rgba(255, 255, 255, ${op * 0.35})`;
    ctx.fill();
  }
}

// ── Grid Lines Drawing ───────────────────────────────────────

function drawGrid(
  ctx: CanvasRenderingContext2D,
  G: { px: number; py: number }[][],
  alpha: number,
  parallaxX: number, parallaxY: number,
) {
  if (alpha < 0.01) return;
  const GC = "175, 170, 185"; // Warm grey-violet grid lines for light theme
  ctx.lineWidth = 1.15;

  ctx.save();
  ctx.translate(parallaxX, parallaxY);

  // Horizontal Grid Lines
  for (let r = 0; r < ROWS; r++) {
    ctx.beginPath();
    for (let c = 0; c < COLS; c++) {
      c === 0 ? ctx.moveTo(G[r][c].px, G[r][c].py) : ctx.lineTo(G[r][c].px, G[r][c].py);
    }
    const a = (0.12 + (r / (ROWS - 1)) * 0.46) * alpha;
    const g = ctx.createLinearGradient(G[r][0].px, 0, G[r][COLS - 1].px, 0);
    g.addColorStop(0, `rgba(${GC}, 0)`);
    g.addColorStop(0.12, `rgba(${GC}, ${a})`);
    g.addColorStop(0.88, `rgba(${GC}, ${a})`);
    g.addColorStop(1, `rgba(${GC}, 0)`);
    ctx.strokeStyle = g;
    ctx.stroke();
  }

  // Vertical Grid Lines
  for (let c = 0; c < COLS; c++) {
    ctx.beginPath();
    for (let r = 0; r < ROWS; r++) {
      r === 0 ? ctx.moveTo(G[r][c].px, G[r][c].py) : ctx.lineTo(G[r][c].px, G[r][c].py);
    }
    const s = 1 - Math.abs((c - (COLS - 1) / 2) / ((COLS - 1) / 2));
    ctx.strokeStyle = `rgba(${GC}, ${(0.06 + s * 0.34) * alpha})`;
    ctx.stroke();
  }

  // Intersection Dots
  for (let r = 1; r < ROWS - 1; r += 2) {
    for (let c = 1; c < COLS - 1; c += 2) {
      if (r < 5) continue; // Leave the top 5 rows clear of intersection dots
      ctx.beginPath();
      ctx.arc(G[r][c].px, G[r][c].py, 1.8, 0, 6.283);
      ctx.fillStyle = `rgba(${GC}, ${(0.18 + (r / (ROWS - 1)) * 0.52) * alpha})`;
      ctx.fill();
    }
  }

  ctx.restore();
}

// ══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════════════════════════════

export default function PromptIQUniverse() {
  const bgCanvasRef = useRef<HTMLCanvasElement>(null);
  const mainCanvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const rafRef = useRef(0);
  const mouseRef = useRef({ x: 0, y: 0, sx: 0, sy: 0, active: false });
  const timeRef = useRef(0);
  const entRef = useRef(0);
  const scrollRef = useRef(false);

  // Structured particles
  const heavyRef = useRef<HeavyPlanet[]>([]);
  const mediumRef = useRef<MediumFlow[]>([]);
  const tinyRef = useRef<TinyAmbient[]>([]);

  // DOM node anchors and engine positioning
  const nPhysRef = useRef<Map<string, NPhys>>(new Map());
  const nElsRef = useRef<Record<string, HTMLDivElement | null>>({});
  const aiRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);

  const [activeId, setActiveId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const aRef = useRef<string | null>(null);
  const hRef = useRef<string | null>(null);

  useEffect(() => { aRef.current = activeId; }, [activeId]);
  useEffect(() => { hRef.current = hoverId; }, [hoverId]);

  // Initialize and main loop
  useEffect(() => {
    const bgC = bgCanvasRef.current;
    const mainC = mainCanvasRef.current;
    const container = containerRef.current;
    if (!bgC || !mainC || !container) return;

    const bgX = bgC.getContext("2d", { alpha: true })!;
    const mX = mainC.getContext("2d", { alpha: true })!;
    let cw = 0, ch = 0, active = true, initialized = false;

    // ─ Resize ───────────────────────────────────────────
    function resize() {
      cw = mainC!.clientWidth;
      ch = mainC!.clientHeight;
      if (cw === 0 || ch === 0) return;
      const dpr = Math.min(devicePixelRatio || 1, 2);
      mainC!.width = cw * dpr;
      mainC!.height = ch * dpr;
      mX.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Blur background at 1x DPR
      bgC!.width = cw;
      bgC!.height = ch;
      bgX.setTransform(1, 0, 0, 1, 0, 0);

      mouseRef.current.sx = cw / 2;
      mouseRef.current.sy = ch / 2;

      if (!initialized) {
        initialized = true;
        initHeavyPlanets();
        initMediumFlow();
        initTinyAmbient();
        initNodePhys();
        rafRef.current = requestAnimationFrame(tick);
      }
    }

    // ─ 1. Heavy Planets (6 total, spread out widely on 21x25 grid) ──────
    function initHeavyPlanets() {
      const arr: HeavyPlanet[] = [];
      const anchors = [
        { c: 2.5, r: 13.0, sz: 12, h: 0, rgb: "139,92,246" },  // Far left
        { c: 5.5, r: 19.5, sz: 11, h: 0, rgb: "96,165,250" },  // Mid left
        { c: 10.5, r: 21.5, sz: 15, h: 0, rgb: "99,102,241" }, // Center bottom
        { c: 10.0, r: 9.5,  sz: 10, h: 0, rgb: "244,114,182" }, // Center top-ish
        { c: 14.5, r: 19.0, sz: 12, h: 0, rgb: "168,85,247" }, // Mid right
        { c: 18.5, r: 13.5, sz: 13, h: 0, rgb: "236,72,153" }, // Far right
      ];

      anchors.forEach((anc) => {
        arr.push({
          c: anc.c, r: anc.r,
          vc: 0, vr: 0,
          homeC: anc.c, homeR: anc.r,
          mass: rr(3.5, 5.0),
          fric: 0.975,
          springK: rr(0.003, 0.006),
          p1: Math.random() * 200, p2: Math.random() * 200,
          size: anc.sz,
          op: rr(0.42, 0.58),
          rgb: anc.rgb,
          hoverHeight: anc.h,
          trail: Array.from({ length: 4 }, () => ({ x: 0, y: 0 })),
          glow: 2.8,
        });
      });
      heavyRef.current = arr;
    }

    // ─ 2. Medium Flow ────────────────────────────────────
    function initMediumFlow() {
      const arr: MediumFlow[] = [];
      const paths = [
        [{ c: 4, r: 8 }, { c: 10, r: 8 }, { c: 10, r: 12 }],
        [{ c: 5, r: 10 }, { c: 10, r: 10 }, { c: 10, r: 12 }],
        [{ c: 4, r: 14 }, { c: 6, r: 14 }, { c: 10, r: 12 }],
        [{ c: 5, r: 16 }, { c: 10, r: 16 }, { c: 10, r: 12 }],
        [{ c: 16, r: 8 }, { c: 10, r: 8 }, { c: 10, r: 12 }],
        [{ c: 15, r: 10 }, { c: 10, r: 10 }, { c: 10, r: 12 }],
        [{ c: 16, r: 14 }, { c: 12, r: 14 }, { c: 10, r: 12 }],
        [{ c: 15, r: 16 }, { c: 10, r: 16 }, { c: 10, r: 12 }],
      ];

      for (let i = 0; i < 11; i++) {
        const selectedPath = pk(paths);
        arr.push({
          c: selectedPath[0].c, r: selectedPath[0].r,
          path: selectedPath,
          pathIndex: 1,
          speed: rr(0.012, 0.024),
          size: rr(3.5, 6.0),
          op: rr(0.28, 0.48),
          rgb: pk(COLORS),
          hoverHeight: 2,
          trail: Array.from({ length: 3 }, () => ({ x: 0, y: 0 })),
        });
      }
      mediumRef.current = arr;
    }

    // ─ 3. Tiny Ambient ───────────────────────────────────
    function initTinyAmbient() {
      const arr: TinyAmbient[] = [];
      const usedKeys = new Set<string>();

      while (arr.length < 15) {
        const gr = Math.floor(rr(5, 23));
        const gc = Math.floor(rr(2, 19));
        const key = `${gc}-${gr}`;

        if (!usedKeys.has(key)) {
          usedKeys.add(key);
          arr.push({
            c: gc, r: gr,
            homeC: gc, homeR: gr,
            p1: Math.random() * 200, p2: Math.random() * 200,
            size: rr(1.0, 2.0),
            op: rr(0.12, 0.28),
            rgb: pk(COLORS),
            hoverHeight: 0,
            trail: Array.from({ length: 2 }, () => ({ x: 0, y: 0 })),
          });
        }
      }
      tinyRef.current = arr;
    }

    // ─ 4. Node Physics ──────────────────────────────────
    function initNodePhys() {
      const m = new Map<string, NPhys>();
      NODES.forEach((n) => {
        m.set(n.id, {
          x: 0, y: 0, vx: 0, vy: 0,
          sc: 0, scV: 0, entered: false,
        });
      });
      nPhysRef.current = m;
    }

    // ─ Reset Medium Particle Flow ────────────────────────
    function resetMediumFlow(p: MediumFlow) {
      const paths = [
        [{ c: 4, r: 8 }, { c: 10, r: 8 }, { c: 10, r: 12 }],
        [{ c: 5, r: 10 }, { c: 10, r: 10 }, { c: 10, r: 12 }],
        [{ c: 4, r: 14 }, { c: 6, r: 14 }, { c: 10, r: 12 }],
        [{ c: 5, r: 16 }, { c: 10, r: 16 }, { c: 10, r: 12 }],
        [{ c: 16, r: 8 }, { c: 10, r: 8 }, { c: 10, r: 12 }],
        [{ c: 15, r: 10 }, { c: 10, r: 10 }, { c: 10, r: 12 }],
        [{ c: 16, r: 14 }, { c: 12, r: 14 }, { c: 10, r: 12 }],
        [{ c: 15, r: 16 }, { c: 10, r: 16 }, { c: 10, r: 12 }],
      ];
      p.path = pk(paths);
      p.c = p.path[0].c;
      p.r = p.path[0].r;
      p.pathIndex = 1;
      p.speed = rr(0.012, 0.024);
      p.rgb = pk(COLORS);
      p.op = rr(0.28, 0.48);
      for (let i = 0; i < p.trail.length; i++) {
        p.trail[i] = { x: 0, y: 0 };
      }
    }

    // ─ Gravity Well displacement calculation ──────
    function getWarpZ(u: number, v: number, t: number) {
      let warp = 0;

      // 1. Warp under Central AI Engine (col 10, row 12)
      const engineU = (10 - (COLS - 1) / 2) * SX;
      const engineV = (12 - (ROWS - 1) / 2) * SY;
      const dEngU = u - engineU;
      const dEngV = v - engineV;
      const dist2Eng = dEngU * dEngU + dEngV * dEngV;
      warp -= 65 * Math.exp(-dist2Eng / (2 * 125 * 125));

      // 2. Warp under each Feature Node
      NODES.forEach((n) => {
        const nodeU = (n.gridC - (COLS - 1) / 2) * SX;
        const nodeV = (n.gridR - (ROWS - 1) / 2) * SY;
        const dNodeU = u - nodeU;
        const dNodeV = v - nodeV;
        const dist2Node = dNodeU * dNodeU + dNodeV * dNodeV;
        const ph = nPhysRef.current.get(n.id);
        const scale = ph ? ph.sc : 1;
        warp -= 35 * scale * Math.exp(-dist2Node / (2 * 80 * 80));
      });

      // 3. Warp under each Heavy Planet
      const heavies = heavyRef.current;
      heavies.forEach((p) => {
        const pU = (p.c - (COLS - 1) / 2) * SX;
        const pV = (p.r - (ROWS - 1) / 2) * SY;
        const dpU = u - pU;
        const dpV = v - pV;
        const dist2Planet = dpU * dpU + dpV * dpV;
        warp -= 28 * Math.exp(-dist2Planet / (2 * 65 * 65));
      });

      return warp;
    }

    // ─ Computed grid points with gravity wells ───────────
    function computeGridPoints(t: number) {
      const mcx = cw / 2, mcy = ch * 0.50; // Shifted mcy to 50% height to raise grid vertically
      const G: { px: number; py: number; wz: number }[][] = [];
      for (let r = 0; r < ROWS; r++) {
        G[r] = [];
        for (let c = 0; c < COLS; c++) {
          const u = (c - (COLS - 1) / 2) * SX;
          const v = (r - (ROWS - 1) / 2) * SY;
          const d = Math.sqrt(u * u + v * v);

          const baseWz =
            Math.sin(u * 0.008 + t) * Math.cos(v * 0.008 + t * 0.75) * 20 +
            Math.sin(d * 0.01 - t * 1.3) * 6;
          const warpZ = getWarpZ(u, v, t);
          const wz = baseWz + warpZ;

          const ry = v * COST - wz * SINT;
          const rz = v * SINT + wz * COST;
          const s = CAM / (CAM + rz + 80);
          G[r][c] = { px: mcx + u * s, py: mcy + ry * s, wz };
        }
      }
      return G;
    }

    // ─ Wave height calculation at arbitrary grid coord ──
    function getWaveZ(c: number, r: number, t: number) {
      const u = (c - (COLS - 1) / 2) * SX;
      const v = (r - (ROWS - 1) / 2) * SY;
      const d = Math.sqrt(u * u + v * v);
      const baseWz =
        Math.sin(u * 0.008 + t) * Math.cos(v * 0.008 + t * 0.75) * 20 +
        Math.sin(d * 0.01 - t * 1.3) * 6;
      const warpZ = getWarpZ(u, v, t);
      return baseWz + warpZ;
    }

    // ─ Event Listeners ───────────────────────────────────
    const onMM = (e: MouseEvent) => {
      const r = container!.getBoundingClientRect();
      mouseRef.current.x = e.clientX - r.left;
      mouseRef.current.y = e.clientY - r.top;
      mouseRef.current.active = true;
    };
    const onML = () => { mouseRef.current.active = false; };
    container.addEventListener("mousemove", onMM);
    container.addEventListener("mouseleave", onML);

    let scrollTO: ReturnType<typeof setTimeout>;
    const onScroll = () => {
      scrollRef.current = true;
      clearTimeout(scrollTO);
      scrollTO = setTimeout(() => { scrollRef.current = false; }, 150);
    };
    window.addEventListener("scroll", onScroll, { passive: true });

    // ─ TICK LOOP ─────────────────────────────────────────
    let lastTs = 0;

    function tick(ts: number) {
      if (!active) return;
      rafRef.current = requestAnimationFrame(tick);

      const dt = ts - lastTs;
      const limit = scrollRef.current ? 66.7 : 16.7;
      if (dt < limit) return;
      lastTs = ts - (dt % limit);

      const time = timeRef.current;
      const ent = entRef.current;

      if (!scrollRef.current) {
        timeRef.current += 0.016;
        entRef.current = Math.min(entRef.current + 0.016, 20);
      }

      // Smooth mouse input
      const m = mouseRef.current;
      const tgtX = m.active ? m.x : cw / 2;
      const tgtY = m.active ? m.y : ch / 2;
      m.sx += (tgtX - m.sx) * 0.06;
      m.sy += (tgtY - m.sy) * 0.06;

      // Normalized coordinates
      const normX = (m.sx - cw / 2) / Math.max(cw / 2, 1);
      const normY = (m.sy - ch / 2) / Math.max(ch / 2, 1);

      // Camera Parallax values
      const bgPx = normX * -2, bgPy = normY * -1.5;
      const midPx = normX * -5, midPy = normY * -3.0;
      const fgPx = normX * -10, fgPy = normY * -6.0;

      // Choreographed entrance factors
      const gridAlpha = c01((ent - ENT.GRID) / ENT.DUR);
      const engineAlpha = c01((ent - ENT.ENGINE) / ENT.DUR);
      const nodeAlpha = c01((ent - ENT.NODES) / ENT.DUR);
      const ambientAlpha = c01((ent - ENT.AMBIENT) / ENT.DUR);
      const mediumAlpha = c01((ent - ENT.MEDIUM) / ENT.DUR);
      const heavyAlpha = c01((ent - ENT.HEAVY) / ENT.DUR);

      const mcx = cw / 2, mcy = ch * 0.50; // Visual center at 50% height

      // Compute grid wave frame (includes gravity well warps)
      const G = computeGridPoints(time);

      // ═════════ PHYSICS RUN (paused on scroll) ═════════
      if (!scrollRef.current) {

        // ── 1. Heavy Planets ──
        const heavies = heavyRef.current;
        for (let i = 0; i < heavies.length; i++) {
          const p = heavies[i];

          const n = noise(time * 0.4, p.p1, p.p2);
          const tgtC = p.homeC + n.x * 1.5;
          const tgtR = p.homeR + n.y * 0.8;

          // Spring forces in grid coordinates
          let fc = (tgtC - p.c) * p.springK;
          let fr = (tgtR - p.r) * p.springK;

          // Gentle mouse reaction
          if (m.active) {
            const wz = getWaveZ(p.c, p.r, time);
            const pr = projectGrid(p.c, p.r, wz, mcx, mcy, p.hoverHeight);
            const dx = (pr.x + fgPx) - m.sx;
            const dy = (pr.y + fgPy) - m.sy;
            const dist2 = dx * dx + dy * dy;

            if (dist2 < 40000 && dist2 > 1) {
              const dist = Math.sqrt(dist2);
              const f = (1 - dist / 200) * 0.2 / p.mass;
              fc += (dx / dist) * f;
              fr += (dy / dist) * f;
            }
          }

          p.vc = (p.vc + fc / p.mass) * p.fric;
          p.vr = (p.vr + fr / p.mass) * p.fric;

          p.c += p.vc;
          p.r += p.vr;

          const wz = getWaveZ(p.c, p.r, time);
          const pr = projectGrid(p.c, p.r, wz, mcx, mcy, p.hoverHeight);

          // Update trail history
          for (let k = p.trail.length - 1; k > 0; k--) {
            p.trail[k].x = p.trail[k - 1].x;
            p.trail[k].y = p.trail[k - 1].y;
          }
          p.trail[0] = { x: pr.x, y: pr.y };
        }

        // ── 2. Medium Flow ──
        const mediums = mediumRef.current;
        for (let i = 0; i < mediums.length; i++) {
          const p = mediums[i];

          const tgt = p.path[p.pathIndex];
          const dc = tgt.c - p.c;
          const dr = tgt.r - p.r;
          const dist = Math.sqrt(dc * dc + dr * dr);

          if (dist < 0.08) {
            if (p.pathIndex < p.path.length - 1) {
              p.pathIndex++;
            } else {
              resetMediumFlow(p);
            }
          } else {
            p.c += (dc / dist) * p.speed;
            p.r += (dr / dist) * p.speed;
          }

          const wz = getWaveZ(p.c, p.r, time);
          const pr = projectGrid(p.c, p.r, wz, mcx, mcy, p.hoverHeight);

          for (let k = p.trail.length - 1; k > 0; k--) {
            p.trail[k].x = p.trail[k - 1].x;
            p.trail[k].y = p.trail[k - 1].y;
          }
          p.trail[0] = { x: pr.x, y: pr.y };
        }

        // ── 3. Tiny Ambient ──
        const tinies = tinyRef.current;
        for (let i = 0; i < tinies.length; i++) {
          const p = tinies[i];

          const n = noise(time * 0.8 + i, p.p1, p.p2);
          p.c = p.homeC + n.x * 0.15;
          p.r = p.homeR + n.y * 0.15;

          const wz = getWaveZ(p.c, p.r, time);
          const pr = projectGrid(p.c, p.r, wz, mcx, mcy, p.hoverHeight);

          for (let k = p.trail.length - 1; k > 0; k--) {
            p.trail[k].x = p.trail[k - 1].x;
            p.trail[k].y = p.trail[k - 1].y;
          }
          p.trail[0] = { x: pr.x, y: pr.y };
        }

        // ── 4. Feature Node anchors update ──
        NODES.forEach((n, i) => {
          const ph = nPhysRef.current.get(n.id)!;
          const pt = G[n.gridR]?.[n.gridC];
          if (!pt) return;

          const eT = ent - (ENT.NODES + i * 0.15);
          if (eT < 0) { ph.sc = 0; return; }

          if (!ph.entered) {
            ph.entered = true;
            ph.x = pt.px;
            ph.y = pt.py;
          }

          ph.scV += (1 - ph.sc) * 0.08;
          ph.scV *= 0.82;
          ph.sc += ph.scV;

          const tX = pt.px;
          const tY = pt.py;

          ph.vx += (tX - ph.x) * 0.045;
          ph.vy += (tY - ph.y) * 0.045;

          if (m.active) {
            const dx = ph.x + fgPx - m.sx;
            const dy = ph.y + fgPy - m.sy;
            const dist2 = dx * dx + dy * dy;
            if (dist2 < 40000 && dist2 > 1) {
              const dist = Math.sqrt(dist2);
              const f = (1 - dist / 200) * 0.8;
              ph.vx += (dx / dist) * f;
              ph.vy += (dy / dist) * f;
            }
          }

          ph.vx *= 0.88;
          ph.vy *= 0.88;
          ph.x += ph.vx;
          ph.y += ph.vy;
        });

      } // End physics

      // ═════════════════ CANVAS RENDER ═════════════════

      // ── Background canvas (blurred tiny ambient) ──
      bgX.clearRect(0, 0, cw, ch);
      if (ambientAlpha > 0.01) {
        bgX.save();
        bgX.globalAlpha = ambientAlpha;
        const tinies = tinyRef.current;
        for (let i = 0; i < tinies.length; i++) {
          const p = tinies[i];
          const wz = getWaveZ(p.c, p.r, time);
          const pr = projectGrid(p.c, p.r, wz, mcx, mcy, p.hoverHeight);
          drawDot(bgX, pr.x, pr.y, p.size, p.rgb, p.op, 0, p.trail, bgPx, bgPy);
        }
        bgX.restore();
      }

      // ── Main canvas (sharp elements) ──
      mX.clearRect(0, 0, cw, ch);

      // 1. Grid
      drawGrid(mX, G, gridAlpha, bgPx, bgPy);

      // 2. Node shadows on grid
      NODES.forEach((n, i) => {
        const eT = ent - (ENT.NODES + i * 0.15);
        if (eT < 0) return;
        const pt = G[n.gridR]?.[n.gridC];
        if (!pt) return;
        mX.beginPath();
        mX.ellipse(pt.px + bgPx, pt.py + bgPy + 5, 17, 5, 0, 0, 6.283);
        mX.fillStyle = `rgba(0,0,0, ${c01(eT / 0.5) * 0.06})`;
        mX.fill();
      });

      // AI Engine shadow (G[12][10] is the center row/col)
      const cPt = G[12]?.[10];
      if (cPt && engineAlpha > 0.01) {
        mX.beginPath();
        mX.ellipse(cPt.px + bgPx, cPt.py + bgPy + 8, 32, 8, 0, 0, 6.283);
        mX.fillStyle = `rgba(234,88,12, ${0.12 * engineAlpha})`;
        mX.fill();
      }

      // 3. Medium Flow (Sharp, middle parallax)
      if (mediumAlpha > 0.01) {
        mX.save();
        mX.globalAlpha = mediumAlpha;
        const mediums = mediumRef.current;
        for (let i = 0; i < mediums.length; i++) {
          const p = mediums[i];
          const wz = getWaveZ(p.c, p.r, time);
          const pr = projectGrid(p.c, p.r, wz, mcx, mcy, p.hoverHeight);

          const vc = (p.path[p.pathIndex].c - p.c);
          const vr = (p.path[p.pathIndex].r - p.r);
          const vl = Math.sqrt(vc * vc + vr * vr) || 1;
          const vx = (vc / vl) * p.speed * SX;
          const vy = (vr / vl) * p.speed * SY;

          drawDot(mX, pr.x, pr.y, p.size, p.rgb, p.op, 0, p.trail, midPx, midPy, vx, vy);
        }
        mX.restore();
      }

      // 4. Heavy Planets (Sharp, foreground parallax)
      if (heavyAlpha > 0.01) {
        mX.save();
        mX.globalAlpha = heavyAlpha;
        const heavies = heavyRef.current;
        for (let i = 0; i < heavies.length; i++) {
          const p = heavies[i];
          const wz = getWaveZ(p.c, p.r, time);
          const pr = projectGrid(p.c, p.r, wz, mcx, mcy, p.hoverHeight);
          const currentSz = p.size * pr.scale;

          drawDot(mX, pr.x, pr.y, currentSz, p.rgb, p.op, p.glow, p.trail, fgPx, fgPy, p.vc * SX, p.vr * SY);
        }
        mX.restore();
      }

      mX.restore();

      // ── Position DOM elements ──
      // Central AI Engine (G[12][10] is exactly the center row/col)
      if (aiRef.current && cPt) {
        const ae = aiRef.current;
        ae.style.left = `${cPt.px + midPx}px`;
        ae.style.top = `${cPt.py + midPy}px`;
        ae.style.transform = "translate(-50%,-50%)";
        ae.style.opacity = String(engineAlpha);
      }

      // Ambient Glow
      if (glowRef.current) glowRef.current.style.opacity = String(gridAlpha);

      // Feature Node DOM wrappers (Glossy 3D Glass)
      NODES.forEach((n) => {
        const ph = nPhysRef.current.get(n.id)!;
        const el = nElsRef.current[n.id];
        if (!el) return;
        if (ph.sc < 0.01) { el.style.opacity = "0"; return; }

        const isAct = aRef.current === n.id;
        const isDim = aRef.current !== null && !isAct;

        el.style.left = `${ph.x + fgPx}px`;
        el.style.top = `${ph.y + fgPy}px`;
        el.style.transform = `translate(-50%,-50%) scale(${ph.sc * (isAct ? 1.14 : 1)})`;
        el.style.opacity = String(ph.sc * (isAct ? 1 : isDim ? 0.22 : 1));
        el.style.zIndex = String(isAct ? 500 : 10);
      });
    }

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(mainC);

    return () => {
      active = false;
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      container.removeEventListener("mousemove", onMM);
      container.removeEventListener("mouseleave", onML);
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  // ── JSX ────────────────────────────────────────────────────
  return (
    <div
      ref={containerRef}
      className="absolute inset-0 bg-[#FAFBFC]"
      onClick={() => setActiveId(null)}
    >
      {/* Background canvas — blurred tiny ambient */}
      <canvas
        ref={bgCanvasRef}
        className="absolute inset-0 pointer-events-none"
        style={{ width: "100%", height: "100%", filter: "blur(2.5px)", opacity: 0.65, zIndex: 0 }}
      />

      {/* Main canvas — sharp grid + middle + foreground */}
      <canvas
        ref={mainCanvasRef}
        className="absolute inset-0 pointer-events-none"
        style={{ width: "100%", height: "100%", zIndex: 1 }}
      />

      {/* Edge fade vignettes to match light background */}
      <div className="pointer-events-none absolute inset-0" style={{ zIndex: 2 }}>
        <div className="absolute left-0 top-0 bottom-0" style={{ width: "4%", background: "linear-gradient(to right, #FAFBFC, transparent)" }} />
        <div className="absolute right-0 top-0 bottom-0" style={{ width: "4%", background: "linear-gradient(to left, #FAFBFC, transparent)" }} />
        <div className="absolute top-0 left-0 right-0" style={{ height: "24%", background: "linear-gradient(to bottom, #FAFBFC, transparent)" }} />
        <div className="absolute bottom-0 left-0 right-0" style={{ height: "4%", background: "linear-gradient(to top, #FAFBFC, transparent)" }} />
      </div>

      {/* Ambient center glow */}
      <div
        ref={glowRef}
        className="pointer-events-none absolute inset-0"
        style={{
          background: "radial-gradient(ellipse 55% 40% at 50% 50%, rgba(139,92,246,0.05) 0%, transparent 70%)",
          zIndex: 3, opacity: 0,
        }}
      />

      {/* ── Central AI Engine ── */}
      <div ref={aiRef} className="absolute" style={{ zIndex: 50, opacity: 0 }}>
        <div className="relative flex items-center justify-center">
          <motion.div
            className="absolute rounded-full"
            style={{ width: 144, height: 144, background: "radial-gradient(circle, rgba(249,115,22,0.22) 0%, rgba(234,88,12,0.06) 55%, transparent 100%)" }}
            animate={{ scale: [1, 1.14, 1], opacity: [0.65, 0.95, 0.65] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute rounded-full"
            style={{ width: 96, height: 96, background: "radial-gradient(circle, rgba(255,255,255,0.9) 0%, rgba(251,146,60,0.70) 28%, rgba(234,88,12,0.15) 65%, transparent 100%)" }}
            animate={{ scale: [1, 1.08, 1], opacity: [0.65, 0.9, 0.65] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          />
          <div className="absolute pointer-events-none" style={{ transform: "rotateX(70deg) rotateY(-20deg)" }}>
            <motion.div
              className="border border-[#F97316]/30 rounded-full"
              style={{ width: 138, height: 138 }}
              animate={{ rotate: 360 }}
              transition={{ duration: 13, repeat: Infinity, ease: "linear" }}
            />
          </div>
          <div className="absolute pointer-events-none" style={{ transform: "rotateX(65deg) rotateY(25deg)" }}>
            <motion.div
              className="border border-[#8B5CF6]/20 rounded-full"
              style={{ width: 166, height: 166 }}
              animate={{ rotate: -360 }}
              transition={{ duration: 17, repeat: Infinity, ease: "linear" }}
            />
          </div>
          <motion.div
            className="relative z-10 flex h-16 w-16 items-center justify-center rounded-full"
            style={{
              background: "linear-gradient(135deg,#F97316,#EA580C,#DC2626)",
              boxShadow: "0 0 28px #EA580C,0 0 10px #F97316 inset",
              border: "1.5px solid rgba(255,255,255,0.35)",
            }}
            animate={{ y: [-2, 2, -2] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L22 7L22 17L12 22L2 17L2 7Z" />
              <path d="M2 7L12 12L22 7" />
              <path d="M12 12L12 22" />
            </svg>
          </motion.div>
          <div
            className="absolute pointer-events-none"
            style={{ top: "calc(50% + 42px)", left: "50%", transform: "translateX(-50%)", whiteSpace: "nowrap" }}
          >
            <span className="text-[10px] tracking-[0.22em] font-extrabold uppercase text-[#EA580C] bg-white/80 backdrop-blur-md px-2 py-0.5 rounded-full border border-orange-400/20 shadow-sm">
              AI Engine
            </span>
          </div>
        </div>
      </div>

      {/* ── Feature Nodes (Light Theme Glossy 3D Glass) ── */}
      {NODES.map((n) => {
        const NodeIcon = n.icon;
        const isActive = activeId === n.id;
        const isHovered = hoverId === n.id;
        const labelOnRight = n.side === "left";

        return (
          <div
            key={n.id}
            ref={(el) => { nElsRef.current[n.id] = el; }}
            className="absolute cursor-pointer"
            style={{ left: 0, top: 0, transform: "translate(-50%,-50%)", zIndex: isActive ? 200 : 10, opacity: 0 }}
            onClick={(e) => { e.stopPropagation(); setActiveId(isActive ? null : n.id); }}
            onMouseEnter={() => setHoverId(n.id)}
            onMouseLeave={() => setHoverId(null)}
          >
            {/* Pulse ring */}
            <AnimatePresence>
              {(isHovered || isActive) && (
                <motion.div
                  className="absolute -inset-3 rounded-full pointer-events-none"
                  style={{ border: `1.5px solid ${n.color}`, boxShadow: `0 0 12px ${n.glow}` }}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: [0.8, 0.35, 0.8], scale: [1, 1.06, 1] }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
                />
              )}
            </AnimatePresence>

            {/* Glossy 3D glass sphere */}
            <div
              className="relative flex items-center justify-center rounded-full"
              style={{
                width: 52, height: 52,
                background: `radial-gradient(circle at 35% 35%, #ffffff 0%, #f9fafb 32%, #f3f4f6 60%, ${n.glow.replace("0.28", "0.12")} 85%, ${n.glow.replace("0.28", "0.22")} 100%)`,
                boxShadow: isHovered || isActive
                  ? "0 10px 24px -4px rgba(0,0,0,0.12), inset 2px 2px 4px rgba(255,255,255,0.9), inset -2px -2px 6px rgba(0,0,0,0.06)"
                  : "0 6px 18px -4px rgba(0,0,0,0.08), inset 2px 2px 3px rgba(255,255,255,0.95), inset -2px -2px 5px rgba(0,0,0,0.04)",
                border: `1px solid ${isHovered || isActive ? n.color : "rgba(210, 205, 225, 0.55)"}`,
                transition: "box-shadow 0.25s ease, border-color 0.25s ease",
              }}
            >
              <NodeIcon size={17} style={{ color: isHovered || isActive ? n.color : "#9CA3AF", transition: "color 0.2s" }} />
            </div>

            {/* Floating label */}
            {!isActive && (
              <div
                className={`absolute top-1/2 -translate-y-1/2 whitespace-nowrap px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider pointer-events-none border transition-all duration-150 ${labelOnRight ? "left-15" : "right-15"}`}
                style={{
                  opacity: isHovered ? 1 : 0.5,
                  background: isHovered ? "white" : "rgba(255,255,255,0.85)",
                  backdropFilter: "blur(6px)",
                  borderColor: isHovered ? n.color : "rgba(229,231,235,0.7)",
                  color: isHovered ? "#1A1A2E" : "#5B6278",
                }}
              >
                {n.title}
              </div>
            )}

            {/* Info panel */}
            <AnimatePresence>
              {(isHovered || isActive) && (
                <motion.div
                  className={`absolute z-50 p-4 rounded-xl border pointer-events-auto ${labelOnRight ? "left-15" : "right-15"}`}
                  style={{
                    top: "-10px",
                    width: isActive ? "260px" : "180px",
                    background: "rgba(255,255,255,0.96)",
                    backdropFilter: "blur(18px)",
                    borderColor: isActive ? n.color : "rgba(139,92,246,0.13)",
                    boxShadow: isActive
                      ? `0 12px 32px rgba(99,102,241,0.13), 0 4px 10px ${n.glow}`
                      : "0 8px 20px rgba(0,0,0,0.07)",
                  }}
                  initial={{ opacity: 0, scale: 0.92, x: labelOnRight ? -6 : 6 }}
                  animate={{ opacity: 1, scale: 1, x: 0 }}
                  exit={{ opacity: 0, scale: 0.92, x: labelOnRight ? -6 : 6 }}
                  transition={{ duration: 0.18, ease: [0.215, 0.61, 0.355, 1] }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <div className="p-1 rounded-md" style={{ background: n.glow }}>
                      <NodeIcon size={11} style={{ color: n.color }} />
                    </div>
                    <h4 className="text-[11px] font-bold text-[#0A0A0A] uppercase tracking-wide">{n.title}</h4>
                  </div>
                  <p className="text-[11px] leading-relaxed text-[#6B7280]">{isActive ? n.fullDesc : n.shortDesc}</p>
                  {isActive && (
                    <div className="mt-2 pt-2 border-t border-gray-100 flex items-center justify-between text-[9px] text-[#8B5CF6] font-semibold">
                      <span>Active Module</span>
                      <button className="hover:underline" onClick={() => setActiveId(null)}>Dismiss</button>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
