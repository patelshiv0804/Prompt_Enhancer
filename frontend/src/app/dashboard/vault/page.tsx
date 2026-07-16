'use client';

import React from 'react';
import { Library } from 'lucide-react';

export default function VaultPage() {
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 48px 64px', width: '100%' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: -0.3, marginBottom: 8 }}>Vault</h1>
      <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: 48 }}>Your saved prompts and collections</p>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, paddingTop: 80 }}>
        <div style={{ width: 72, height: 72, borderRadius: 20, background: 'rgba(124,58,237,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-primary)' }}>
          <Library size={32} strokeWidth={1.2} />
        </div>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Your Vault is empty</h2>
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', margin: 0, textAlign: 'center', maxWidth: 320 }}>
          Save optimized prompts from the Optimizer to build your personal library.
        </p>
      </div>
    </div>
  );
}
