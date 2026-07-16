"use client";

import { motion } from "framer-motion";
import { ArrowRight, Play } from "lucide-react";
import TrustLogos from "./TrustLogos";
import PromptIQUniverse from "./PromptIQUniverse";

export default function Hero() {
  return (
    <section
      id="hero"
      className="relative overflow-hidden bg-white"
      style={{ height: "100vh", minHeight: 640 }}
    >
      {/* ── Full-screen 3D canvas (absolute, fills whole hero) ── */}
      <PromptIQUniverse />

      {/* ── Centered text overlay ── */}
      <div
        className="absolute inset-0 z-[1000] flex flex-col items-center justify-start pointer-events-none"
        style={{ paddingTop: "clamp(32px, 5vh, 60px)" }}
      >
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6 flex items-center gap-2"
        >
          <div className="rounded-full" style={{ width: 6, height: 6, background: "#8B5CF6" }} />
          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.14em", textTransform: "uppercase", color: "#8B5CF6" }}>
            AI-Powered Prompt Intelligence
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          style={{
            fontSize: "clamp(30px, 5vw, 60px)",
            fontWeight: 800,
            lineHeight: 1.05,
            letterSpacing: "-0.025em",
            color: "#0A0A0A",
            margin: 0,
            textAlign: "center",
            maxWidth: 820,
            padding: "0 24px",
          }}
        >
          From rough ideas
          <br />
          to{" "}
          <span style={{
            background: "linear-gradient(135deg, #6366F1 0%, #8B5CF6 40%, #EC4899 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}>
            remarkable
          </span>{" "}results.
        </motion.h1>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="flex flex-wrap items-center justify-center gap-4 pointer-events-auto"
          style={{ marginTop: 34 }}
        >
          <a
            href="#get-started"
            id="hero-cta-primary"
            className="group"
            style={{
              display: "inline-flex", alignItems: "center", gap: 10,
              background: "#0D0D1A", color: "#fff",
              borderRadius: 999, padding: "14px 28px",
              fontSize: 15, fontWeight: 600,
              textDecoration: "none",
              boxShadow: "0 4px 20px rgba(0,0,0,0.15)",
              transition: "all 0.2s ease",
            }}
          >
            Enhance your prompt
            <ArrowRight size={16} />
          </a>
          <a
            href="#how-it-works"
            id="hero-cta-secondary"
            style={{
              display: "inline-flex", alignItems: "center", gap: 10,
              color: "#374151", fontSize: 15, fontWeight: 500,
              textDecoration: "none",
            }}
          >
            <span style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 36, height: 36, borderRadius: "50%",
              border: "1.5px solid #E5E7EB",
              background: "rgba(255,255,255,0.85)",
            }}>
              <Play size={12} style={{ marginLeft: 2, color: "#6B7280" }} />
            </span>
            See how it works
          </a>
        </motion.div>

        {/* Trust logos */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9, duration: 0.7 }}
          className="pointer-events-auto"
        >
          {/* <TrustLogos /> */}
        </motion.div>
      </div>
    </section>
  );
}
