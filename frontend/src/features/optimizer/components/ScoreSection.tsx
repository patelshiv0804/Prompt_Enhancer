'use client';

import React, { useEffect, useState } from 'react';
import { CheckCircle2, AlertTriangle, Minus, TrendingUp } from 'lucide-react';

const DIMENSIONS = [
  { id: 'clarity',     label: 'Clarity',     status: 'good',    icon: CheckCircle2, desc: 'Instructions are direct and unambiguous.',    scoreBefore: 68, scoreAfter: 91 },
  { id: 'context',     label: 'Context',     status: 'good',    icon: CheckCircle2, desc: 'Sufficient background information provided.', scoreBefore: 72, scoreAfter: 88 },
  { id: 'role',        label: 'Role',        status: 'neutral', icon: Minus,        desc: 'No specific persona requested.',              scoreBefore: 32, scoreAfter: 74 },
  { id: 'format',      label: 'Format',      status: 'good',    icon: CheckCircle2, desc: 'Output structure clearly defined.',           scoreBefore: 55, scoreAfter: 90 },
  { id: 'constraints', label: 'Constraints', status: 'warning', icon: AlertTriangle,desc: 'Negative constraints could be stricter.',     scoreBefore: 40, scoreAfter: 77 },
  { id: 'examples',    label: 'Examples',    status: 'neutral', icon: Minus,        desc: 'Zero-shot approach used.',                   scoreBefore: 28, scoreAfter: 65 },
];

function useCountUp(target: number, active: boolean, duration = 1200): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!active) { setValue(0); return; }
    let current = 0;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      current += step;
      if (current >= target) { setValue(target); clearInterval(timer); }
      else setValue(Math.floor(current));
    }, 16);
    return () => clearInterval(timer);
  }, [target, active, duration]);
  return value;
}

function scoreColor(s: number) {
  if (s >= 80) return 'var(--color-success)';
  if (s >= 55) return 'var(--color-primary)';
  return '#F59E0B';
}

function scoreLabel(s: number) {
  if (s >= 90) return 'Excellent';
  if (s >= 75) return 'Good';
  if (s >= 55) return 'Fair';
  return 'Needs Work';
}

const BEFORE_TOTAL = 49;
const AFTER_TOTAL  = 81;

interface ScoreSectionProps { isAnalyzed: boolean; isOptimized: boolean; }

export default function ScoreSection({ isAnalyzed, isOptimized }: ScoreSectionProps) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (isAnalyzed || isOptimized) {
      const t = setTimeout(() => setReady(true), 80);
      return () => clearTimeout(t);
    } else { setReady(false); }
  }, [isAnalyzed, isOptimized]);

  const displayScore      = isOptimized ? AFTER_TOTAL : BEFORE_TOTAL;
  const animatedScore     = useCountUp(displayScore, ready);
  if (!isAnalyzed && !isOptimized) return null;

  const radius            = 48;
  const circumference     = 2 * Math.PI * radius;
  const strokeDashoffset  = circumference - (animatedScore / 100) * circumference;

  const edgeColor = (status: string) => {
    if (status === 'good')    return 'linear-gradient(180deg, var(--color-success), rgba(16,185,129,0.3))';
    if (status === 'warning') return 'linear-gradient(180deg, var(--color-primary), rgba(124,58,237,0.3))';
    return 'transparent';
  };

  const iconColor = (status: string) => {
    if (status === 'good')    return 'var(--color-success)';
    if (status === 'warning') return 'var(--color-primary)';
    return 'var(--color-text-secondary)';
  };

  return (
    <div style={{ width: '100%', marginTop: 32, animation: 'fadeInRise 500ms ease-out forwards' }}>
      <div
        style={{
          display: 'flex', background: '#FFFFFF', border: '1px solid rgba(124,58,237,0.10)',
          borderRadius: 28, boxShadow: '0 4px 24px rgba(109,40,217,0.07), 0 1px 4px rgba(0,0,0,0.04)',
          padding: 32, gap: 40, position: 'relative', overflow: 'hidden',
          transition: 'transform 300ms ease-in-out, box-shadow 300ms ease-in-out',
        }}
        className="hover:translate-y-[-3px] hover:shadow-[0_12px_48px_rgba(109,40,217,0.10),0_4px_12px_rgba(0,0,0,0.05)]"
      >
        {/* Left: Ring */}
        <div style={{
          flex: '0 0 200px', display: 'flex', flexDirection: 'column', alignItems: 'center',
          borderRight: '1px solid rgba(0,0,0,0.07)', paddingRight: 40,
        }}>
          <div style={{ position: 'relative', width: 120, height: 120, marginBottom: 16 }}>
            <svg style={{ transform: 'rotate(-90deg)' }} width="120" height="120">
              <circle cx="60" cy="60" r={radius} fill="none" stroke="rgba(124,58,237,0.10)" strokeWidth="8" />
              <circle
                cx="60" cy="60" r={radius} fill="none"
                stroke="var(--color-primary)" strokeWidth="8" strokeLinecap="round"
                strokeDasharray={circumference} strokeDashoffset={strokeDashoffset}
                style={{ transition: 'stroke-dashoffset 1.5s ease-out', filter: 'drop-shadow(0 0 6px rgba(124,58,237,0.3))' }}
              />
            </svg>
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontSize: 36, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: -1 }}>{animatedScore}</span>
            </div>
          </div>

          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-primary)', marginBottom: 24 }}>
            {scoreLabel(animatedScore)}
          </div>

          {isOptimized && (
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 700,
              color: 'var(--color-success)', background: 'rgba(16,185,129,0.10)',
              border: '1px solid rgba(16,185,129,0.22)', padding: '3px 10px', borderRadius: 9999, marginBottom: 16,
            }}>
              <TrendingUp size={12} />
              <span>+{AFTER_TOTAL - BEFORE_TOTAL} pts</span>
            </div>
          )}

          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {isOptimized ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ color: 'var(--color-text-secondary)' }}>Before</span>
                  <span style={{ fontWeight: 600, color: 'var(--color-text-secondary)' }}>{BEFORE_TOTAL}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ color: 'var(--color-text-secondary)' }}>After</span>
                  <span style={{ fontWeight: 700, color: 'var(--color-success)' }}>{AFTER_TOTAL}</span>
                </div>
              </>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ color: 'var(--color-text-secondary)' }}>Words</span>
                  <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>16</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ color: 'var(--color-text-secondary)' }}>Est. Tokens</span>
                  <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>~24</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right: Dimensions grid */}
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, alignContent: 'start' }}>
          {DIMENSIONS.map(dim => {
            const Icon      = dim.icon;
            const displayed = isOptimized ? dim.scoreAfter : dim.scoreBefore;
            return (
              <div
                key={dim.id}
                style={{
                  background: 'rgba(124,58,237,0.03)', border: '1px solid rgba(124,58,237,0.09)',
                  borderRadius: 12, padding: 16, position: 'relative', overflow: 'hidden',
                  display: 'flex', flexDirection: 'column', gap: 8,
                  transition: 'transform 250ms ease, box-shadow 250ms ease, background 250ms ease',
                }}
                className="hover:translate-y-[-3px] hover:!bg-[rgba(124,58,237,0.05)] hover:shadow-[0_8px_24px_rgba(109,40,217,0.09)]"
              >
                {/* Colored edge bar */}
                <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: 3, borderRadius: '3px 0 0 3px', background: edgeColor(dim.status) }} />

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icon size={15} style={{ color: iconColor(dim.status), flexShrink: 0 }} />
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', flex: 1 }}>{dim.label}</span>
                  <div style={{ marginLeft: 'auto', flexShrink: 0 }}>
                    {isOptimized ? (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 600 }}>
                        <span style={{ color: 'var(--color-text-secondary)', fontWeight: 500 }}>{dim.scoreBefore}</span>
                        <span style={{ color: 'var(--color-text-secondary)', fontSize: 10 }}>→</span>
                        <span style={{ fontWeight: 700, color: scoreColor(dim.scoreAfter) }}>{dim.scoreAfter}</span>
                      </span>
                    ) : (
                      <span style={{ fontSize: 13, fontWeight: 700, color: scoreColor(dim.scoreBefore) }}>{dim.scoreBefore}</span>
                    )}
                  </div>
                </div>

                <div style={{ height: 3, background: 'rgba(124,58,237,0.08)', borderRadius: 99, overflow: 'hidden', margin: '2px 0 4px' }}>
                  <div style={{ height: '100%', borderRadius: 99, width: `${displayed}%`, background: scoreColor(displayed), transition: 'width 0.8s ease-out' }} />
                </div>

                <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.5, margin: 0 }}>{dim.desc}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
