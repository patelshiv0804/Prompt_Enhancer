"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, useInView, Variants } from "framer-motion";

// Upward Arrow Icon component (↗)
const ArrowUpRight = ({ className = "text-emerald-400" }: { className?: string }) => (
  <svg
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    className={`inline-block ml-1 align-baseline ${className}`}
  >
    <line x1="7" y1="17" x2="17" y2="7" strokeLinecap="round" strokeLinejoin="round" />
    <polyline points="7 7 17 7 17 17" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// Number animation component using requestAnimationFrame for smooth spring-like count up
function AnimatedScore({ from, to, delay = 0 }: { from: number; to: number; delay?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, amount: 0.1 });
  const [count, setCount] = useState(from);

  useEffect(() => {
    if (!isInView) return;

    let startTimestamp: number | null = null;
    let timer: number;
    const duration = 1.0; // 1 second duration

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const elapsed = (timestamp - startTimestamp) / 1000;
      const progress = Math.min(elapsed, duration);

      // easeOutExpo for spring-like deceleration count up
      const easeProgress = progress === duration ? 1 : 1 - Math.pow(2, -10 * progress);
      const currentCount = Math.floor(from + easeProgress * (to - from));
      setCount(currentCount);

      if (progress < duration) {
        timer = window.requestAnimationFrame(step);
      } else {
        setCount(to);
      }
    };

    const delayTimer = setTimeout(() => {
      timer = window.requestAnimationFrame(step);
    }, delay * 1000);

    return () => {
      clearTimeout(delayTimer);
      if (timer) window.cancelAnimationFrame(timer);
    };
  }, [isInView, from, to, delay]);

  return <span ref={ref}>{count}</span>;
}

// 6 Dimensions Data Configuration
const dimensions = [
  {
    name: "Clarity",
    from: 78,
    to: 96,
    gradient: "from-[#A78BFA] to-[#60A5FA]", // Lavender -> Soft Blue
    arrowColor: "text-[#A78BFA]", // Lavender
  },
  {
    name: "Context",
    from: 60,
    to: 92,
    gradient: "from-[#EC4899] to-[#A78BFA]", // Pink -> Lavender
    arrowColor: "text-[#A78BFA]",
  },
  {
    name: "Role",
    from: 45,
    to: 90,
    gradient: "from-[#8B5CF6] to-[#C4B5FD]", // Purple -> Light Violet
    arrowColor: "text-[#A78BFA]",
  },
  {
    name: "Format",
    from: 50,
    to: 88,
    gradient: "from-[#A78BFA] to-[#EC4899]", // Lavender -> Pink
    arrowColor: "text-[#A78BFA]",
  },
  {
    name: "Constraints",
    from: 40,
    to: 86,
    gradient: "from-[#60A5FA] to-[#A78BFA]", // Soft Blue -> Lavender
    arrowColor: "text-[#A78BFA]",
  },
  {
    name: "Examples",
    from: 30,
    to: 80,
    gradient: "from-[#EC4899] to-[#8B5CF6]", // Pink -> Purple
    arrowColor: "text-[#A78BFA]",
  },
];


export default function PromptTransformationShowcase() {
  const [copied, setCopied] = useState(false);
  const enhancedText = "Write a compelling product launch announcement for our AI-powered productivity tool. Highlight the key benefits, who it's for, and what makes it unique. Keep it engaging, concise, and action-oriented.";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(enhancedText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  // Entry animation variants
  const containerVariants: Variants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: 0.15,
      },
    },
  };

  const leftContentVariants: Variants = {
    hidden: { opacity: 0, y: 35 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.7,
        ease: [0.22, 1, 0.36, 1],
      },
    },
  };

  const consoleVariants: Variants = {
    hidden: { opacity: 0, y: 35 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.8,
        ease: [0.22, 1, 0.36, 1],
      },
    },
  };

  const panelVariants: Variants = {
    hidden: { opacity: 0, y: 35 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.8,
        ease: [0.22, 1, 0.36, 1],
        staggerChildren: 0.1,
      },
    },
  };

  const columnVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.6,
        ease: [0.22, 1, 0.36, 1],
      },
    },
  };


  return (
    <section className="w-full bg-[#FAFBFC] pb-20 px-6 md:px-12 lg:px-16" id="transformation-showcase">
      <motion.div
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.25 }}
        className="mx-auto max-w-[1320px] rounded-[32px] bg-[#05050A] border border-white/[0.06] overflow-hidden relative p-8 md:p-14 lg:p-20 shadow-[0_24px_80px_rgba(0,0,0,0.5)]"
      >
        {/* Subtle noise/grain texture */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.015] mix-blend-overlay">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <filter id="noiseFilter">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.8"
                numOctaves="3"
                stitchTiles="stitch"
              />
            </filter>
            <rect width="100%" height="100%" filter="url(#noiseFilter)" />
          </svg>
        </div>

        {/* Soft radial glow with slight purple tint */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at 65% 50%, rgba(139, 92, 246, 0.15) 0%, rgba(99, 102, 241, 0.05) 45%, transparent 80%)",
          }}
        />

        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-[4fr_6fr] gap-12 lg:gap-16 items-center">
          {/* LEFT COLUMN */}
          <motion.div variants={leftContentVariants} className="flex flex-col items-start">
            <span className="text-[11px] font-bold tracking-[0.22em] text-white/40 uppercase">
              SEE THE TRANSFORMATION
            </span>
            <h2 className="text-[clamp(32px,4.5vw,46px)] font-semibold text-white tracking-tight leading-[1.1] mt-5 mb-6">
              Better prompts.
              <br />
              Better outcomes.
            </h2>

            <div className="mt-12 flex flex-col items-start w-full">
              <p className="text-[18px] leading-relaxed text-gray-400/80 mb-8 max-w-sm">
                Our AI analyzes your prompt across<br />
                6 key dimensions and transforms it<br />
                for maximum impact.
              </p>
            </div>
          </motion.div>

          {/* RIGHT COLUMN */}
          <div className="flex flex-col gap-6 md:gap-8 w-full">
            {/* Unified macOS console window */}
            <motion.div
              variants={consoleVariants}
              className="w-full"
            >
              <motion.div
                animate={{ y: [0, -6, 0] }}
                transition={{
                  duration: 6,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
                className="w-full bg-[#08080E]/60 border border-white/[0.08] rounded-[22px] overflow-hidden shadow-[0_30px_70px_rgba(0,0,0,0.65),0_0_50px_rgba(139,92,246,0.05)] backdrop-blur-xl relative"
              >
                {/* Header bar */}
                <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.06] bg-[#07070B]/85 select-none">
                  {/* Traffic lights */}
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#FF5F56]/15" />
                    <div className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#FFBD2E]/15" />
                    <div className="w-3 h-3 rounded-full bg-[#27C93F] border border-[#27C93F]/15" />
                  </div>
                  {/* Window title */}
                  <div className="text-[12px] font-mono text-white/40 tracking-wider">
                    prompt-transformer.sh
                  </div>
                  {/* Status Indicator */}
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
                    <span className="text-[10px] font-mono text-white/30 uppercase tracking-wider">active</span>
                  </div>
                </div>

                {/* Content grid */}
                <div className="relative grid grid-cols-1 md:grid-cols-2 gap-0 items-stretch">
                  
                  {/* Desktop Center Arrow Button */}
                  <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-20 hidden md:flex h-10 w-10 items-center justify-center rounded-full bg-white text-gray-900 shadow-[0_4px_25px_rgba(139,92,246,0.4)] border border-white/[0.08] hover:scale-110 active:scale-95 transition-transform duration-200 cursor-pointer">
                    <span className="text-lg font-bold select-none">→</span>
                  </div>

                  {/* LEFT PANE: Your prompt (Input) */}
                  <div className="p-6 md:p-8 flex flex-col justify-between bg-[#08080C]/20">
                    <div>
                      <div className="flex items-center gap-2.5 mb-5">
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          className="text-white/50"
                        >
                          <polyline points="4 17 10 11 4 5" strokeLinecap="round" strokeLinejoin="round" />
                          <line x1="12" y1="19" x2="20" y2="19" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <span className="text-[13px] font-medium text-white/80 font-mono">Your prompt</span>
                      </div>

                      <div className="bg-[#030307]/50 border border-white/[0.04] rounded-xl p-5 text-[14px] leading-relaxed text-white/70 min-h-[140px] font-sans">
                        Write a product launch announcement.
                      </div>
                    </div>

                    <div className="text-[11px] text-white/30 font-mono mt-6">
                      28/1000
                    </div>
                  </div>

                  {/* Mobile Divider Arrow (DOM flow) */}
                  <div className="flex md:hidden justify-center items-center my-[-18px] z-20 pointer-events-none">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-gray-900 shadow-[0_4px_15px_rgba(139,92,246,0.35)] border border-white/[0.08] pointer-events-auto active:scale-95 transition-transform">
                      <span className="text-md font-bold select-none rotate-90 leading-none">→</span>
                    </div>
                  </div>

                  {/* RIGHT PANE: Enhanced prompt (Output) */}
                  <div className="p-6 md:p-8 flex flex-col justify-between bg-[#08080C]/40 border-t border-white/[0.06] md:border-t-0 md:border-l border-white/[0.06]">
                    <div>
                      <div className="flex items-center justify-between mb-5">
                        <div className="flex items-center gap-2.5">
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            className="text-[#A78BFA]"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M9.813 15.904L9 21l-.813-5.096L3.096 15 8 14.187 8.813 9.096 9.813 14.19 14.9 15l-5.09 1.096z"
                            />
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M19.071 4.929l-.26 1.63L17.18 6.82l1.63.26.26 1.63.26-1.63 1.63-.26-1.63-.26-.26-1.63z"
                            />
                          </svg>
                          <span className="text-[13px] font-medium text-white/80 font-mono">Enhanced prompt</span>
                        </div>

                        {/* Copy Button */}
                        <button
                          onClick={handleCopy}
                          className="flex items-center gap-1.5 text-[11px] text-white/60 hover:text-white transition-colors cursor-pointer bg-white/5 hover:bg-white/10 px-2.5 py-1.5 rounded-lg border border-white/[0.06] active:scale-95"
                        >
                          {copied ? (
                            <>
                              <svg
                                width="12"
                                height="12"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                className="text-green-400"
                              >
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                              <span className="text-green-400 font-medium">Copied!</span>
                            </>
                          ) : (
                            <>
                              <svg
                                width="12"
                                height="12"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                              </svg>
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>

                      <div className="bg-[#030307]/60 border border-[#8B5CF6]/20 shadow-[0_0_15px_rgba(139,92,246,0.06)] rounded-xl p-5 text-[14px] leading-relaxed text-white/90 font-sans">
                        {enhancedText}
                      </div>
                    </div>

                    {/* Bottom tags */}
                    <div className="flex flex-wrap gap-2 mt-6">
                      <span className="text-[10.5px] font-semibold tracking-wider px-3 py-1 rounded-full border bg-blue-500/10 border-blue-500/20 text-[#60A5FA]">
                        Clearer
                      </span>
                      <span className="text-[10.5px] font-semibold tracking-wider px-3 py-1 rounded-full border bg-purple-500/10 border-purple-500/20 text-[#C084FC]">
                        Context rich
                      </span>
                      <span className="text-[10.5px] font-semibold tracking-wider px-3 py-1 rounded-full border bg-pink-500/10 border-pink-500/20 text-[#F472B6]">
                        Actionable
                      </span>
                      <span className="text-[10.5px] font-semibold tracking-wider px-3 py-1 rounded-full border bg-orange-500/10 border-orange-500/20 text-[#FB923C]">
                        Impactful
                      </span>
                    </div>
                  </div>

                </div>
              </motion.div>
            </motion.div>

            {/* 6-Dimensional Analysis Panel */}
            <motion.div
              variants={panelVariants}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.15 }}
              className="w-full bg-white/[0.02] border border-white/[0.08] backdrop-blur-md rounded-[20px] p-6 md:py-6 md:px-8 shadow-[0_20px_50px_rgba(0,0,0,0.35)] relative overflow-hidden"
            >
              {/* Subtle noise/grain texture inside panel */}
              <div className="absolute inset-0 pointer-events-none opacity-[0.015] mix-blend-overlay">
                <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
                  <filter id="panelNoiseFilter">
                    <feTurbulence
                      type="fractalNoise"
                      baseFrequency="0.8"
                      numOctaves="3"
                      stitchTiles="stitch"
                    />
                  </filter>
                  <rect width="100%" height="100%" filter="url(#panelNoiseFilter)" />
                </svg>
              </div>

              <span className="relative z-10 text-[13px] font-medium text-white/90 mb-5 block">
                6-Dimensional Analysis
              </span>

              <div className="relative z-10 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-y-6 lg:gap-y-0 w-full">
                {dimensions.map((dim, idx) => (
                  <motion.div
                    key={dim.name}
                    variants={columnVariants}
                    className="flex flex-col border-white/[0.06] lg:border-r lg:last:border-r-0 lg:px-3.5 xl:px-6 lg:first:pl-0 lg:last:pr-0"
                  >
                    <span className="text-[10px] font-semibold tracking-wider text-[#94A3B8] uppercase mb-1.5">
                      {dim.name}
                    </span>
                    <div className="flex items-center">
                      <span className="text-[14px] text-[#F8FAFC]/50 font-medium">{dim.from}</span>
                      <span className="text-[14px] text-[#94A3B8]/20 mx-1.5">→</span>
                      <span className="text-[16px] text-[#F8FAFC] font-semibold min-w-[20px]">
                        <AnimatedScore from={dim.from} to={dim.to} delay={idx * 0.1 + 0.2} />
                      </span>
                      <ArrowUpRight className={dim.arrowColor} />
                    </div>

                    {/* Progress Bar Container */}
                    <div className="relative w-full h-[4px] bg-white/5 rounded-full mt-3 overflow-visible">
                      {/* Glow Behind */}
                      <motion.div
                        initial={{ width: 0 }}
                        whileInView={{ width: `${dim.to}%` }}
                        viewport={{ once: true }}
                        transition={{
                          duration: 1.0,
                          ease: [0.25, 1, 0.5, 1], // easeOut
                          delay: idx * 0.1 + 0.2,
                        }}
                        className={`absolute top-0 left-0 h-full rounded-full blur-[4px] opacity-12 bg-gradient-to-r ${dim.gradient}`}
                      />
                      {/* Active Progress */}
                      <motion.div
                        initial={{ width: 0 }}
                        whileInView={{ width: `${dim.to}%` }}
                        viewport={{ once: true }}
                        transition={{
                          duration: 1.0,
                          ease: [0.25, 1, 0.5, 1], // easeOut
                          delay: idx * 0.1 + 0.2,
                        }}
                        className={`absolute top-0 left-0 h-full rounded-full bg-gradient-to-r ${dim.gradient} z-10`}
                      />
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
