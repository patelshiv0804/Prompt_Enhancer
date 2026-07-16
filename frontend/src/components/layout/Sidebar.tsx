'use client';

import React, { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import {
  Sparkles, LayoutTemplate, Library, Fingerprint,
  Settings, User, History as HistoryIcon, Clock,
  Code2, Search, Film, PlaySquare, Image as ImageIcon,
  Megaphone, BookOpen, Mail, Star, ChevronDown, ChevronRight,
} from 'lucide-react';

export type ActivePage = 'optimizer' | 'history' | 'templates' | 'vault' | 'style-memory' | 'chaining' | 'settings' | 'chat';

interface NavItem { id: ActivePage; icon: React.ElementType; label: string; shortcut?: string; }
interface NavGroup { label: string; items: NavItem[]; }

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Workspace',
    items: [
      { id: 'optimizer',  icon: Sparkles,        label: 'Optimizer',  shortcut: '⌘1' },
      { id: 'templates',  icon: LayoutTemplate,  label: 'Templates',  shortcut: '⌘2' },
      { id: 'vault',      icon: Library,         label: 'Vault',      shortcut: '⌘3' },
    ],
  },
  {
    label: 'Personalize',
    items: [
      { id: 'style-memory', icon: Fingerprint, label: 'Style Memory' },
      { id: 'settings',     icon: Settings,    label: 'Settings' },
    ],
  },
];

const SIDEBAR_HISTORY_ICONS: Record<string, React.ElementType> = {
  coding: Code2, research: Search, marketing: Megaphone,
  storytelling: BookOpen, 'image-gen': ImageIcon, cinematic: Film,
  youtube: PlaySquare, general: Sparkles, email: Mail,
};
const SIDEBAR_HISTORY_ACCENTS: Record<string, string> = {
  coding: '#0EA5E9', research: '#8B5CF6', marketing: '#10B981',
  storytelling: '#F59E0B', 'image-gen': '#EC4899', cinematic: '#8B5CF6',
  youtube: '#EF4444', general: '#7C3AED', email: '#0EA5E9',
};
const MOCK_RECENT = [
  { id: 'r1', prompt: 'Write a viral Twitter thread about AI in healthcare',  category: 'marketing',    score: 94, isFavorite: true,  ago: '2m' },
  { id: 'r2', prompt: 'Debug my React useEffect infinite loop issue',         category: 'coding',       score: 88, isFavorite: false, ago: '1h' },
  { id: 'r3', prompt: 'Cinematic shot of neon rain on cyberpunk streets',     category: 'cinematic',    score: 91, isFavorite: false, ago: '3h' },
  { id: 'r4', prompt: 'Explain quantum entanglement to a 10-year-old',        category: 'research',     score: 76, isFavorite: false, ago: '5h' },
  { id: 'r5', prompt: 'Generate a product launch email sequence',             category: 'email',        score: 83, isFavorite: true,  ago: 'Yesterday' },
  { id: 'r6', prompt: 'YouTube thumbnail prompt for tech review video',       category: 'youtube',      score: 79, isFavorite: false, ago: 'Yesterday' },
  { id: 'r7', prompt: 'Anime-style landscape with cherry blossoms',           category: 'image-gen',    score: 95, isFavorite: true,  ago: '2d' },
  { id: 'r8', prompt: 'Write a compelling SaaS landing page headline',        category: 'marketing',    score: 87, isFavorite: false, ago: '3d' },
];

export default function Sidebar() {
  const router   = useRouter();
  const pathname = usePathname();
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [recentCollapsed, setRecentCollapsed] = useState(false);

  const toggleGroup = (label: string) =>
    setCollapsedGroups(prev => ({ ...prev, [label]: !prev[label] }));

  const navigate = (page: ActivePage) => router.push(`/dashboard/${page}`);
  const isActive = (page: ActivePage) => pathname === `/dashboard/${page}` || (page === 'optimizer' && pathname === '/dashboard');

  const currentChatId = pathname.startsWith('/dashboard/chat/') ? pathname.split('/dashboard/chat/')[1] : null;

  return (
    <aside
      style={{
        width: 248, height: 'calc(100vh - 24px)', display: 'flex', flexDirection: 'column',
        flexShrink: 0, position: 'relative', zIndex: 100, margin: 12, borderRadius: 20,
        overflow: 'hidden', background: 'rgba(248, 245, 255, 0.82)',
        backdropFilter: 'blur(24px) saturate(160%)', WebkitBackdropFilter: 'blur(24px) saturate(160%)',
        border: '1px solid rgba(139, 92, 246, 0.10)',
        boxShadow: '0 2px 24px rgba(109,40,217,0.07), 0 1px 4px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.80)',
      }}
    >
      {/* Logo */}
      <div style={{ padding: '20px 20px 16px', flexShrink: 0, borderBottom: '1px solid rgba(124,58,237,0.07)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <img src="/logo_1.svg" alt="Logo" style={{ width: 28, height: 28, borderRadius: 8, objectFit: 'contain' }} />
          <span style={{ fontSize: 15, fontWeight: 800, color: '#2D1B69', letterSpacing: '1.5px', textTransform: 'uppercase' }}>AURE</span>
        </div>
      </div>

      {/* Scrollable body */}
      <div style={{
        flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '12px 10px',
        display: 'flex', flexDirection: 'column', gap: 4,
        scrollbarWidth: 'thin', scrollbarColor: 'rgba(124,58,237,0.15) transparent',
      }}>

        {/* Nav Groups */}
        {NAV_GROUPS.map(group => {
          const isCollapsed = !!collapsedGroups[group.label];
          return (
            <div key={group.label} style={{ display: 'flex', flexDirection: 'column', marginBottom: 4 }}>
              <button
                onClick={() => toggleGroup(group.label)}
                aria-expanded={!isCollapsed}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '5px 8px',
                  borderRadius: 6, border: 'none', background: 'transparent', cursor: 'pointer',
                  width: '100%', textAlign: 'left', marginBottom: 2,
                }}
                className="group/navgroup hover:bg-[rgba(124,58,237,0.06)] transition-colors duration-150"
              >
                <span style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'rgba(45,27,105,0.45)', flex: 1 }}>
                  {group.label}
                </span>
                {isCollapsed
                  ? <ChevronRight size={12} style={{ color: 'rgba(109,40,217,0.35)', flexShrink: 0 }} />
                  : <ChevronDown  size={12} style={{ color: 'rgba(109,40,217,0.35)', flexShrink: 0 }} />
                }
              </button>

              {!isCollapsed && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1, animation: 'groupItemsIn 0.18s ease-out' }}>
                  {group.items.map(item => {
                    const Icon   = item.icon;
                    const active = isActive(item.id);
                    return (
                      <button
                        key={item.id}
                        id={`nav-${item.id}`}
                        onClick={() => navigate(item.id)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
                          borderRadius: 10, fontSize: 13.5, fontWeight: active ? 600 : 500,
                          cursor: 'pointer', border: 'none', width: '100%', textAlign: 'left',
                          color: active ? '#4C1D95' : 'rgba(45,27,105,0.65)',
                          background: active ? 'rgba(124,58,237,0.11)' : 'transparent',
                          transition: 'background 160ms ease, color 160ms ease',
                        }}
                        className={!active ? 'hover:bg-[rgba(124,58,237,0.07)] hover:!text-[rgba(45,27,105,0.90)]' : ''}
                      >
                        <span style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                          background: active ? 'rgba(124,58,237,0.14)' : 'transparent',
                          color: active ? '#7C3AED' : 'rgba(109,40,217,0.50)',
                          transition: 'background 160ms ease, color 160ms ease',
                        }}>
                          <Icon size={16} strokeWidth={1.8} />
                        </span>
                        <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {item.label}
                        </span>
                        {item.shortcut && (
                          <span style={{ fontSize: 10, fontWeight: 500, color: 'rgba(109,40,217,0.30)', opacity: 0, transition: 'opacity 150ms' }}
                            className="group-hover/navgroup:opacity-100">
                            {item.shortcut}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {/* Section Divider */}
        <div style={{
          height: 1, margin: '8px 4px', flexShrink: 0,
          background: 'linear-gradient(to right, transparent, rgba(124,58,237,0.15) 20%, rgba(124,58,237,0.15) 80%, transparent)',
        }} />

        {/* Recent History */}
        <div style={{ display: 'flex', flexDirection: 'column', marginBottom: 4 }}>
          <div
            role="button" tabIndex={0}
            onClick={() => setRecentCollapsed(v => !v)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setRecentCollapsed(v => !v); }}}
            aria-expanded={!recentCollapsed}
            style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '5px 8px',
              borderRadius: 6, border: 'none', background: 'transparent', cursor: 'pointer',
              width: '100%', textAlign: 'left', marginBottom: 2,
            }}
            className="hover:bg-[rgba(124,58,237,0.06)] transition-colors duration-150"
          >
            <HistoryIcon size={12} style={{ color: 'rgba(109,40,217,0.45)', flexShrink: 0 }} />
            <span style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'rgba(45,27,105,0.45)', flex: 1 }}>Recent</span>
            <button
              id="sidebar-history-view-all"
              onClick={e => { e.stopPropagation(); router.push('/dashboard/history'); }}
              style={{
                fontSize: 10, fontWeight: 600, color: '#6D28D9', background: 'none', border: 'none',
                cursor: 'pointer', padding: '2px 5px', borderRadius: 4, marginRight: 2,
              }}
              className="hover:bg-[rgba(124,58,237,0.10)] hover:!text-[#5B21B6] transition-colors duration-150"
            >View all</button>
            {recentCollapsed
              ? <ChevronRight size={12} style={{ color: 'rgba(109,40,217,0.35)', flexShrink: 0 }} />
              : <ChevronDown  size={12} style={{ color: 'rgba(109,40,217,0.35)', flexShrink: 0 }} />
            }
          </div>

          {!recentCollapsed && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1, animation: 'groupItemsIn 0.18s ease-out' }}>
              {MOCK_RECENT.map(item => {
                const Icon   = SIDEBAR_HISTORY_ICONS[item.category] || Clock;
                const accent = SIDEBAR_HISTORY_ACCENTS[item.category] || '#7C3AED';
                const active = pathname === `/dashboard/chat/${item.id}`;
                return (
                  <button
                    key={item.id}
                    id={`sidebar-history-item-${item.id}`}
                    title={item.prompt}
                    onClick={() => router.push(`/dashboard/chat/${item.id}`)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 9, padding: active ? '8px 10px 8px 8px' : '8px 10px',
                      borderRadius: 10, background: active ? 'rgba(124,58,237,0.12)' : 'transparent',
                      border: 'none', cursor: 'pointer', width: '100%', textAlign: 'left',
                      borderLeft: active ? '2px solid #7C3AED' : '2px solid transparent',
                      transition: 'background 160ms ease', flexShrink: 0,
                    }}
                    className={!active ? 'hover:bg-[rgba(124,58,237,0.07)]' : ''}
                  >
                    <div style={{
                      width: 26, height: 26, borderRadius: 7, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', flexShrink: 0, color: accent, background: `${accent}18`,
                    }}>
                      <Icon size={11} strokeWidth={2} />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0, flex: 1 }}>
                      <p style={{
                        fontSize: 12, fontWeight: active ? 600 : 500,
                        color: active ? '#4C1D95' : 'rgba(45,27,105,0.80)',
                        margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.3,
                      }}>{item.prompt}</p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <span style={{ fontSize: 10, color: 'rgba(45,27,105,0.40)', fontWeight: 400, whiteSpace: 'nowrap' }}>{item.ago}</span>
                        {item.isFavorite && <Star size={9} fill="#F59E0B" color="#F59E0B" style={{ flexShrink: 0 }} />}
                      </div>
                    </div>
                    <span style={{ fontSize: 10.5, fontWeight: 700, lineHeight: 1, flexShrink: 0, color: accent, opacity: 0.75 }}>
                      {item.score}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div style={{ flexShrink: 0, padding: '0 10px 12px' }}>
        <div style={{ height: 1, background: 'rgba(124,58,237,0.09)', margin: '0 0 10px' }} />
        <button
          id="user-profile-btn"
          style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
            borderRadius: 12, width: '100%', cursor: 'pointer',
            background: 'rgba(255,255,255,0.55)', border: '1px solid rgba(124,58,237,0.10)',
            textAlign: 'left', boxShadow: '0 1px 4px rgba(109,40,217,0.06)', transition: 'background 160ms ease',
          }}
          className="hover:!bg-[rgba(255,255,255,0.80)] hover:border-[rgba(124,58,237,0.18)]"
        >
          <div style={{
            background: 'linear-gradient(135deg, rgba(124,58,237,0.18), rgba(167,139,250,0.12))',
            color: '#7C3AED', width: 30, height: 30, borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: '1px solid rgba(124,58,237,0.15)', flexShrink: 0,
          }}>
            <User size={15} strokeWidth={1.5} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: 12.5, fontWeight: 600, color: '#3B1082', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Alex P.
            </span>
            <span style={{
              fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px',
              background: 'linear-gradient(135deg, #7C3AED, #A855F7)', color: 'white',
              padding: '2px 8px', borderRadius: 9999, flexShrink: 0,
              boxShadow: '0 2px 6px rgba(124,58,237,0.25)',
            }}>Pro</span>
          </div>
        </button>
      </div>
    </aside>
  );
}
