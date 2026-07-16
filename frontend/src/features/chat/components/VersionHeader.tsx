'use client';

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { History, Star, ScrollText, Search, X } from 'lucide-react';

interface VersionHeaderProps {
  versions: { versionNumber: number; overallScore: number; timestamp: string; originalIndex?: number }[];
  activeIndex: number;
  bestIndex: number;
  hoveredIndex?: number | null;
  onOpenHistory: () => void;
  onSelectVersion?: (index: number) => void;
  onHoverVersion?: (index: number | null) => void;
}

function scoreColor(s: number) {
  if (s >= 80) return '#10B981';
  if (s >= 55) return '#7C3AED';
  return '#F59E0B';
}

function scoreGradient(s: number) {
  if (s >= 80) return 'linear-gradient(135deg, #10B981, #34D399)';
  if (s >= 55) return 'linear-gradient(135deg, #7C3AED, #A855F7)';
  return 'linear-gradient(135deg, #F59E0B, #FBBF24)';
}

export default function VersionHeader({
  versions, activeIndex, bestIndex, hoveredIndex, onOpenHistory, onSelectVersion, onHoverVersion,
}: VersionHeaderProps) {
  const scrollRef            = useRef<HTMLDivElement>(null);
  const currentBubbleRef     = useRef<HTMLDivElement>(null);
  const bubbleRefsMap        = useRef<Map<number, HTMLDivElement>>(new Map());
  const [atStart, setAtStart] = useState(true);
  const [atEnd,   setAtEnd]   = useState(false);
  const [searchQuery,    setSearchQuery]    = useState('');
  const [searchMatch,    setSearchMatch]    = useState<number | null>(null);
  const [searchNotFound, setSearchNotFound] = useState(false);

  const activeVersion = versions[activeIndex];
  if (!activeVersion) return null;

  /* Auto-scroll to current bubble */
  useEffect(() => {
    const t = setTimeout(() => {
      if (currentBubbleRef.current && scrollRef.current) {
        const c = scrollRef.current;
        const b = currentBubbleRef.current;
        const scrollLeft = b.offsetLeft - c.offsetLeft - c.getBoundingClientRect().width / 2 + b.getBoundingClientRect().width / 2;
        c.scrollTo({ left: Math.max(0, scrollLeft), behavior: 'smooth' });
      }
    }, 10);
    return () => clearTimeout(t);
  }, [activeIndex]);

  /* Search */
  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
    setSearchNotFound(false);
    setSearchMatch(null);
    if (!query.trim()) return;
    const num = parseInt(query.replace(/^[vV]/, ''), 10);
    if (isNaN(num)) return;
    const idx = versions.findIndex(v => v.versionNumber === num);
    if (idx === -1) { setSearchNotFound(true); return; }
    setSearchMatch(idx);
    const el = bubbleRefsMap.current.get(idx);
    if (el && scrollRef.current) {
      const c = scrollRef.current;
      c.scrollTo({ left: Math.max(0, el.offsetLeft - c.offsetLeft - c.getBoundingClientRect().width / 2 + el.offsetWidth / 2), behavior: 'smooth' });
    }
  }, [versions]);

  const clearSearch = useCallback(() => { setSearchQuery(''); setSearchMatch(null); setSearchNotFound(false); }, []);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    setAtStart(el.scrollLeft <= 4);
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 4);
  }, []);

  useEffect(() => { handleScroll(); }, [handleScroll, versions.length]);

  const activeColor = scoreColor(activeVersion.overallScore);

  /* Build strip bubbles */
  const stripElements: React.ReactNode[] = [];
  versions.forEach((bubble, idx) => {
    const v         = bubble as typeof bubble & { originalIndex?: number };
    const isCurrent = idx === activeIndex;
    const isBest    = idx === bestIndex;
    const isHovered = hoveredIndex !== null && idx === hoveredIndex;
    const isSearched = searchMatch === idx;

    if (idx > 0) {
      stripElements.push(
        <div
          key={`conn-${idx}`}
          style={{
            width: 28,
            height: 2.5,
            background: 'linear-gradient(to right, rgba(167, 139, 250, 0.35), rgba(167, 139, 250, 0.55))',
            flexShrink: 0,
            alignSelf: 'center',
            marginTop: -16,
            borderRadius: 2,
            transition: 'background 200ms ease',
          }}
        />
      );
    }

    const dotColor = isCurrent
      ? 'white'
      : isBest
      ? '#FBBF24'
      : isHovered
      ? '#ffffff'
      : 'rgba(255, 255, 255, 0.9)';

    const dotBg = isCurrent
      ? 'linear-gradient(135deg, #7C3AED, #A855F7)'
      : isBest
      ? 'rgba(245, 158, 11, 0.1)'
      : isHovered
      ? 'rgba(167, 139, 250, 0.25)'
      : 'rgba(167, 139, 250, 0.15)';

    const dotBorder = isCurrent
      ? '2px solid transparent'
      : isBest
      ? '2px solid #F59E0B'
      : isSearched
      ? '2px solid #60D8FA'
      : isHovered
      ? '2px solid rgba(167, 139, 250, 0.7)'
      : '2px solid rgba(167, 139, 250, 0.45)';

    const dotBoxShadow = isCurrent
      ? '0 6px 24px rgba(124, 58, 237, 0.45)'
      : isSearched
      ? '0 0 0 3px rgba(96, 216, 250, 0.20), 0 4px 20px rgba(96, 216, 250, 0.30)'
      : isHovered
      ? '0 4px 20px rgba(124, 58, 237, 0.4)'
      : 'none';

    stripElements.push(
      <div
        key={`bubble-${idx}`}
        ref={el => {
          if (el) bubbleRefsMap.current.set(idx, el);
          if (isCurrent && el) (currentBubbleRef as React.MutableRefObject<HTMLDivElement>).current = el;
        }}
        onClick={() => onSelectVersion?.(v.originalIndex !== undefined ? v.originalIndex : idx)}
        onMouseEnter={() => onHoverVersion?.(v.originalIndex !== undefined ? v.originalIndex : idx)}
        onMouseLeave={() => onHoverVersion?.(null)}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 4,
          cursor: 'pointer',
          position: 'relative',
          flexShrink: 0,
          padding: '0 2px',
          userSelect: 'none',
          transition: 'transform 200ms ease',
        }}
        className="hover:translate-y-[-3px]"
      >
        {/* Tooltip */}
        <div style={{
          position: 'absolute', bottom: 'calc(100% + 10px)', left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(30, 16, 53, 0.95)', color: 'white', borderRadius: 10, padding: '6px 12px',
          fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap', pointerEvents: 'none',
          opacity: isHovered || isSearched ? 1 : 0, transition: 'opacity 150ms ease', zIndex: 10,
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35), 0 2px 6px rgba(124, 58, 237, 0.15)',
          border: '1px solid rgba(167, 139, 250, 0.25)',
        }}>
          v{bubble.versionNumber}
          <span style={{ marginLeft: 4, color: '#A78BFA' }}>· {bubble.overallScore}</span>
          <span style={{ marginLeft: 6, color: 'rgba(255, 255, 255, 0.35)', fontWeight: 400 }}>{bubble.timestamp}</span>
        </div>

        {/* Best star */}
        {isBest && (
          <span style={{ position: 'absolute', top: -6, right: -6, zIndex: 2 }}>
            <Star size={10} fill="#F59E0B" color="#F59E0B" />
          </span>
        )}

        {/* Circle dot */}
        <div style={{
          width: 44, height: 44,
          borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 700,
          color: dotColor,
          background: dotBg,
          border: dotBorder,
          boxShadow: dotBoxShadow,
          transform: isCurrent ? 'scale(1.18)' : 'scale(1)',
          transition: 'all 200ms ease',
        }}>
          {bubble.overallScore}
        </div>

        {/* Version label below */}
        <span style={{
          fontSize: 11,
          fontWeight: 600,
          color: isCurrent ? '#C4B5FD' : isHovered ? 'rgba(255, 255, 255, 0.95)' : 'rgba(255, 255, 255, 0.65)',
          letterSpacing: '0.2px',
          transform: isCurrent ? 'scale(1.1)' : 'scale(1)',
          transition: 'all 200ms ease',
        }}>
          v{bubble.versionNumber}
        </span>
        {isCurrent && <span style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.6px', color: '#C4B5FD' }}>Current</span>}
        {isBest && !isCurrent && <span style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.6px', color: '#FCD34D' }}>Best</span>}
        {isSearched && !isCurrent && <span style={{ fontSize: 9, fontWeight: 700, color: '#60D8FA' }}>Found</span>}
      </div>
    );
  });

  return (
    <div style={{
      background: 'linear-gradient(135deg, #1E1035 0%, #2D1B69 40%, #1A0F2E 100%)',
      borderRadius: 18, padding: '20px 24px 18px', marginBottom: 16,
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.25), 0 2px 8px rgba(109, 40, 217, 0.15), inset 0 1px 0 rgba(167, 139, 250, 0.1)',
      border: '1px solid rgba(167, 139, 250, 0.15)',
      position: 'relative', overflow: 'visible',
    }}>
      {/* Ambient glow */}
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 0%, rgba(167, 139, 250, 0.15) 0%, transparent 70%)', pointerEvents: 'none' }} />

      {/* Top Row */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        {/* Badge group */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(255, 255, 255, 0.08)', border: '1px solid rgba(167, 139, 250, 0.2)', borderRadius: 20, padding: '5px 14px', fontSize: 13, fontWeight: 600, color: 'rgba(255, 255, 255, 0.9)', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05)' }}>
            v{activeVersion.versionNumber} <span style={{ color: 'rgba(167, 139, 250, 0.5)' }}>·</span> Current
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: activeColor, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', boxShadow: '0 0 6px currentColor' }} />
            Score: {activeVersion.overallScore}
          </div>
        </div>

        {/* Version search */}
        <div style={{
          position: 'relative', display: 'flex', alignItems: 'center',
          background: searchNotFound ? 'rgba(239, 68, 68, 0.12)' : searchMatch !== null ? 'rgba(96, 216, 250, 0.12)' : 'rgba(255, 255, 255, 0.07)',
          border: `1px solid ${searchNotFound ? 'rgba(239, 68, 68, 0.5)' : searchMatch !== null ? 'rgba(96, 216, 250, 0.5)' : 'rgba(167, 139, 250, 0.20)'}`,
          borderRadius: 24, padding: '6px 12px', transition: 'all 250ms ease', width: 240,
        }}>
          <Search size={12} style={{ position: 'absolute', left: 12, color: searchNotFound ? 'rgba(239, 68, 68, 0.8)' : searchMatch !== null ? 'rgba(167, 139, 250, 1)' : 'rgba(196, 181, 253, 0.6)' }} />
          <input
            type="text" placeholder="Jump to version… v3, v46" value={searchQuery}
            onChange={e => handleSearch(e.target.value)} spellCheck={false}
            style={{
              padding: '0 18px 0 20px', fontSize: 12, fontWeight: 500, background: 'transparent',
              border: 'none', outline: 'none', color: 'rgba(255, 255, 255, 0.9)', width: '100%', letterSpacing: '0.2px',
            }}
          />
          {searchQuery && (
            <button onClick={clearSearch} style={{ position: 'absolute', right: 10, background: 'rgba(255, 255, 255, 0.10)', border: 'none', borderRadius: '50%', cursor: 'pointer', color: 'rgba(255, 255, 255, 0.5)', display: 'flex', width: 18, height: 18, alignItems: 'center', justifyContent: 'center', padding: 0 }}>
              <X size={11} />
            </button>
          )}
        </div>

        {/* All Drafts button */}
        <button onClick={onOpenHistory} style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '7px 16px',
          background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(167, 139, 250, 0.15)',
          borderRadius: 10, fontSize: 13, fontWeight: 600, color: 'rgba(255, 255, 255, 0.7)', cursor: 'pointer',
          transition: 'all 250ms ease', whiteSpace: 'nowrap', boxShadow: '0 2px 6px rgba(0, 0, 0, 0.15)',
        }} className="hover:!bg-[rgba(167,139,250,0.12)] hover:!text-[#A78BFA] hover:!border-[rgba(167,139,250,0.35)] hover:shadow-[0_4px_16px_rgba(124,58,237,0.2)] hover:translate-y-[-1px]">
          <ScrollText size={14} />
          <span>All Drafts ({versions.length})</span>
        </button>
      </div>

      {/* Journey strip */}
      <div style={{ position: 'relative' }}>
        {/* Left fade */}
        {!atStart && <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 40, background: 'linear-gradient(to right, #1E1035, transparent)', zIndex: 5, pointerEvents: 'none' }} />}
        {/* Right fade */}
        {!atEnd && <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 40, background: 'linear-gradient(to left, #1A0F2E, transparent)', zIndex: 5, pointerEvents: 'none' }} />}

        <div
          ref={scrollRef} onScroll={handleScroll}
          style={{
            display: 'flex', alignItems: 'center', gap: 0, overflowX: 'auto', overflowY: 'visible',
            paddingBottom: 16, paddingTop: 40,
            scrollbarWidth: 'none', msOverflowStyle: 'none',
          }}
        >
          {stripElements}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 14, marginTop: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255, 255, 255, 0.5)', minWidth: 36 }}>Score</span>
        <div style={{ flex: 1, height: 6, background: 'rgba(255, 255, 255, 0.08)', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${activeVersion.overallScore}%`, background: scoreGradient(activeVersion.overallScore), borderRadius: 99, transition: 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)', position: 'relative' }} />
        </div>
        <span style={{ fontSize: 14, fontWeight: 800, color: 'white', minWidth: 28, textAlign: 'right' }}>{activeVersion.overallScore}</span>
        <span style={{ fontSize: 10, color: 'rgba(255, 255, 255, 0.35)', whiteSpace: 'nowrap' }}>
          +{activeVersion.overallScore - versions[0].overallScore} from v1
        </span>
      </div>
    </div>
  );
}
