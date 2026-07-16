"use client";
import { useEffect, useRef, useState, useCallback } from "react";

/* ─────────────────────────────────────────────
 * HeroParticleBurst — 3D spherical particle vortex
 * converging into the center icon.
 *
 * Each particle lives on a sphere in 3D space
 * (theta, phi, radius) and spirals inward.
 * Perspective projection gives depth: particles
 * behind the sphere appear smaller & dimmer.
 * Mouse repulsion pushes particles away.
 * ───────────────────────────────────────────── */

interface Particle {
  // 3D spherical coordinates
  theta: number;    // azimuthal angle (around Y axis, 0–2π)
  phi: number;      // polar angle (from top, 0–π)
  r: number;        // distance from center

  // Motion
  thetaSpeed: number;
  phiSpeed: number;
  inwardSpeed: number;

  // Visual
  size: number;
  opacity: number;
  trail: { x: number; y: number; z: number; sx: number; sy: number }[];
  trailLength: number;
  phase: number;

  // Mouse displacement (screen space, decays)
  dx: number;
  dy: number;

  // Cached screen position
  sx: number;
  sy: number;
  sz: number; // depth for sorting & sizing
}

const PARTICLE_COUNT = 30;
const PERSPECTIVE = 600; // camera distance — controls 3D "pop"

// Angle-based color: maps the azimuthal angle to a gradient around the sphere
function colorForAngle(theta: number): string {
  let a = theta % (Math.PI * 2);
  if (a < 0) a += Math.PI * 2;
  const stops: { a: number; c: [number, number, number] }[] = [
    { a: 0,              c: [244, 114, 182] }, // right — pink
    { a: Math.PI * 0.25, c: [251, 146, 110] }, // lower-right — peach
    { a: Math.PI * 0.5,  c: [236, 72, 153]  }, // bottom — hot pink
    { a: Math.PI * 0.75, c: [192, 132, 252] }, // lower-left — light purple
    { a: Math.PI,        c: [167, 139, 250] }, // left — violet
    { a: Math.PI * 1.25, c: [139, 92, 246]  }, // upper-left — deep violet
    { a: Math.PI * 1.5,  c: [129, 140, 248] }, // top — indigo
    { a: Math.PI * 1.75, c: [196, 181, 253] }, // upper-right — lavender
    { a: Math.PI * 2,    c: [244, 114, 182] }, // wrap
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    if (a >= stops[i].a && a <= stops[i + 1].a) {
      const t = (a - stops[i].a) / (stops[i + 1].a - stops[i].a);
      const c1 = stops[i].c;
      const c2 = stops[i + 1].c;
      return `${Math.round(c1[0] + (c2[0] - c1[0]) * t)}, ${Math.round(c1[1] + (c2[1] - c1[1]) * t)}, ${Math.round(c1[2] + (c2[2] - c1[2]) * t)}`;
    }
  }
  return "200, 150, 250";
}

export default function HeroParticleBurst() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const animFrameRef = useRef<number>(0);
  const mouseRef = useRef({ x: 0, y: 0, active: false });
  const sizeRef = useRef({ w: 0, h: 0, cx: 0, cy: 0, sphereR: 0, coreR: 0 });
  const [isVisible, setIsVisible] = useState(true);

  // Intersection Observer to monitor viewport visibility
  useEffect(() => {
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
  }, []);

  const spawnParticle = useCallback((p: Particle) => {
    const { sphereR, coreR } = sizeRef.current;
    // Spawn on the outer shell of the sphere
    p.theta = Math.random() * Math.PI * 2;
    p.phi = Math.acos(2 * Math.random() - 1); // uniform distribution on sphere
    p.r = sphereR * (0.8 + Math.random() * 0.3);

    // Rotation speeds — varying directions for organic swirl
    p.thetaSpeed = (0.002 + Math.random() * 0.008) * (Math.random() > 0.5 ? 1 : -1);
    p.phiSpeed = (0.001 + Math.random() * 0.004) * (Math.random() > 0.5 ? 1 : -1);
    p.inwardSpeed = 0.12 + Math.random() * 0.45;

    p.size = 0.4 + Math.random() * 1.8;
    p.opacity = 0.2 + Math.random() * 0.75;
    p.trail = [];
    p.trailLength = 4 + Math.floor(Math.random() * 6); // reduced from 16 for better speed
    p.phase = Math.random() * Math.PI * 2;
    p.dx = 0;
    p.dy = 0;
    p.sx = 0;
    p.sy = 0;
    p.sz = 0;
    void coreR;
  }, []);

  const initParticles = useCallback(() => {
    const arr: Particle[] = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const p: Particle = {
        theta: 0, phi: 0, r: 0,
        thetaSpeed: 0, phiSpeed: 0, inwardSpeed: 0,
        size: 0, opacity: 0, trail: [], trailLength: 0, phase: 0,
        dx: 0, dy: 0, sx: 0, sy: 0, sz: 0,
      };
      spawnParticle(p);
      // Stagger initial radii so the field is full immediately
      const { sphereR, coreR } = sizeRef.current;
      p.r = coreR + Math.random() * (sphereR - coreR);
      arr.push(p);
    }
    particlesRef.current = arr;
  }, [spawnParticle]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !isVisible) return; // Completely pause and teardown when offscreen
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

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
      const cx = w * 0.5;
      const cy = h * 0.5;
      const sphereR = Math.min(w, h) * 0.44;
      const coreR = Math.min(w, h) * 0.07;
      sizeRef.current = { w, h, cx, cy, sphereR, coreR };
      if (particlesRef.current.length === 0) initParticles();
    };

    resize();
    window.addEventListener("resize", resize);

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top, active: true };
    };
    const handleMouseLeave = () => { mouseRef.current.active = false; };
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    let time = 0;
    // Slow global rotation of the "camera" for constant 3D feel
    let globalRotY = 0;

    const animate = () => {
      const { w, h, cx, cy, sphereR, coreR } = sizeRef.current;
      if (w === 0 || h === 0) {
        animFrameRef.current = requestAnimationFrame(animate);
        return;
      }

      ctx.clearRect(0, 0, w, h);
      time += 0.016;
      globalRotY += 0.0015; // slow overall rotation

      const particles = particlesRef.current;
      const mouse = mouseRef.current;
      const cosGR = Math.cos(globalRotY);
      const sinGR = Math.sin(globalRotY);

      // Update positions
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        // Spiral inward
        p.theta += p.thetaSpeed;
        p.phi += p.phiSpeed;

        // Keep phi bounded — bounce at poles for natural motion
        if (p.phi < 0.15) { p.phi = 0.15; p.phiSpeed = Math.abs(p.phiSpeed); }
        if (p.phi > Math.PI - 0.15) { p.phi = Math.PI - 0.15; p.phiSpeed = -Math.abs(p.phiSpeed); }

        // Accelerate inward as closer to core
        const proximity = 1 - Math.max(0, (p.r - coreR) / (sphereR - coreR));
        p.r -= p.inwardSpeed * (0.5 + proximity * 0.8);

        // Respawn when reaching core
        if (p.r < coreR) {
          spawnParticle(p);
          continue;
        }

        // Convert spherical → 3D cartesian
        const sinPhi = Math.sin(p.phi);
        const cosPhi = Math.cos(p.phi);
        const sinTheta = Math.sin(p.theta);
        const cosTheta = Math.cos(p.theta);

        let x3d = p.r * sinPhi * cosTheta;
        let y3d = p.r * cosPhi;
        let z3d = p.r * sinPhi * sinTheta;

        // Apply global Y-axis rotation for 3D feel
        const rx = x3d * cosGR - z3d * sinGR;
        const rz = x3d * sinGR + z3d * cosGR;
        x3d = rx;
        z3d = rz;

        // Perspective projection
        const depth = PERSPECTIVE + z3d;
        const scale = depth > 10 ? PERSPECTIVE / depth : 0.1;

        let screenX = cx + x3d * scale;
        let screenY = cy + y3d * scale;

        // Decay mouse displacement
        p.dx *= 0.87;
        p.dy *= 0.87;

        // Mouse repulsion (in screen space)
        if (mouse.active) {
          const mdx = screenX + p.dx - mouse.x;
          const mdy = screenY + p.dy - mouse.y;
          const md2 = mdx * mdx + mdy * mdy;
          const R = 120;
          if (md2 < R * R && md2 > 0.01) {
            const d = Math.sqrt(md2);
            const force = (1 - d / R) * 20;
            p.dx += (mdx / d) * force;
            p.dy += (mdy / d) * force;
          }
        }

        screenX += p.dx;
        screenY += p.dy;

        p.sx = screenX;
        p.sy = screenY;
        p.sz = z3d; // store depth for draw order & sizing

        // Trail
        p.trail.unshift({ x: x3d, y: y3d, z: z3d, sx: screenX, sy: screenY });
        if (p.trail.length > p.trailLength) p.trail.pop();
      }

      // Sort by depth — draw far particles first (painter's algorithm)
      const indices = Array.from({ length: particles.length }, (_, i) => i);
      indices.sort((a, b) => particles[a].sz - particles[b].sz);

      // Draw
      for (const idx of indices) {
        const p = particles[idx];
        if (p.r < coreR) continue;

        // Depth-based fade & scale
        const depthVal = PERSPECTIVE + p.sz;
        if (depthVal < 10) continue;
        const depthScale = PERSPECTIVE / depthVal;
        const depthFade = Math.max(0, Math.min(1, (depthVal - 50) / (PERSPECTIVE * 1.5)));

        // Edge fade — fade in/out at spawn/death radius
        const rRatio = (p.r - coreR) / (sphereR - coreR);
        const edgeFade = rRatio > 0.85
          ? (1 - rRatio) / 0.15
          : rRatio < 0.15
          ? rRatio / 0.15
          : 1;

        const drawOpacity = p.opacity * depthFade * Math.max(0, Math.min(1, edgeFade));
        if (drawOpacity < 0.01) continue;

        const drawSize = p.size * depthScale;
        const color = colorForAngle(p.theta);

        // Trail (filament arc)
        if (p.trail.length > 1) {
          ctx.beginPath();
          ctx.moveTo(p.trail[0].sx, p.trail[0].sy);
          for (let t = 1; t < p.trail.length; t++) {
            ctx.lineTo(p.trail[t].sx, p.trail[t].sy);
          }
          ctx.strokeStyle = `rgba(${color}, ${drawOpacity * 0.15})`;
          ctx.lineWidth = drawSize * 0.5;
          ctx.stroke();
        }

        // Outer glow (bigger for "in front" particles)
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, drawSize * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${color}, ${drawOpacity * 0.1})`;
        ctx.fill();

        // Core dot
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, drawSize, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${color}, ${drawOpacity * 0.9})`;
        ctx.fill();

        // Bright center for larger particles
        if (drawSize > 0.8) {
          ctx.beginPath();
          ctx.arc(p.sx, p.sy, drawSize * 0.3, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 255, 255, ${drawOpacity * 0.5})`;
          ctx.fill();
        }
      }

      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);
    return () => {
      cancelAnimationFrame(animFrameRef.current);
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [isVisible, initParticles, spawnParticle]);

  return (
    <div ref={containerRef} className="absolute inset-0 h-full w-full">
      <canvas
        ref={canvasRef}
        className="absolute inset-0 h-full w-full"
        style={{ pointerEvents: "auto" }}
      />
      {/* Center icon — white rounded square with sparkle */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <div
          className="flex h-20 w-20 items-center justify-center rounded-[22px] bg-white"
          style={{ boxShadow: "0 20px 60px -10px rgba(120, 80, 200, 0.35), 0 8px 20px -4px rgba(236, 72, 153, 0.25)" }}
        >
          <svg viewBox="0 0 24 24" className="h-9 w-9" fill="none">
            <path
              d="M12 2 L13.8 9.2 L21 11 L13.8 12.8 L12 20 L10.2 12.8 L3 11 L10.2 9.2 Z"
              fill="#1a1230"
            />
          </svg>
        </div>
      </div>
    </div>
  );
}
