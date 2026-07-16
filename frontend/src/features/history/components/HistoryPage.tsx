'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search, Star, MoreHorizontal, FileText, Code2, PlaySquare, Mail, Film,
  Image as ImageIcon, ChevronLeft, ChevronRight, Megaphone, BookOpen,
  Sparkles, TrendingUp, SlidersHorizontal, ChevronDown, Zap, Clock,
  Trash2, ExternalLink, Copy,
} from 'lucide-react';
import { fetchHistory, fetchHistoryStats, toggleFavorite, deleteHistoryItem } from '../services/historyService';
import type { HistoryItem, HistoryStats, SortBy } from '../types/history.types';

const PAGE_SIZE = 8;

const FILTER_CATEGORIES = [
  { id: 'all', label: 'All' }, { id: 'favorites', label: '★ Favorites' }, { id: 'general', label: 'General' },
  { id: 'coding', label: 'Coding' }, { id: 'research', label: 'Research' }, { id: 'marketing', label: 'Marketing' },
  { id: 'cinematic', label: 'Cinematic' }, { id: 'youtube', label: 'YouTube' }, { id: 'image-gen', label: 'Image Gen' },
];

const SORT_OPTIONS: { id: SortBy; label: string }[] = [
  { id: 'most-recent', label: 'Most Recent' }, { id: 'highest-score', label: 'Highest Score' },
  { id: 'lowest-score', label: 'Lowest Score' }, { id: 'oldest', label: 'Oldest' },
];

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  coding: Code2, research: Search, marketing: Megaphone, storytelling: BookOpen,
  'image-gen': ImageIcon, cinematic: Film, youtube: PlaySquare, seo: TrendingUp, general: Sparkles, email: Mail,
};
const CATEGORY_ACCENTS: Record<string, string> = {
  coding: '#0EA5E9', research: '#8B5CF6', marketing: '#10B981', storytelling: '#F59E0B',
  'image-gen': '#EC4899', cinematic: '#8B5CF6', youtube: '#EF4444', seo: '#10B981', general: '#7C3AED', email: '#0EA5E9',
};

function timeAgo(isoString: string): string {
  const diff  = Date.now() - new Date(isoString).getTime();
  const mins  = Math.floor(diff / 60_000);
  const hours = Math.floor(mins / 60);
  const days  = Math.floor(hours / 24);
  if (mins < 1)   return 'just now';
  if (mins < 60)  return `${mins}m ago`;
  if (hours < 24) return `${hours} hours ago`;
  if (days === 1) return 'Yesterday';
  if (days < 7)   return `${days} days ago`;
  return new Date(isoString).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function scoreColor(score: number): string {
  if (score >= 90) return '#10B981';
  if (score >= 80) return '#7C3AED';
  if (score >= 65) return '#F59E0B';
  return '#EF4444';
}

function useCountUp(target: number, active: boolean, duration = 1200): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!active || target === 0) return;
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

/* ── StatCard ── */
interface StatCardProps {
  label: string; value: number; suffix?: string; prefix?: string;
  icon: React.ElementType; accent: string; sub?: React.ReactNode; sparkline?: boolean; animate: boolean;
}

function StatCard({ label, value, suffix = '', prefix = '', icon: Icon, accent, sub, sparkline, animate }: StatCardProps) {
  const count = useCountUp(value, animate);
  return (
    <div style={{
      background: '#FFFFFF', border: '1px solid rgba(124,58,237,0.10)', borderRadius: 16, padding: '20px 24px',
      flex: '1 1 0', minWidth: 0, boxShadow: '0 4px 12px rgba(109,40,217,0.06), 0 1px 3px rgba(0,0,0,0.04)',
      display: 'flex', flexDirection: 'column', gap: 8, transition: 'transform 250ms ease, box-shadow 250ms ease',
    }}
    className="hover:translate-y-[-2px] hover:shadow-[0_8px_24px_rgba(109,40,217,0.09),0_2px_6px_rgba(0,0,0,0.05)]"
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.9px', color: 'var(--color-text-secondary)' }}>{label}</span>
        <div style={{ width: 28, height: 28, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: accent, background: `${accent}18` }}>
          <Icon size={14} strokeWidth={2} />
        </div>
      </div>
      <div style={{ fontSize: 32, fontWeight: 800, color: accent, letterSpacing: -1, lineHeight: 1 }}>
        {prefix}{count.toLocaleString()}{suffix}
      </div>
      {sub && <div style={{ marginTop: 4 }}>{sub}</div>}
      {sparkline && (
        <svg viewBox="0 0 90 28" preserveAspectRatio="none" style={{ width: '100%', height: 28, marginTop: 8 }}>
          <polyline points="0,24 12,20 22,22 34,12 46,16 58,8 70,10 80,5 90,3" fill="none" stroke={accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </div>
  );
}

/* ── HistoryRow ── */
function HistoryRow({ item, onToggleFavorite, onDelete }: { item: HistoryItem; onToggleFavorite: (id: string, current: boolean) => void; onDelete: (id: string) => void; }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const Icon    = CATEGORY_ICONS[item.category] || FileText;
  const accent  = CATEGORY_ACCENTS[item.category] || '#7C3AED';

  useEffect(() => {
    function close(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  return (
    <div id={`history-row-${item.id}`} style={{
      display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px',
      background: menuOpen ? 'rgba(124,58,237,0.04)' : '#FFFFFF',
      border: '1px solid rgba(124,58,237,0.09)', borderRadius: 14,
      transition: 'background 200ms ease, box-shadow 200ms ease, border-color 200ms ease',
      position: 'relative',
    }}
    className="hover:!bg-[rgba(124,58,237,0.03)] hover:shadow-[0_4px_16px_rgba(109,40,217,0.07)] hover:!border-[rgba(124,58,237,0.15)]"
    >
      <div style={{ width: 38, height: 38, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', color: accent, background: `${accent}14`, border: `1px solid ${accent}22`, flexShrink: 0 }}>
        <Icon size={16} strokeWidth={1.6} />
      </div>

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <p style={{ margin: 0, fontSize: 14, fontWeight: 500, color: 'var(--color-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.prompt}</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--color-text-secondary)' }}>
          <Clock size={11} strokeWidth={1.5} />
          <span>{timeAgo(item.createdAt)}</span>
          <span style={{ opacity: 0.3 }}>·</span>
          <span style={{ fontWeight: 500 }}>{item.targetModel}</span>
          <span style={{ opacity: 0.3 }}>·</span>
          <span style={{ fontWeight: 500 }}>{item.mode}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, flexShrink: 0 }}>
        <span style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--color-text-secondary)', opacity: 0.6 }}>Score</span>
        <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1, color: scoreColor(item.score) }}>{item.score}</span>
      </div>

      <button id={`star-btn-${item.id}`} onClick={() => onToggleFavorite(item.id, item.isFavorite)} title={item.isFavorite ? 'Remove from favorites' : 'Add to favorites'}
        style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '50%', border: 'none', cursor: 'pointer', background: 'transparent', color: item.isFavorite ? '#F59E0B' : 'rgba(107,107,138,0.40)', transition: 'all 200ms ease', flexShrink: 0 }}
        className="hover:!bg-[rgba(245,158,11,0.10)] hover:!text-[#F59E0B] hover:scale-110"
      >
        <Star size={15} strokeWidth={item.isFavorite ? 0 : 1.5} fill={item.isFavorite ? 'currentColor' : 'none'} />
      </button>

      <div style={{ position: 'relative', flexShrink: 0 }} ref={menuRef}>
        <button id={`more-btn-${item.id}`} onClick={() => setMenuOpen(v => !v)}
          style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '50%', border: 'none', cursor: 'pointer', background: 'transparent', color: 'rgba(107,107,138,0.50)', transition: 'all 200ms ease' }}
          className="hover:!bg-[rgba(124,58,237,0.08)] hover:!text-[var(--color-primary)]"
        >
          <MoreHorizontal size={16} strokeWidth={1.5} />
        </button>
        {menuOpen && (
          <div id={`row-dropdown-${item.id}`} style={{
            position: 'absolute', top: 'calc(100% + 4px)', right: 0, background: '#FFFFFF',
            border: '1px solid rgba(124,58,237,0.10)', borderRadius: 10, minWidth: 170,
            overflow: 'hidden', zIndex: 50, boxShadow: '0 8px 24px rgba(109,40,217,0.10), 0 2px 8px rgba(0,0,0,0.06)',
            animation: 'dropdownFadeIn 150ms ease',
          }}>
            {[
              { icon: ExternalLink, label: 'Open in Optimizer', danger: false, onClick: () => {} },
              { icon: Copy, label: 'Copy Prompt', danger: false, onClick: () => { navigator.clipboard.writeText(item.prompt); setMenuOpen(false); } },
            ].map(({ icon: Icon2, label, onClick }) => (
              <button key={label} onClick={onClick}
                style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '9px 14px', fontSize: 13, color: 'var(--color-text-primary)', border: 'none', cursor: 'pointer', background: 'transparent', textAlign: 'left' }}
                className="hover:bg-[rgba(124,58,237,0.05)]"
              ><Icon2 size={13} strokeWidth={1.8} />{label}</button>
            ))}
            <div style={{ height: 1, background: 'rgba(124,58,237,0.08)', margin: '4px 0' }} />
            <button onClick={() => { setMenuOpen(false); onDelete(item.id); }}
              style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '9px 14px', fontSize: 13, color: '#EF4444', border: 'none', cursor: 'pointer', background: 'transparent', textAlign: 'left' }}
              className="hover:bg-[rgba(239,68,68,0.06)]"
            ><Trash2 size={13} strokeWidth={1.8} />Delete</button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Pagination ── */
function Pagination({ currentPage, totalPages, onPageChange }: { currentPage: number; totalPages: number; onPageChange: (p: number) => void; }) {
  const pages: (number | '…')[] = [];
  if (totalPages <= 7) { for (let i = 1; i <= totalPages; i++) pages.push(i); }
  else {
    pages.push(1);
    if (currentPage > 3) pages.push('…');
    for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) pages.push(i);
    if (currentPage < totalPages - 2) pages.push('…');
    pages.push(totalPages);
  }
  const btnBase: React.CSSProperties = { width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, fontSize: 13, fontWeight: 500, border: '1px solid rgba(124,58,237,0.10)', cursor: 'pointer', transition: 'all 200ms ease', background: 'transparent', color: 'var(--color-text-secondary)' };
  return (
    <div id="history-pagination" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 32, paddingBottom: 48 }}>
      <button id="pagination-prev" disabled={currentPage === 1} onClick={() => onPageChange(currentPage - 1)} style={{ ...btnBase, opacity: currentPage === 1 ? 0.4 : 1 }} className="hover:!bg-[rgba(124,58,237,0.08)] hover:!text-[var(--color-primary)] hover:!border-[rgba(124,58,237,0.20)]">
        <ChevronLeft size={16} strokeWidth={2} />
      </button>
      {pages.map((p, i) => p === '…' ? (
        <span key={`e${i}`} style={{ width: 34, textAlign: 'center', color: 'var(--color-text-secondary)' }}>…</span>
      ) : (
        <button key={p} id={`page-btn-${p}`} onClick={() => onPageChange(p as number)}
          style={{ ...btnBase, background: currentPage === p ? 'linear-gradient(135deg, #7C3AED, #A855F7)' : 'transparent', color: currentPage === p ? 'white' : 'var(--color-text-secondary)', border: currentPage === p ? 'none' : '1px solid rgba(124,58,237,0.10)', fontWeight: currentPage === p ? 700 : 500, boxShadow: currentPage === p ? '0 4px 12px rgba(124,58,237,0.30)' : 'none' }}
          className={currentPage !== p ? 'hover:!bg-[rgba(124,58,237,0.08)] hover:!text-[var(--color-primary)]' : ''}
        >{p}</button>
      ))}
      <button id="pagination-next" disabled={currentPage === totalPages} onClick={() => onPageChange(currentPage + 1)} style={{ ...btnBase, opacity: currentPage === totalPages ? 0.4 : 1 }} className="hover:!bg-[rgba(124,58,237,0.08)] hover:!text-[var(--color-primary)] hover:!border-[rgba(124,58,237,0.20)]">
        <ChevronRight size={16} strokeWidth={2} />
      </button>
    </div>
  );
}

/* ── Main Page ── */
export default function HistoryPage() {
  const [stats,        setStats]        = useState<HistoryStats | null>(null);
  const [statsAnimate, setStatsAnimate] = useState(false);
  const [items,        setItems]        = useState<HistoryItem[]>([]);
  const [loading,      setLoading]      = useState(true);
  const [currentPage,  setCurrentPage]  = useState(1);
  const [totalPages,   setTotalPages]   = useState(1);
  const [total,        setTotal]        = useState(0);
  const [search,       setSearch]       = useState('');
  const [debSearch,    setDebSearch]    = useState('');
  const [activeCategory, setActiveCategory] = useState('all');
  const [sortBy,       setSortBy]       = useState<SortBy>('most-recent');
  const [showSort,     setShowSort]     = useState(false);
  const sortRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fetchHistoryStats().then(d => { setStats(d); setTimeout(() => setStatsAnimate(true), 80); }); }, []);
  useEffect(() => { const t = setTimeout(() => setDebSearch(search), 350); return () => clearTimeout(t); }, [search]);
  useEffect(() => { setCurrentPage(1); }, [debSearch, activeCategory, sortBy]);
  useEffect(() => {
    setLoading(true);
    fetchHistory(currentPage, PAGE_SIZE, { search: debSearch, category: activeCategory, sortBy }).then(d => {
      setItems(d.items); setTotalPages(d.totalPages); setTotal(d.total); setLoading(false);
    });
  }, [currentPage, debSearch, activeCategory, sortBy]);
  useEffect(() => {
    function close(e: MouseEvent) { if (sortRef.current && !sortRef.current.contains(e.target as Node)) setShowSort(false); }
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const handleToggleFavorite = useCallback((id: string, current: boolean) => {
    setItems(prev => prev.map(i => i.id === id ? { ...i, isFavorite: !current } : i));
    toggleFavorite(id, !current);
  }, []);
  const handleDelete = useCallback((id: string) => {
    setItems(prev => prev.filter(i => i.id !== id));
    setTotal(prev => prev - 1);
    deleteHistoryItem(id);
  }, []);

  const activeSortLabel = SORT_OPTIONS.find(s => s.id === sortBy)?.label ?? 'Sort';

  return (
    <div id="history-page" style={{ maxWidth: 1100, margin: '0 auto', padding: '0 48px', paddingTop: 8, width: '100%', display: 'flex', flexDirection: 'column', paddingBottom: 64 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '32px 0 28px' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: -0.3, margin: '0 0 4px' }}>Your Prompt History</h1>
          <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', margin: 0 }}>
            {total > 0 ? `${total.toLocaleString()} prompts · track, revisit and re-use your best optimizations` : 'Track, revisit and re-use your best optimized prompts'}
          </p>
        </div>
        <button id="history-new-prompt-btn" style={{
          display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 10, fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
          background: 'linear-gradient(135deg, #7C3AED 0%, #A855F7 100%)', color: 'white', boxShadow: '0 4px 14px rgba(124,58,237,0.30)', transition: 'all 200ms ease',
        }} className="hover:translate-y-[-1px] hover:brightness-105">
          <Zap size={14} strokeWidth={2} />New Prompt
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 28 }}>
        <StatCard label="Total Prompts" value={stats?.totalPrompts ?? 0} icon={Sparkles} accent="#7C3AED" animate={statsAnimate} />
        <StatCard label="Avg Score" value={stats?.averageScore ?? 0} suffix="%" icon={TrendingUp} accent="#10B981" animate={statsAnimate}
          sub={<div style={{ height: 4, background: 'rgba(16,185,129,0.12)', borderRadius: 99, overflow: 'hidden' }}><div style={{ height: '100%', background: '#10B981', borderRadius: 99, width: statsAnimate ? `${stats?.averageScore ?? 0}%` : '0%', transition: 'width 1.2s ease-out' }} /></div>}
        />
        <StatCard label="This Week" value={stats?.thisWeekDelta ?? 0} prefix="+" icon={Zap} accent="#0EA5E9" animate={statsAnimate} sparkline />
        <StatCard label="Favorites" value={stats?.favoritesCount ?? 0} icon={Star} accent="#F59E0B" animate={statsAnimate}
          sub={<button id="view-all-favorites-btn" onClick={() => setActiveCategory('favorites')} style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }} className="hover:underline">View all →</button>}
        />
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        {/* Search */}
        <div style={{ position: 'relative', flex: '0 0 260px' }}>
          <Search size={14} strokeWidth={1.8} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-secondary)', pointerEvents: 'none' }} />
          <input id="history-search-input" type="text" placeholder="Search prompts..." value={search} onChange={e => setSearch(e.target.value)}
            style={{ width: '100%', padding: '9px 36px 9px 36px', fontSize: 13, background: '#FFFFFF', border: '1px solid rgba(124,58,237,0.12)', borderRadius: 10, outline: 'none', color: 'var(--color-text-primary)', transition: 'border-color 200ms ease, box-shadow 200ms ease' }}
            className="focus:!border-[rgba(124,58,237,0.35)] focus:shadow-[0_0_0_3px_rgba(124,58,237,0.08)]"
          />
          {search && <button onClick={() => setSearch('')} title="Clear" style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: 'var(--color-text-secondary)', lineHeight: 1 }}>×</button>}
        </div>

        {/* Category chips */}
        <div id="history-filter-chips" style={{ display: 'flex', gap: 6, overflowX: 'auto', flexWrap: 'nowrap', flex: 1, scrollbarWidth: 'none', msOverflowStyle: 'none' }} className="no-scrollbar">
          {FILTER_CATEGORIES.map(cat => (
            <button key={cat.id} id={`filter-${cat.id}`} onClick={() => setActiveCategory(cat.id)}
              style={{
                padding: '6px 14px', borderRadius: 9999, fontSize: 12.5, fontWeight: 500, cursor: 'pointer', border: 'none', whiteSpace: 'nowrap', transition: 'all 180ms ease',
                flexShrink: 0,
                background: activeCategory === cat.id ? 'linear-gradient(135deg, #7C3AED, #A855F7)' : 'rgba(124,58,237,0.06)',
                color: activeCategory === cat.id ? 'white' : 'var(--color-text-secondary)',
                boxShadow: activeCategory === cat.id ? '0 3px 10px rgba(124,58,237,0.25)' : 'none',
              }}
              className={activeCategory !== cat.id ? 'hover:!bg-[rgba(124,58,237,0.12)] hover:!text-[var(--color-text-primary)]' : ''}
            >{cat.label}</button>
          ))}
        </div>

        {/* Sort */}
        <div style={{ position: 'relative', flexShrink: 0 }} ref={sortRef}>
          <button id="sort-btn" onClick={() => setShowSort(v => !v)}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, fontSize: 13, fontWeight: 500, border: '1px solid rgba(124,58,237,0.12)', cursor: 'pointer', background: '#FFFFFF', color: 'var(--color-text-secondary)', transition: 'all 200ms ease' }}
            className="hover:!border-[rgba(124,58,237,0.22)] hover:!text-[var(--color-text-primary)]"
          >
            <SlidersHorizontal size={13} strokeWidth={2} />{activeSortLabel}
            <ChevronDown size={12} strokeWidth={2} style={{ transition: 'transform 200ms', transform: showSort ? 'rotate(180deg)' : 'none' }} />
          </button>
          {showSort && (
            <div id="sort-menu" style={{ position: 'absolute', top: 'calc(100% + 6px)', right: 0, background: '#FFFFFF', border: '1px solid rgba(124,58,237,0.10)', borderRadius: 10, minWidth: 180, zIndex: 50, padding: 4, boxShadow: '0 8px 24px rgba(109,40,217,0.10)', animation: 'dropdownFadeIn 150ms ease' }}>
              {SORT_OPTIONS.map(opt => (
                <button key={opt.id} id={`sort-${opt.id}`} onClick={() => { setSortBy(opt.id); setShowSort(false); }}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 12px', fontSize: 13, fontWeight: sortBy === opt.id ? 600 : 500, color: sortBy === opt.id ? 'var(--color-primary)' : 'var(--color-text-primary)', borderRadius: 8, border: 'none', cursor: 'pointer', background: 'transparent', textAlign: 'left' }}
                  className="hover:bg-[rgba(124,58,237,0.05)]"
                >
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-primary)', opacity: sortBy === opt.id ? 1 : 0, flexShrink: 0 }} />
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* List */}
      <div id="history-list" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px', borderRadius: 14, border: '1px solid rgba(124,58,237,0.09)' }}>
              <div className="skeleton" style={{ width: 38, height: 38, borderRadius: 10 }} />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div className="skeleton" style={{ height: 16, width: '60%' }} />
                <div className="skeleton" style={{ height: 12, width: '40%' }} />
              </div>
              <div className="skeleton" style={{ width: 36, height: 36, borderRadius: 8 }} />
            </div>
          ))
        ) : items.length === 0 ? (
          <div id="history-empty-state" style={{ textAlign: 'center', padding: '64px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 56, height: 56, borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(124,58,237,0.08)', color: 'var(--color-primary)' }}><Search size={26} strokeWidth={1.2} /></div>
            <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>No prompts found</h3>
            <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', margin: 0 }}>Try adjusting your search or filter settings.</p>
            <button id="history-reset-btn" onClick={() => { setSearch(''); setActiveCategory('all'); }}
              style={{ marginTop: 8, padding: '8px 20px', borderRadius: 9, fontSize: 13, fontWeight: 600, border: '1px solid rgba(124,58,237,0.20)', cursor: 'pointer', background: 'transparent', color: 'var(--color-primary)' }}
              className="hover:bg-[rgba(124,58,237,0.06)]"
            >Clear filters</button>
          </div>
        ) : items.map(item => (
          <HistoryRow key={item.id} item={item} onToggleFavorite={handleToggleFavorite} onDelete={handleDelete} />
        ))}
      </div>

      {!loading && totalPages > 1 && (
        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
      )}
    </div>
  );
}
