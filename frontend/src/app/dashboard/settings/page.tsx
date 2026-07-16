'use client';

import React from 'react';
import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 48px 64px', width: '100%' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: -0.3, marginBottom: 8 }}>Settings</h1>
      <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: 40 }}>Manage your account and preferences</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {['Account', 'Billing', 'API Keys', 'Notifications'].map(section => (
          <div key={section} style={{ background: '#FFFFFF', border: '1px solid rgba(124,58,237,0.10)', borderRadius: 16, padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', boxShadow: '0 2px 8px rgba(109,40,217,0.04)' }}>
            <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-text-primary)' }}>{section}</span>
            <button style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-primary)', background: 'none', border: 'none', cursor: 'pointer' }}>Configure →</button>
          </div>
        ))}
      </div>
    </div>
  );
}
