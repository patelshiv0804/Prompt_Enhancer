"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";

/* ─────────────────────────────────────────────
 * AnimatedParticleFlow — CANVAS REWRITE
 *
 * 1. Single HTML5 Canvas element: Eliminates all SVG paths, tags,
 *    animateMotion, and nested groups. Reduces DOM node count to a single node.
 *
 * 2. Canvas Bezier Math: Resolves points along cubic Bezier curves in JS,
 *    rendering paths and particles natively.
 *
 * 3. Passive Scroll Throttling: During scroll events, freezes particle movement
 *    and throttles draw rate to 15 FPS. Automatically resumes full 60 FPS 
 *    motion after 150ms of no scrolling.
 *
 * 4. Offscreen loop cancellation: IntersectionObserver halts the requestAnimationFrame
 *    loop entirely when off-screen.
 * ───────────────────────────────────────────── */

export const ENGINE_CENTER = { x: 530, y: 415 };
export const FLOW_WIDTH = 1060;
export const FLOW_HEIGHT = 780;

const CX = ENGINE_CENTER.x;
const CY = ENGINE_CENTER.y;

interface Point {
  x: number;
  y: number;
}

interface BezierCurve {
  p0: Point;
  p1: Point;
  p2: Point;
  p3: Point;
}

interface PathConfig {
  id: string;
  curves: BezierCurve[];
  color: string;
  duration: number;
  delay: number;
  particleCount: number;
  baseOpacity?: number;
  primaryOpacity?: number;
  secondaryOpacity?: number;
}

const PATHS: PathConfig[] = [
  // ─── Top card → AI Engine (exactly 5 input paths) ───
  {
    id: "t-far-left",
    color: "#A855F7", duration: 5, delay: 0, particleCount: 1,
    curves: [
      { p0: { x: 370, y: 115 }, p1: { x: 310, y: 160 }, p2: { x: 200, y: 230 }, p3: { x: 190, y: 290 } },
      { p0: { x: 190, y: 290 }, p1: { x: 180, y: 350 }, p2: { x: 350, y: 390 }, p3: { x: CX, y: CY } }
    ]
  },
  {
    id: "t-center-left",
    color: "#EC4899", duration: 4, delay: 0.5, particleCount: 1,
    curves: [
      { p0: { x: 445, y: 115 }, p1: { x: 435, y: 170 }, p2: { x: 415, y: 260 }, p3: { x: 445, y: 330 } },
      { p0: { x: 445, y: 330 }, p1: { x: 465, y: 370 }, p2: { x: 498, y: 400 }, p3: { x: CX, y: CY } }
    ]
  },
  {
    id: "t-center",
    color: "#c026d3", duration: 3.5, delay: 0.2, particleCount: 2,
    baseOpacity: 0.3,
    primaryOpacity: 0.6,
    secondaryOpacity: 0.4,
    curves: [
      { p0: { x: CX, y: 115 }, p1: { x: CX, y: 200 }, p2: { x: CX, y: 310 }, p3: { x: CX, y: CY } }
    ]
  },
  {
    id: "t-center-right",
    color: "#60A5FA", duration: 4, delay: 0.4, particleCount: 1,
    curves: [
      { p0: { x: 615, y: 115 }, p1: { x: 625, y: 170 }, p2: { x: 645, y: 260 }, p3: { x: 615, y: 330 } },
      { p0: { x: 615, y: 330 }, p1: { x: 595, y: 370 }, p2: { x: 562, y: 400 }, p3: { x: CX, y: CY } }
    ]
  },
  {
    id: "t-far-right",
    color: "#A855F7", duration: 5, delay: 0.6, particleCount: 1,
    curves: [
      { p0: { x: 690, y: 115 }, p1: { x: 755, y: 160 }, p2: { x: 860, y: 230 }, p3: { x: 870, y: 290 } },
      { p0: { x: 870, y: 290 }, p1: { x: 880, y: 350 }, p2: { x: 715, y: 390 }, p3: { x: CX, y: CY } }
    ]
  },

  // ─── AI Engine → Model Icons (exactly 10 output paths) ───
  {
    id: "b-chatgpt",
    color: "#A855F7", duration: 4.5, delay: 0, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 500, y: 455 }, p2: { x: 260, y: 520 }, p3: { x: 160, y: 570 } },
      { p0: { x: 160, y: 570 }, p1: { x: 110, y: 600 }, p2: { x: 102, y: 640 }, p3: { x: 102, y: 680 } }
    ]
  },
  {
    id: "b-claude",
    color: "#EC4899", duration: 4.2, delay: 0.3, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 505, y: 453 }, p2: { x: 320, y: 520 }, p3: { x: 240, y: 565 } },
      { p0: { x: 240, y: 565 }, p1: { x: 208, y: 590 }, p2: { x: 198, y: 640 }, p3: { x: 197, y: 680 } }
    ]
  },
  {
    id: "b-gemini",
    color: "#60A5FA", duration: 4.0, delay: 0.5, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 510, y: 453 }, p2: { x: 380, y: 525 }, p3: { x: 330, y: 565 } },
      { p0: { x: 330, y: 565 }, p1: { x: 305, y: 590 }, p2: { x: 294, y: 640 }, p3: { x: 292, y: 680 } }
    ]
  },
  {
    id: "b-midjourney",
    color: "#A855F7", duration: 3.8, delay: 0.7, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 518, y: 455 }, p2: { x: 430, y: 530 }, p3: { x: 405, y: 570 } },
      { p0: { x: 405, y: 570 }, p1: { x: 392, y: 600 }, p2: { x: 388, y: 645 }, p3: { x: 387, y: 680 } }
    ]
  },
  {
    id: "b-veo",
    color: "#EC4899", duration: 3.5, delay: 0.2, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 525, y: 455 }, p2: { x: 495, y: 535 }, p3: { x: 488, y: 575 } },
      { p0: { x: 488, y: 575 }, p1: { x: 484, y: 610 }, p2: { x: 482, y: 650 }, p3: { x: 482, y: 680 } }
    ]
  },
  {
    id: "b-grok",
    color: "#60A5FA", duration: 3.5, delay: 0.4, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 535, y: 455 }, p2: { x: 565, y: 535 }, p3: { x: 572, y: 575 } },
      { p0: { x: 572, y: 575 }, p1: { x: 576, y: 610 }, p2: { x: 578, y: 650 }, p3: { x: 578, y: 680 } }
    ]
  },
  {
    id: "b-perplexity",
    color: "#A855F7", duration: 3.8, delay: 0.6, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 542, y: 455 }, p2: { x: 630, y: 530 }, p3: { x: 655, y: 570 } },
      { p0: { x: 655, y: 570 }, p1: { x: 668, y: 600 }, p2: { x: 672, y: 645 }, p3: { x: 673, y: 680 } }
    ]
  },
  {
    id: "b-cursor",
    color: "#EC4899", duration: 4.0, delay: 0.8, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 550, y: 453 }, p2: { x: 680, y: 525 }, p3: { x: 730, y: 565 } },
      { p0: { x: 730, y: 565 }, p1: { x: 755, y: 590 }, p2: { x: 766, y: 640 }, p3: { x: 768, y: 680 } }
    ]
  },
  {
    id: "b-stable-diffusion",
    color: "#60A5FA", duration: 4.2, delay: 0.1, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 555, y: 453 }, p2: { x: 740, y: 520 }, p3: { x: 820, y: 565 } },
      { p0: { x: 820, y: 565 }, p1: { x: 855, y: 590 }, p2: { x: 862, y: 640 }, p3: { x: 863, y: 680 } }
    ]
  },
  {
    id: "b-dalle",
    color: "#A855F7", duration: 4.5, delay: 0.9, particleCount: 1,
    curves: [
      { p0: { x: CX, y: CY }, p1: { x: 560, y: 455 }, p2: { x: 800, y: 520 }, p3: { x: 900, y: 570 } },
      { p0: { x: 900, y: 570 }, p1: { x: 950, y: 600 }, p2: { x: 958, y: 640 }, p3: { x: 958, y: 680 } }
    ]
  }
];

/* ── Bezier curve mathematics ── */

function getCubicBezierPoint(t: number, p0: Point, p1: Point, p2: Point, p3: Point): Point {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const mt3 = mt2 * mt;
  const t2 = t * t;
  const t3 = t2 * t;

  return {
    x: mt3 * p0.x + 3 * mt2 * t * p1.x + 3 * mt * t2 * p2.x + t3 * p3.x,
    y: mt3 * p0.y + 3 * mt2 * t * p1.y + 3 * mt * t2 * p2.y + t3 * p3.y,
  };
}

function getPointOnPath(u: number, curves: BezierCurve[]): Point {
  const n = curves.length;
  if (n === 1) {
    return getCubicBezierPoint(u, curves[0].p0, curves[0].p1, curves[0].p2, curves[0].p3);
  }
  if (u < 0.5) {
    return getCubicBezierPoint(u * 2, curves[0].p0, curves[0].p1, curves[0].p2, curves[0].p3);
  } else {
    return getCubicBezierPoint(u * 2 - 1, curves[1].p0, curves[1].p1, curves[1].p2, curves[1].p3);
  }
}

/* ── Main Canvas Component ── */

function AnimatedParticleFlowInner() {
  const [mounted, setMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameIdRef = useRef<number>(0);
  const isScrollingRef = useRef(false);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Intersection Observer to monitor viewport visibility
  useEffect(() => {
    if (!mounted) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      { threshold: 0 }
    );
    const container = containerRef.current;
    if (container) {
      observer.observe(container);
    }
    return () => {
      if (container) {
        observer.unobserve(container);
      }
      observer.disconnect();
    };
  }, [mounted]);

  // Pre-calculate particles once to prevent garbage collection overhead
  const particles = useMemo(() => {
    return PATHS.flatMap(path => {
      return Array.from({ length: path.particleCount }, (_, i) => {
        const duration = path.duration + i * 0.6;
        const delay = path.delay + i * (path.duration / path.particleCount);
        const size = 3 - i * 0.4;
        return {
          pathCurves: path.curves,
          color: path.color,
          dur: duration,
          delay: delay,
          size: size
        };
      });
    });
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !isVisible) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let active = true;
    let lastTimestamp = 0;
    let time = 0;

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      const dpr = window.devicePixelRatio || 1;
      const w = rect.width;
      const h = rect.height;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();
    window.addEventListener("resize", resize);

    // Scroll listener to throttle FPS to 15 and pause simulation
    let scrollTimeout: number;
    const handleScroll = () => {
      isScrollingRef.current = true;
      window.clearTimeout(scrollTimeout);
      scrollTimeout = window.setTimeout(() => {
        isScrollingRef.current = false;
      }, 150);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });

    const tick = (timestamp: number) => {
      if (!active) return;
      animFrameIdRef.current = requestAnimationFrame(tick);

      const elapsed = timestamp - lastTimestamp;
      const fpsLimit = isScrollingRef.current ? 66.7 : 16.7; // 15 FPS vs 60 FPS

      if (elapsed >= fpsLimit) {
        lastTimestamp = timestamp - (elapsed % fpsLimit);

        // Advance simulation time only when not scrolling (pauses animations)
        if (!isScrollingRef.current) {
          time += 0.016;
        }

        const dpr = window.devicePixelRatio || 1;
        const w = canvas.width / dpr;
        const h = canvas.height / dpr;
        const scaleX = w / FLOW_WIDTH;
        const scaleY = h / FLOW_HEIGHT;

        ctx.clearRect(0, 0, w, h);
        ctx.save();
        ctx.scale(scaleX, scaleY);

        // 1. Draw Paths (dashes & glow)
        PATHS.forEach(path => {
          const primaryDashOffset = (time / path.duration) * -300;
          const secondaryDashOffset = (time / (path.duration * 0.7)) * -220;

          // Helper to create Bezier paths
          const makePath = () => {
            ctx.beginPath();
            ctx.moveTo(path.curves[0].p0.x, path.curves[0].p0.y);
            path.curves.forEach(c => {
              ctx.bezierCurveTo(c.p1.x, c.p1.y, c.p2.x, c.p2.y, c.p3.x, c.p3.y);
            });
          };

          // Dotted guide line
          ctx.strokeStyle = path.color;
          ctx.globalAlpha = path.baseOpacity ?? 0.08;
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 5]);
          ctx.lineDashOffset = 0;
          makePath();
          ctx.stroke();

          // Secondary animated dash flow
          ctx.strokeStyle = path.color;
          ctx.globalAlpha = path.secondaryOpacity ?? 0.12;
          ctx.lineWidth = 0.8;
          ctx.setLineDash([2, 15]);
          ctx.lineDashOffset = secondaryDashOffset;
          makePath();
          ctx.stroke();

          // Primary animated dash — Core and Glow
          ctx.strokeStyle = path.color;
          ctx.setLineDash([3, 10]);
          ctx.lineDashOffset = primaryDashOffset;

          // Dash glow (larger width, low opacity, no expensive blur filters)
          ctx.lineWidth = 3.5;
          ctx.globalAlpha = (path.primaryOpacity ?? 0.25) * 0.35;
          makePath();
          ctx.stroke();

          // Dash core
          ctx.lineWidth = 1.5;
          ctx.globalAlpha = path.primaryOpacity ?? 0.25;
          makePath();
          ctx.stroke();
        });

        // 2. Draw Moving Particles
        particles.forEach(p => {
          const elapsed = time - p.delay;
          if (elapsed >= 0) {
            const progress = (elapsed / p.dur) % 1;
            const eased = progress < 0.5
              ? 2 * progress * progress
              : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            const point = getPointOnPath(eased, p.pathCurves);

            // Large outer glow halo
            ctx.beginPath();
            ctx.arc(point.x, point.y, p.size * 2.2, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.globalAlpha = 0.12;
            ctx.fill();

            // Core particle body
            ctx.beginPath();
            ctx.arc(point.x, point.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.globalAlpha = 0.85;
            ctx.fill();

            // Bright white center highlight
            ctx.beginPath();
            ctx.arc(point.x, point.y, p.size * 0.35, 0, Math.PI * 2);
            ctx.fillStyle = "white";
            ctx.globalAlpha = 0.7;
            ctx.fill();
          }
        });

        ctx.restore();
      }
    };

    animFrameIdRef.current = requestAnimationFrame(tick);

    return () => {
      active = false;
      cancelAnimationFrame(animFrameIdRef.current);
      window.removeEventListener("resize", resize);
      window.removeEventListener("scroll", handleScroll);
      window.clearTimeout(scrollTimeout);
    };
  }, [isVisible, particles]);

  if (!mounted) {
    return <div style={{ width: FLOW_WIDTH, height: FLOW_HEIGHT }} />;
  }

  return (
    <div
      ref={containerRef}
      className="pointer-events-none absolute inset-0 z-0"
      style={{
        willChange: "transform",
        transform: "translateZ(0)",
        contain: "layout style paint",
      }}
    >
      <canvas
        ref={canvasRef}
        className="h-full w-full"
      />
    </div>
  );
}

const AnimatedParticleFlow = React.memo(AnimatedParticleFlowInner);
export default AnimatedParticleFlow;