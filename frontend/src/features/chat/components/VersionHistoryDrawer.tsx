'use client';

import React, { useState, useMemo, useRef } from 'react';
import { X, Search, Star, TrendingUp, TrendingDown, Minus, History } from 'lucide-react';

interface VersionHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  versions: {
    versionNumber: number;
    overallScore: number;
    timestamp: string;
    isStarred?: boolean;
    tweakNote?: string;
  }[];
  activeIndex: number;
  onSelect: (index: number) => void;
  onToggleStar: (index: number) => void;
  onHoverVersion?: (index: number | null) => void;
}

function scoreColor(s: number) {
  if (s >= 80) return 'var(--color-success, #10B981)';
  if (s >= 55) return 'var(--color-primary, #7C3AED)';
  return '#F59E0B';
}

export default function VersionHistoryDrawer({
  isOpen, onClose, versions, activeIndex, onSelect, onToggleStar, onHoverVersion,
}: VersionHistoryDrawerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter]           = useState<'all' | 'starred' | 'improved'>('all');
  const [scrollTop, setScrollTop]     = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  const enrichedVersions = useMemo(() =>
    versions.map((v, i) => {
      const prevScore = i > 0 ? versions[i - 1].overallScore : v.overallScore;
      return { ...v, originalIndex: i, delta: v.overallScore - prevScore };
    }).reverse(),
  [versions]);

  const filteredVersions = useMemo(() =>
    enrichedVersions.filter(v => {
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!v.versionNumber.toString().includes(q) && !v.tweakNote?.toLowerCase().includes(q)) return false;
      }
      if (filter === 'starred' && !v.isStarred) return false;
      if (filter === 'improved' && v.delta <= 0) return false;
      return true;
    }),
  [enrichedVersions, searchQuery, filter]);

  const itemHeight       = 72;
  const containerHeight  = 500;
  const totalHeight      = filteredVersions.length * itemHeight;
  const startIndex       = Math.max(0, Math.floor(scrollTop / itemHeight) - 5);
  const endIndex         = Math.min(filteredVersions.length, Math.ceil((scrollTop + containerHeight) / itemHeight) + 5);

  const visibleItems = filteredVersions.slice(startIndex, endIndex).map((v, i) => {
    const realIndex = startIndex + i;
    const isCurrent = v.originalIndex === activeIndex;
    const deltaIcon = v.delta > 0
      ? <TrendingUp size={12} style={{ color: '#10B981' }} />
      : v.delta < 0
      ? <TrendingDown size={12} style={{ color: '#EF4444' }} />
      : <Minus size={12} style={{ color: '#94A3B8' }} />;

    return (
      <div key={v.versionNumber} style={{ position: 'absolute', top: realIndex * itemHeight, width: '100%', height: itemHeight, padding: '0 12px', boxSizing: 'border-box' }}>
        <div
          onClick={() => { onSelect(v.originalIndex); onClose(); }}
          onMouseEnter={() => onHoverVersion?.(v.originalIndex)}
          onMouseLeave={() => onHoverVersion?.(null)}
          style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 12, cursor: 'pointer',
            background: isCurrent ? 'rgba(124,58,237,0.10)' : 'transparent',
            border: isCurrent ? '1px solid rgba(124,58,237,0.20)' : '1px solid transparent',
            transition: 'background 150ms ease, border-color 150ms ease',
            height: 62,
          }}
          className={!isCurrent ? 'hover:!bg-[rgba(124,58,237,0.06)]' : ''}
        >
          <button
            onClick={e => { e.stopPropagation(); onToggleStar(v.originalIndex); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, flexShrink: 0, display: 'flex', alignItems: 'center' }}
          >
            <Star size={15} fill={v.isStarred ? '#F59E0B' : 'transparent'} color={v.isStarred ? '#F59E0B' : 'rgba(100,100,130,0.35)'} />
          </button>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
              <span style={{ fontSize: 13, fontWeight: isCurrent ? 700 : 600, color: isCurrent ? '#6D28D9' : 'rgba(45,27,105,0.85)' }}>
                v{v.versionNumber}
              </span>
              <span style={{ fontSize: 11, color: 'rgba(45,27,105,0.40)', fontWeight: 400 }}>{v.timestamp}</span>
              {isCurrent && <span style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', background: 'rgba(124,58,237,0.14)', color: '#7C3AED', padding: '1px 6px', borderRadius: 4 }}>Current</span>}
            </div>
            {v.tweakNote && <div style={{ fontSize: 11, color: 'rgba(45,27,105,0.55)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{v.tweakNote}</div>}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3, flexShrink: 0 }}>
            <span style={{ fontSize: 16, fontWeight: 800, lineHeight: 1, color: scoreColor(v.overallScore) }}>{v.overallScore}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              {deltaIcon}
              <span style={{ fontSize: 11, fontWeight: 600, color: v.delta > 0 ? '#10B981' : v.delta < 0 ? '#EF4444' : '#94A3B8' }}>
                {v.delta > 0 ? `+${v.delta}` : v.delta}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  });

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(15,5,40,0.40)', backdropFilter: 'blur(2px)', zIndex: 1000 }} />

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 360, zIndex: 1001,
        background: 'rgba(250, 248, 255, 0.97)', backdropFilter: 'blur(24px)',
        borderLeft: '1px solid rgba(124,58,237,0.12)',
        boxShadow: '-8px 0 40px rgba(109,40,217,0.10), -2px 0 8px rgba(0,0,0,0.05)',
        display: 'flex', flexDirection: 'column', animation: 'slideInRight 220ms ease-out',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 20px 16px', borderBottom: '1px solid rgba(124,58,237,0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <History size={16} style={{ color: '#7C3AED' }} />
            <span style={{ fontSize: 15, fontWeight: 700, color: '#2D1B69' }}>Version History</span>
            <span style={{ fontSize: 11, fontWeight: 700, background: 'rgba(124,58,237,0.10)', color: '#7C3AED', padding: '2px 8px', borderRadius: 9999 }}>{versions.length}</span>
          </div>
          <button onClick={onClose} style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 8, border: 'none', cursor: 'pointer', background: 'transparent', color: 'rgba(45,27,105,0.50)' }}
            className="hover:!bg-[rgba(124,58,237,0.08)] hover:!text-[#4C1D95]"
          ><X size={18} /></button>
        </div>

        {/* Filters */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(124,58,237,0.07)', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Search */}
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'rgba(45,27,105,0.40)', pointerEvents: 'none' }} />
            <input type="text" placeholder="Search versions..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              style={{ width: '100%', padding: '8px 12px 8px 32px', fontSize: 13, border: '1px solid rgba(124,58,237,0.14)', borderRadius: 9, outline: 'none', background: '#FFFFFF', color: '#2D1B69', boxSizing: 'border-box' }}
              className="focus:!border-[rgba(124,58,237,0.35)] focus:shadow-[0_0_0_3px_rgba(124,58,237,0.08)]"
            />
          </div>
          {/* Chips */}
          <div style={{ display: 'flex', gap: 6 }}>
            {(['all', 'starred', 'improved'] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                style={{
                  padding: '5px 14px', borderRadius: 9999, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer', transition: 'all 160ms ease', textTransform: 'capitalize',
                  background: filter === f ? 'linear-gradient(135deg, #7C3AED, #A855F7)' : 'rgba(124,58,237,0.07)',
                  color: filter === f ? 'white' : 'rgba(45,27,105,0.65)',
                  boxShadow: filter === f ? '0 3px 8px rgba(124,58,237,0.28)' : 'none',
                }}
              >{f}</button>
            ))}
          </div>
        </div>

        {/* List */}
        <div ref={scrollRef} onScroll={e => setScrollTop(e.currentTarget.scrollTop)}
          style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', scrollbarWidth: 'thin', scrollbarColor: 'rgba(124,58,237,0.18) transparent' }}
        >
          {filteredVersions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 24px', color: 'rgba(45,27,105,0.45)', fontSize: 14 }}>No versions found.</div>
          ) : (
            <div style={{ height: totalHeight, position: 'relative', paddingTop: 8 }}>{visibleItems}</div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes slideInRight { from { transform: translateX(100%); opacity:0; } to { transform: translateX(0); opacity:1; } }
      `}</style>
    </>
  );
}
