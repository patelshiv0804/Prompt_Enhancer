"use client";

import { motion } from "framer-motion";

const stats = [
  {
    id: "stat-prompts",
    value: "10M+",
    label: "Prompts enhanced",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" strokeWidth="1.8">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
    iconBg: "rgba(139,92,246,0.1)",
  },
  {
    id: "stat-users",
    value: "500K+",
    label: "Happy users",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#EC4899" strokeWidth="1.8">
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
      </svg>
    ),
    iconBg: "rgba(236,72,153,0.1)",
  },
  {
    id: "stat-uptime",
    value: "99.9%",
    label: "Uptime",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="1.8">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
    iconBg: "rgba(99,102,241,0.1)",
  },
  {
    id: "stat-support",
    value: "24/7",
    label: "AI Support",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#60A5FA" strokeWidth="1.8">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
    iconBg: "rgba(96,165,250,0.1)",
  },
];

export default function StatsSection() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      style={{
        padding: "0 32px 48px",
      }}
      id="stats-section"
    >
      <div
        style={{
          maxWidth: 1000,
          margin: "0 auto",
          background: "#fff",
          borderRadius: 24,
          boxShadow:
            "0 2px 4px rgba(0,0,0,0.02), 0 8px 32px rgba(0,0,0,0.06), 0 1px 2px rgba(99,102,241,0.06)",
          border: "1px solid rgba(0,0,0,0.05)",
          display: "flex",
          overflow: "hidden",
        }}
      >
        {stats.map((stat, i) => (
          <div
            key={stat.id}
            id={stat.id}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              gap: 16,
              padding: "28px 32px",
              borderRight: i < stats.length - 1 ? "1px solid rgba(0,0,0,0.06)" : "none",
            }}
          >
            {/* Icon */}
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: stat.iconBg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              {stat.icon}
            </div>

            {/* Text */}
            <div>
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 800,
                  color: "#0A0A0A",
                  lineHeight: 1,
                  letterSpacing: "-0.02em",
                  marginBottom: 4,
                }}
              >
                {stat.value}
              </div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: "#9CA3AF",
                }}
              >
                {stat.label}
              </div>
            </div>
          </div>
        ))}
      </div>
    </motion.section>
  );
}
