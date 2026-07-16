"use client";

import { motion } from "framer-motion";

const logos = [
  { name: "Notion", svg: <NotionLogo /> },
  { name: "Vercel", svg: <VercelLogo /> },
  { name: "Linear", svg: <LinearLogo /> },
  { name: "Canva", svg: <CanvaLogo /> },
  { name: "Spotify", svg: <SpotifyLogo /> },
  { name: "Adobe", svg: <AdobeLogo /> },
];

export default function TrustLogos() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 1, duration: 0.8 }}
      className="mt-14"
    >
      <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.2em] text-gray-400">
        Trusted by thinkers &amp; builders
      </p>
      <div className="flex flex-nowrap items-center gap-4 opacity-40">
        {logos.map((logo) => (
          <div
            key={logo.name}
            className="flex shrink-0 items-center gap-1 text-gray-500 transition-opacity duration-300 hover:opacity-70"
            title={logo.name}
          >
            {logo.svg}
          </div>
        ))}
      </div>
    </motion.div>
  );
}

/* ── Inline SVG logos (grayscale, minimal, compact) ── */

function NotionLogo() {
  return (
    <div className="flex items-center gap-1">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
        <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L18.28 2.39c-.42-.326-.98-.7-2.055-.607L3.01 2.87c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.84-.046.933-.56.933-1.167V6.354c0-.606-.233-.933-.746-.886l-15.177.886c-.56.047-.747.327-.747.934zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.747 0-.933-.234-1.494-.934l-4.577-7.186v6.952L12.21 19s0 .84-1.168.84l-3.222.187c-.093-.187 0-.653.327-.746l.84-.234V9.854L7.822 9.76c-.094-.42.14-1.026.793-1.073l3.456-.234 4.764 7.28v-6.44l-1.354-.14c-.093-.514.28-.886.747-.933zM2.83 1.634l13.728-.933c1.681-.14 2.1.093 2.8.607l3.876 2.707c.467.327.607.746.607 1.26v14.49c0 1.027-.373 1.634-1.68 1.727L7.168 22.46c-.98.047-1.448-.093-1.962-.747l-3.13-4.06c-.56-.747-.793-1.307-.793-1.96V3.294c0-.84.374-1.54 1.541-1.66z" />
      </svg>
      <span className="text-xs font-semibold">Notion</span>
    </div>
  );
}

function VercelLogo() {
  return (
    <div className="flex items-center gap-1">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 1L24 22H0L12 1Z" />
      </svg>
      <span className="text-xs font-semibold">Vercel</span>
    </div>
  );
}

function LinearLogo() {
  return (
    <div className="flex items-center gap-1">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <path d="M2.886 21.114a1.5 1.5 0 0 1 0-2.122L19.992 1.886a1.5 1.5 0 0 1 2.122 2.122L4.008 21.114a1.5 1.5 0 0 1-2.122 0zm3.336-2.672a1.5 1.5 0 0 1 0-2.122l11.22-11.22a1.5 1.5 0 0 1 2.122 2.122l-11.22 11.22a1.5 1.5 0 0 1-2.122 0zM9.558 15.106a1.5 1.5 0 0 1 0-2.122l4.548-4.548a1.5 1.5 0 0 1 2.122 2.122l-4.548 4.548a1.5 1.5 0 0 1-2.122 0z" />
      </svg>
      <span className="text-xs font-semibold">Linear</span>
    </div>
  );
}

function CanvaLogo() {
  return (
    <div className="flex items-center gap-1">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="4" fill="white" />
      </svg>
      <span className="text-xs font-semibold">Canva</span>
    </div>
  );
}

function SpotifyLogo() {
  return (
    <div className="flex items-center gap-1">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
      </svg>
      <span className="text-xs font-semibold">Spotify</span>
    </div>
  );
}

function AdobeLogo() {
  return (
    <div className="flex items-center gap-1">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <path d="M9.07 0H0v21.87L9.07 0zM14.93 0H24v21.87L14.93 0zM12 8.15l4.62 13.08h-3.07l-1.39-4.13H8.77L12 8.15z" />
      </svg>
      <span className="text-xs font-semibold">Adobe</span>
    </div>
  );
}
