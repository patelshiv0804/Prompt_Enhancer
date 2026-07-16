'use client';

import React from 'react';
import { Fingerprint } from 'lucide-react';

export default function StyleMemoryPage() {
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 48px 64px', width: '100%' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: -0.3, marginBottom: 8 }}>Style Memory</h1>
      <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: 48 }}>Personalize your optimization with saved style profiles</p>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, paddingTop: 80 }}>
        <div style={{ width: 72, height: 72, borderRadius: 20, background: 'rgba(124,58,237,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-primary)' }}>
          <Fingerprint size={32} strokeWidth={1.2} />
        </div>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>No style profiles yet</h2>
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', margin: 0, textAlign: 'center', maxWidth: 320 }}>
          Create custom style profiles to automatically apply your brand voice and preferences to every optimization.
        </p>
        <button style={{ marginTop: 8, padding: '10px 22px', borderRadius: 10, fontSize: 14, fontWeight: 600, border: 'none', cursor: 'pointer', background: 'linear-gradient(135deg, #7C3AED, #A855F7)', color: 'white', boxShadow: '0 4px 14px rgba(124,58,237,0.30)' }}>
          Create Style Profile
        </button>
      </div>
    </div>
  );
}
