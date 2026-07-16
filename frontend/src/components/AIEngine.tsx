"use client";

import React from "react";
import { motion } from "framer-motion";

/* ─────────────────────────────────────────────
 * AIEngine — The orange hexagonal icon at the center
 * of the transformation pipeline. Has a 3D cube icon
 * inside, with radial glow.
 *
 * Performance: Concentric orbit rings and their dots have
 * been removed entirely to maximize performance and simplify
 * the visual interface.
 * ───────────────────────────────────────────── */

const AIEngine = React.memo(function AIEngine() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.6, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      className="relative flex flex-col items-center"
      style={{ willChange: "transform", transform: "translateZ(0)" }}
    >
      {/* Radial glow aura — no CPU/GPU blur filter. Uses smooth multi-stop gradient */}
      <div
        className="absolute -inset-24 opacity-60"
        style={{
          background:
            "radial-gradient(circle, rgba(234,88,12,0.18) 0%, rgba(249,115,22,0.08) 25%, rgba(168,85,247,0.02) 50%, transparent 70%)",
        }}
      />

      {/* Hexagonal orange icon */}
      <div className="relative z-10 flex h-[110px] w-[110px] items-center justify-center">
        {/* Hexagon background */}
        <svg
          width="110"
          height="110"
          viewBox="0 0 72 72"
          fill="none"
          className="absolute inset-0"
        >
          <defs>
            <linearGradient id="hex-gradient" x1="0" y1="0" x2="72" y2="72">
              <stop offset="0%" stopColor="#F97316" />
              <stop offset="50%" stopColor="#EA580C" />
              <stop offset="100%" stopColor="#DC2626" />
            </linearGradient>
            <filter id="hex-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="3" stdDeviation="5" floodColor="#F97316" floodOpacity="0.25" />
            </filter>
          </defs>
          <path
            d="M36 4 L62 18 L62 54 L36 68 L10 54 L10 18 Z"
            fill="url(#hex-gradient)"
            filter="url(#hex-shadow)"
          />
          {/* Inner highlight border */}
          <path
            d="M36 8 L58 20 L58 52 L36 64 L14 52 L14 20 Z"
            fill="none"
            stroke="rgba(255,255,255,0.2)"
            strokeWidth="0.8"
          />
        </svg>

        {/* 3D Cube icon */}
        <svg
          width="42"
          height="42"
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="relative z-10"
        >
          {/* Front face */}
          <path d="M12 2 L22 7 L22 17 L12 22 L2 17 L2 7 Z" />
          {/* Middle horizontal line */}
          <path d="M2 7 L12 12 L22 7" />
          {/* Vertical line */}
          <path d="M12 12 L12 22" />
        </svg>
      </div>
    </motion.div>
  );
});

export default AIEngine;
