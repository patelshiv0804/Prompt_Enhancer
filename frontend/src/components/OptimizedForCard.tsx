"use client";

import React from "react";
import { motion } from "framer-motion";

/* ─────────────────────────────────────────────
 * OptimizedForCard — Shows all target AI platforms
 * in a single horizontal row matching the reference
 * image layout. 10 icons across.
 *
 * Performance: React.memo prevents scroll re-renders.
 * Icon hover uses CSS transitions instead of Framer
 * Motion whileHover (eliminates 10 motion nodes).
 * ───────────────────────────────────────────── */

const apps = [
  { name: "ChatGPT", icon: <ChatGPTIcon /> },
  { name: "Claude", icon: <ClaudeIcon /> },
  { name: "Gemini", icon: <GeminiIcon /> },
  { name: "Midjourney", icon: <MidjourneyIcon /> },
  { name: "VEO", icon: <VEOIcon /> },
  { name: "Grok", icon: <GrokIcon /> },
  { name: "Perplexity", icon: <PerplexityIcon /> },
  { name: "Cursor", icon: <CursorIcon /> },
  { name: "Stable Diffusion", icon: <StableDiffusionIcon /> },
  { name: "DALL·E", icon: <DallEIcon /> },
];

const OptimizedForCard = React.memo(function OptimizedForCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.8, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      className="animate-float-delayed"
    >
      <div className="w-full max-w-[1000px] rounded-[20px] border border-gray-200/60 bg-white/90 px-8 py-6 shadow-[0_2px_24px_rgba(0,0,0,0.06)] backdrop-blur-sm">
        {/* Header */}
        <div className="mb-4 flex items-center gap-2.5">
          <div className="h-[7px] w-[7px] rounded-full bg-red-400" />
          <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-red-400">
            Optimized For
          </span>
        </div>

        {/* Single row of icons */}
        <div className="flex items-center justify-between gap-2">
          {apps.map((app) => (
            <div
              key={app.name}
              className="group flex cursor-pointer flex-col items-center gap-2 rounded-xl p-3 transition-transform duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.08] hover:bg-gray-50"
            >
              <div className="flex h-14 w-14 items-center justify-center rounded-xl border border-gray-100 bg-white shadow-sm transition-shadow duration-200 group-hover:shadow-md">
                {app.icon}
              </div>
              <span className="text-center text-[10px] font-medium leading-tight text-gray-400 transition-colors duration-200 group-hover:text-gray-600">
                {app.name}
              </span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
});

export default OptimizedForCard;

function ChatGPTIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="#10A37F">
      <path d="M22.28 9.82a5.99 5.99 0 0 0-.52-4.91 6.05 6.05 0 0 0-6.51-2.9A6.07 6.07 0 0 0 4.98 4.18a6 6 0 0 0-4 2.9 6.04 6.04 0 0 0 .74 7.1 5.98 5.98 0 0 0 .51 4.91 6.05 6.05 0 0 0 6.52 2.9A5.99 5.99 0 0 0 13.26 24a6.06 6.06 0 0 0 5.77-4.21 5.99 5.99 0 0 0 4-2.9 6.06 6.06 0 0 0-.75-7.07zM13.26 22.43a4.48 4.48 0 0 1-2.88-1.04l.14-.08 4.78-2.76a.8.8 0 0 0 .39-.68v-6.74l2.02 1.17a.07.07 0 0 1 .04.05v5.58a4.5 4.5 0 0 1-4.49 4.5zM3.6 18.3a4.47 4.47 0 0 1-.54-3.01l.14.08 4.78 2.76a.77.77 0 0 0 .78 0l5.84-3.37v2.33a.08.08 0 0 1-.03.06L9.74 19.95a4.5 4.5 0 0 1-6.14-1.65zM2.34 7.9a4.49 4.49 0 0 1 2.37-1.97V11.6a.77.77 0 0 0 .39.68l5.81 3.35-2.02 1.17a.08.08 0 0 1-.07 0l-4.83-2.79A4.5 4.5 0 0 1 2.34 7.87zm16.6 3.86l-5.83-3.39L15.12 7.2a.08.08 0 0 1 .07 0l4.83 2.79a4.49 4.49 0 0 1-.68 8.1v-5.68a.79.79 0 0 0-.4-.66zm2.01-3.02l-.14-.09-4.77-2.78a.78.78 0 0 0-.79 0L9.41 9.23V6.9a.07.07 0 0 1 .03-.06l4.83-2.79a4.5 4.5 0 0 1 6.68 4.66zM8.31 12.86l-2.02-1.16a.08.08 0 0 1-.04-.06V6.08a4.5 4.5 0 0 1 7.38-3.45l-.14.08-4.78 2.76a.8.8 0 0 0-.39.68zm1.1-2.37l2.6-1.5 2.61 1.5v3l-2.6 1.5-2.61-1.5z" />
    </svg>
  );
}

function ClaudeIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="#D4A574">
      <path d="M16.98 3.39l-6.2 17.21h-2.2L14.77 3.39h2.21zm-6.47 0L4.29 20.6H2.09L8.3 3.39h2.21z" />
    </svg>
  );
}

function GeminiIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
      <path d="M14 0C14 7.73 7.73 14 0 14c7.73 0 14 6.27 14 14 0-7.73 6.27-14 14-14C20.27 14 14 7.73 14 0z" fill="#4285F4" />
    </svg>
  );
}

function MidjourneyIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <path d="M4 20h2l4-14h1l2 8 2-8h1l4 14h2" stroke="#000" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function VEOIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <polygon points="8,4 20,12 8,20" fill="#EA4335" />
    </svg>
  );
}

function GrokIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="#000">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function PerplexityIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <path d="M12 2v20M2 12h20M5.6 5.6l12.8 12.8M18.4 5.6L5.6 18.4" stroke="#000" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function CursorIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="#000">
      <path d="M13 2L4.09 12.63a1 1 0 0 0 .77 1.63H11v5.5a.5.5 0 0 0 .9.3L20.91 9.37a1 1 0 0 0-.77-1.63H14V2.5a.5.5 0 0 0-.9-.3z" />
    </svg>
  );
}

function StableDiffusionIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="#A855F7" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="4" fill="#A855F7" />
      <circle cx="12" cy="3" r="1.5" fill="#A855F7" />
      <circle cx="12" cy="21" r="1.5" fill="#A855F7" />
      <circle cx="3" cy="12" r="1.5" fill="#A855F7" />
      <circle cx="21" cy="12" r="1.5" fill="#A855F7" />
    </svg>
  );
}

function DallEIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="#10A37F">
      <path d="M22.28 9.82a5.99 5.99 0 0 0-.52-4.91 6.05 6.05 0 0 0-6.51-2.9A6.07 6.07 0 0 0 4.98 4.18a6 6 0 0 0-4 2.9 6.04 6.04 0 0 0 .74 7.1 5.98 5.98 0 0 0 .51 4.91 6.05 6.05 0 0 0 6.52 2.9A5.99 5.99 0 0 0 13.26 24a6.06 6.06 0 0 0 5.77-4.21 5.99 5.99 0 0 0 4-2.9 6.06 6.06 0 0 0-.75-7.07z" />
      <circle cx="12" cy="12" r="3" fill="white" />
    </svg>
  );
}
