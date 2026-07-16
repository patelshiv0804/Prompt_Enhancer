import React, { useState } from 'react';
import { Sparkles } from 'lucide-react';

const MODES = [
  'General', 'Coding', 'Research', 'Marketing', 'Storytelling',
  'Image Gen', 'Cinematic Video', 'YouTube Shorts', 'SEO',
];

interface ControlsProps {
  onAnalyze: () => void;
  isAnalyzing: boolean;
}

export default function Controls({ onAnalyze, isAnalyzing }: ControlsProps) {
  const [activeMode, setActiveMode] = useState('Cinematic Video');

  return (
    <div style={{ marginTop: 32, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '1.2px' }}>
        Optimization Target
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {MODES.map(mode => (
          <button
            key={mode}
            onClick={() => setActiveMode(mode)}
            style={{
              padding: '7px 14px', borderRadius: 9999, fontSize: 13, fontWeight: 500,
              cursor: 'pointer', transition: 'all 250ms ease',
              color: activeMode === mode ? '#6D28D9' : '#6B6B8A',
              background: activeMode === mode
                ? 'linear-gradient(160deg, rgba(167,139,250,0.22) 0%, rgba(196,181,253,0.12) 100%)'
                : 'linear-gradient(160deg, rgba(109,40,217,0.07) 0%, rgba(124,58,237,0.03) 100%)',
              border: `1px solid ${activeMode === mode ? 'rgba(124,58,237,0.30)' : 'rgba(124,58,237,0.12)'}`,
              boxShadow: activeMode === mode
                ? 'inset 0 1px 0 rgba(255,255,255,0.70), 0 4px 14px rgba(124,58,237,0.18), 0 1px 4px rgba(0,0,0,0.08), 0 0 0 1px rgba(124,58,237,0.18)'
                : 'inset 0 2px 4px rgba(80,20,180,0.10), inset 0 1px 2px rgba(0,0,0,0.06), 0 1px 0 rgba(255,255,255,0.80)',
              transform: activeMode === mode ? 'translateY(-1px)' : 'none',
            }}
          >
            {mode}
          </button>
        ))}
      </div>
      <button
        onClick={onAnalyze}
        disabled={isAnalyzing}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 28px',
          borderRadius: 11, fontSize: 14, fontWeight: 600, border: 'none', cursor: isAnalyzing ? 'not-allowed' : 'pointer',
          background: 'linear-gradient(135deg, #7C3AED 0%, #A855F7 100%)', color: 'white',
          boxShadow: '0 4px 16px rgba(124,58,237,0.30)', opacity: isAnalyzing ? 0.75 : 1,
          transition: 'all 220ms ease', alignSelf: 'flex-start',
        }}
        className={!isAnalyzing ? 'hover:translate-y-[-1px] hover:shadow-[0_8px_24px_rgba(124,58,237,0.40)] hover:brightness-105' : ''}
      >
        <Sparkles size={14} style={{ animation: 'pulseGlow 2s infinite' }} />
        {isAnalyzing ? 'Analyzing...' : 'Analyze & Optimize'}
      </button>
    </div>
  );
}
