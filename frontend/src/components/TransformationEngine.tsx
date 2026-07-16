"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import RawPromptCard from "./RawPromptCard";
import AIEngine from "./AIEngine";
import AnimatedParticleFlow, {
  ENGINE_CENTER,
  FLOW_WIDTH,
  FLOW_HEIGHT,
} from "./AnimatedParticleFlow";
import OptimizedForCard from "./OptimizedForCard";

/* ─────────────────────────────────────────────
 * TransformationEngine — The second "page" section.
 *
 * Layout:
 *   - Left column: section badge + heading (overlaid)
 *   - Full-width pipeline visualization
 *     Raw Prompt Card → AI Engine → Optimized For Card
 *   - Engine position is derived from the path convergence
 *     point so the hexagon always sits exactly where all
 *     incoming and outgoing particle paths meet.
 * ───────────────────────────────────────────── */

/* Convert SVG-space coordinates to CSS % within the container */
const engineLeftPct = `${(ENGINE_CENTER.x / FLOW_WIDTH) * 100}%`;
const engineTopPct = `${(ENGINE_CENTER.y / FLOW_HEIGHT) * 100}%`;

export default function TransformationEngine() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      { rootMargin: "200px 0px" } // trigger load slightly before it scrolls into view
    );
    const section = sectionRef.current;
    if (section) {
      observer.observe(section);
    }
    return () => {
      if (section) {
        observer.unobserve(section);
      }
      observer.disconnect();
    };
  }, []);

  return (
    <section
      ref={sectionRef}
      className="relative overflow-hidden bg-[#FAFBFC]"
      id="transformation-engine"
      style={{ minHeight: "100vh" }}
    >
      {/* Subtle background gradients */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className="absolute left-[5%] top-[20%] h-[600px] w-[600px] opacity-25"
          style={{
            background:
              "radial-gradient(circle, rgba(139, 92, 246, 0.08) 0%, transparent 70%)",
          }}
        />
        <div
          className="absolute right-[15%] bottom-[10%] h-[500px] w-[500px] opacity-20"
          style={{
            background:
              "radial-gradient(circle, rgba(236, 72, 153, 0.06) 0%, transparent 70%)",
          }}
        />
        <div
          className="absolute right-[5%] top-[30%] h-[400px] w-[400px] opacity-20"
          style={{
            background:
              "radial-gradient(circle, rgba(249, 115, 22, 0.06) 0%, transparent 70%)",
          }}
        />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-[1440px] px-6 py-12 lg:px-12 lg:py-16 flex flex-col items-center">
        {/* ── Centered Header: Section Label + Heading ── */}
        <motion.div
          className="relative z-20 flex flex-col items-center text-center mb-12 max-w-2xl"
          initial={{ opacity: 0, y: -25 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        >
          {/* Section badge */}
          <div className="mb-4 flex items-center gap-2.5">
            <div className="flex h-5 w-5 items-center justify-center rounded-[5px] bg-gradient-to-br from-violet-500 to-purple-600">
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="white"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
              </svg>
            </div>
            <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">
              The Transformation Engine
            </span>
          </div>

          {/* Heading */}
          <h2 className="text-[clamp(32px,3.8vw,46px)] font-extrabold leading-[1.2] tracking-tight text-gray-900">
            One prompt.{" "}
            <span className="gradient-text italic">Optimized everywhere.</span>
          </h2>
        </motion.div>

        {/* ── Full-width AI Visualization Pipeline ── */}
        <motion.div
          className="relative flex w-full items-center justify-center"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.15 }}
          transition={{ delay: 0.2, duration: 1 }}
        >
          {/*
           * The container dimensions match the SVG viewBox exactly (1060×780).
           * All child elements are absolutely positioned so the engine can be
           * placed at the exact convergence point of the path system.
           */}
          <div
            className="relative"
            style={{ width: FLOW_WIDTH, height: FLOW_HEIGHT }}
          >
            {/* Particle flow (SVG overlay — covers full container) */}
            {isVisible && <AnimatedParticleFlow />}

            {/* Top: Raw Prompt Card — centered horizontally at top */}
            <div className="absolute left-1/2 top-2 z-10 -translate-x-1/2">
              <RawPromptCard />
            </div>

            {/* Center: AI Engine — placed at the exact convergence node.
             *  transform: translate(-50%, -50%) centers the hexagon on the point. */}
            <div
              className="absolute z-10"
              style={{
                left: engineLeftPct,
                top: engineTopPct,
                transform: "translate(-50%, -50%)",
              }}
            >
              <AIEngine />
            </div>

            {/* "AI Enhancement Engine" label — positioned to the right of the engine */}
            <motion.div
              className="absolute z-10 flex items-center gap-2"
              style={{
                left: `calc(${engineLeftPct} + 80px)`,
                top: engineTopPct,
                transform: "translateY(-50%)",
              }}
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.8, duration: 0.6 }}
            >
              <svg
                width="60"
                height="38"
                viewBox="0 0 55 35"
                fill="none"
                className="text-gray-300"
              >
                <path
                  d="M2 32 C 12 32, 25 5, 50 5"
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeDasharray="3 3"
                  fill="none"
                />
                <path
                  d="M47 2 L51 5 L47 8"
                  stroke="currentColor"
                  strokeWidth="1"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span
                className="whitespace-nowrap text-[14px] italic text-gray-400"
                style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
              >
                AI Enhancement
                <br />
                Engine
              </span>
            </motion.div>

            {/* Bottom: Optimized For Card — centered horizontally at bottom */}
            <div className="absolute bottom-2 left-1/2 z-10 -translate-x-1/2">
              <OptimizedForCard />
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
