'use client';

import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';

interface HeaderProps {
  activeTab?: string;
  onTabChange?: (tab: string) => void;
}

export default function Header({ activeTab = 'Draft', onTabChange }: HeaderProps) {
  const [showStyleDropdown, setShowStyleDropdown] = useState(false);
  const [activeStyle, setActiveStyle]             = useState('None');
  const [showTargetDropdown, setShowTargetDropdown] = useState(false);
  const [activeTarget, setActiveTarget]           = useState('ChatGPT');
  const [activeEngine, setActiveEngine]           = useState('Claude Sonnet 4.5');

  const styleDropdownRef  = useRef<HTMLDivElement>(null);
  const targetDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (styleDropdownRef.current && !styleDropdownRef.current.contains(event.target as Node))
        setShowStyleDropdown(false);
      if (targetDropdownRef.current && !targetDropdownRef.current.contains(event.target as Node))
        setShowTargetDropdown(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const styles = [
    { name: 'None',                  color: '#9ca3af' },
    { name: 'Cinematic Noir',        color: '#f59e0b' },
    { name: 'Editorial Warm',        color: '#ea580c' },
    { name: 'Product Launch Voice',  color: '#0ea5e9' },
  ];
  const models  = ['ChatGPT', 'Claude', 'Gemini', 'Grok', 'Midjourney', 'VEO', 'DALL-E', 'Stable Diffusion'];
  const engines = ['Claude Sonnet 4.5', 'GPT-5.2'];

  const activeStyleObj = styles.find(s => s.name === activeStyle) || styles[0];

  /* ── Shared inline styles as objects for readability ── */
  const pillBase: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px',
    borderRadius: 9999, fontSize: 13, fontWeight: 500, cursor: 'pointer',
    whiteSpace: 'nowrap', transition: 'all 250ms ease',
  };

  return (
    <header style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '32px 48px 24px', gap: 16, flexShrink: 0,
      maxWidth: 1100, margin: '0 auto', width: '100%',
    }}>
      {/* Left: Title + Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: '-0.02em' }}>
          Optimizer
        </h1>

        {/* Recessed tab trough */}
        <div style={{
          display: 'flex', alignItems: 'center',
          background: 'linear-gradient(160deg, rgba(109,40,217,0.10) 0%, rgba(124,58,237,0.04) 100%)',
          border: '1px solid rgba(124,58,237,0.13)', borderRadius: 9999, padding: 3, gap: 2,
          boxShadow: 'inset 0 2px 5px rgba(80,20,180,0.14), inset 0 1px 2px rgba(0,0,0,0.08), 0 1px 0 rgba(255,255,255,0.75)',
        }}>
          {['Draft', 'History'].map(tab => (
            <button
              key={tab}
              onClick={() => onTabChange?.(tab)}
              style={{
                fontSize: 13, fontWeight: tab === activeTab ? 600 : 500,
                color: tab === activeTab ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                padding: '5px 14px', borderRadius: 9999, border: 'none', cursor: 'pointer',
                background: tab === activeTab ? '#ffffff' : 'transparent',
                boxShadow: tab === activeTab
                  ? 'inset 0 1px 0 rgba(255,255,255,0.90), 0 4px 8px rgba(80,20,180,0.12), 0 1px 3px rgba(0,0,0,0.10), 0 0 0 1px rgba(124,58,237,0.07)'
                  : 'none',
                transform: tab === activeTab ? 'translateY(-0.5px)' : 'none',
                transition: 'all 250ms ease',
              }}
            >{tab}</button>
          ))}
        </div>
      </div>

      {/* Right: Style + Target pills */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>

        {/* Style dropdown */}
        <div style={{ position: 'relative' }} ref={styleDropdownRef}>
          <button
            onClick={() => { setShowStyleDropdown(!showStyleDropdown); setShowTargetDropdown(false); }}
            style={{
              ...pillBase,
              background: 'linear-gradient(160deg, rgba(109,40,217,0.07) 0%, rgba(255,255,255,0.80) 100%)',
              border: '1px solid rgba(124,58,237,0.13)', color: 'var(--color-text-primary)',
              boxShadow: 'inset 0 2px 4px rgba(80,20,180,0.10), inset 0 1px 2px rgba(0,0,0,0.06), 0 1px 0 rgba(255,255,255,0.90)',
            }}
            className="hover:translate-y-[-1px] hover:border-[rgba(124,58,237,0.22)] hover:shadow-[inset_0_1px_3px_rgba(80,20,180,0.08),0_3px_10px_rgba(124,58,237,0.10),0_1px_0_rgba(255,255,255,1)]"
          >
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: activeStyleObj.color, display: 'inline-block', flexShrink: 0 }} />
            <span style={{ opacity: 0.6 }}>Style</span>
            <span style={{ opacity: 0.3 }}>|</span>
            <span style={{ fontWeight: 600 }}>{activeStyle}</span>
            <ChevronDown size={13} style={{ opacity: 0.5 }} />
          </button>

          {showStyleDropdown && (
            <div style={{
              position: 'absolute', top: 'calc(100% + 8px)', right: 0, background: 'white',
              border: '1px solid rgba(124,58,237,0.10)', borderRadius: 12, minWidth: 200,
              overflow: 'hidden', zIndex: 100,
              boxShadow: '0 8px 24px rgba(109,40,217,0.10), 0 2px 8px rgba(0,0,0,0.06)',
              animation: 'dropdownFadeIn 150ms ease',
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-secondary)', padding: '10px 12px 6px' }}>
                Style Memory
              </div>
              <div style={{ padding: 4, display: 'flex', flexDirection: 'column', gap: 1 }}>
                {styles.map(style => (
                  <button key={style.name} onClick={() => { setActiveStyle(style.name); setShowStyleDropdown(false); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 10px',
                      fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)',
                      borderRadius: 8, textAlign: 'left', border: 'none', cursor: 'pointer', background: 'transparent',
                    }}
                    className="hover:bg-[rgba(124,58,237,0.05)]"
                  >
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: style.color, display: 'inline-block' }} />
                    {style.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Target dropdown */}
        <div style={{ position: 'relative' }} ref={targetDropdownRef}>
          <button
            onClick={() => { setShowTargetDropdown(!showTargetDropdown); setShowStyleDropdown(false); }}
            style={{
              ...pillBase,
              background: 'linear-gradient(135deg, #7C3AED 0%, #A855F7 100%)', color: 'white',
              boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.22), 0 5px 16px rgba(124,58,237,0.38), 0 2px 5px rgba(0,0,0,0.14), 0 0 0 1px rgba(124,58,237,0.20)',
            }}
            className="hover:translate-y-[-2px] hover:brightness-105 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.28),0_8px_24px_rgba(124,58,237,0.48),0_3px_8px_rgba(0,0,0,0.16),0_0_0_1px_rgba(124,58,237,0.25)]"
          >
            <span style={{ opacity: 0.75 }}>Target</span>
            <span style={{ opacity: 0.4 }}>|</span>
            <span style={{ fontWeight: 600 }}>{activeTarget}</span>
            <ChevronDown size={13} style={{ opacity: 0.6 }} />
          </button>

          {showTargetDropdown && (
            <div style={{
              position: 'absolute', top: 'calc(100% + 8px)', right: 0, background: 'white',
              border: '1px solid rgba(124,58,237,0.10)', borderRadius: 12, minWidth: 220,
              overflow: 'hidden', zIndex: 100,
              boxShadow: '0 8px 24px rgba(109,40,217,0.10), 0 2px 8px rgba(0,0,0,0.06)',
              animation: 'dropdownFadeIn 150ms ease',
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-secondary)', padding: '10px 12px 6px' }}>
                Target AI model
              </div>
              <div style={{ padding: 4, display: 'flex', flexDirection: 'column', gap: 1 }}>
                {models.map(model => (
                  <button key={model} onClick={() => { setActiveTarget(model); setShowTargetDropdown(false); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 10px',
                      fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)',
                      borderRadius: 8, textAlign: 'left', border: 'none', cursor: 'pointer', background: 'transparent',
                    }}
                    className="hover:bg-[rgba(124,58,237,0.05)]"
                  >
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-primary)', flexShrink: 0, opacity: activeTarget === model ? 1 : 0 }} />
                    {model}
                  </button>
                ))}
              </div>
              <div style={{ height: 1, background: 'rgba(124,58,237,0.08)', margin: '4px 0' }} />
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-secondary)', padding: '6px 12px' }}>
                Optimizer Engine
              </div>
              <div style={{ padding: 4, display: 'flex', flexDirection: 'column', gap: 1 }}>
                {engines.map(engine => (
                  <button key={engine} onClick={() => { setActiveEngine(engine); setShowTargetDropdown(false); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 10px',
                      fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)',
                      borderRadius: 8, textAlign: 'left', border: 'none', cursor: 'pointer', background: 'transparent',
                    }}
                    className="hover:bg-[rgba(124,58,237,0.05)]"
                  >
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-primary)', flexShrink: 0, opacity: activeEngine === engine ? 1 : 0 }} />
                    {engine}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
