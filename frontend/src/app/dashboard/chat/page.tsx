'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { MessageSquare, Sparkles, ArrowRight } from 'lucide-react';

const MOCK_CHATS = [
  { id: 'r1', title: 'Write a viral Twitter thread about AI in healthcare', category: 'marketing', score: 94 },
  { id: 'r2', title: 'Debug my React useEffect infinite loop issue',         category: 'coding',    score: 88 },
  { id: 'r3', title: 'Cinematic shot of neon rain on cyberpunk streets',     category: 'cinematic', score: 91 },
  { id: 'r4', title: 'Explain quantum entanglement to a 10-year-old',        category: 'research',  score: 76 },
  { id: 'r5', title: 'Generate a product launch email sequence',             category: 'email',     score: 83 },
  { id: 'r6', title: 'YouTube thumbnail prompt for tech review video',       category: 'youtube',   score: 79 },
  { id: 'r7', title: 'Anime-style landscape with cherry blossoms',           category: 'image-gen', score: 95 },
  { id: 'r8', title: 'Write a compelling SaaS landing page headline',        category: 'marketing', score: 87 },
];

export default function ChatIndexPage() {
  const router = useRouter();
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 48px 64px', width: '100%', overflowY: 'auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: -0.3, marginBottom: 8 }}>Chat Sessions</h1>
      <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: 32 }}>Resume or start new optimization conversations</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {MOCK_CHATS.map(chat => (
          <button key={chat.id} onClick={() => router.push(`/dashboard/chat/${chat.id}`)}
            style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px', background: '#FFFFFF', border: '1px solid rgba(124,58,237,0.10)', borderRadius: 14, cursor: 'pointer', textAlign: 'left', transition: 'all 200ms ease', boxShadow: '0 2px 8px rgba(109,40,217,0.04)' }}
            className="hover:!border-[rgba(124,58,237,0.18)] hover:shadow-[0_4px_16px_rgba(109,40,217,0.08)] hover:translate-y-[-1px]"
          >
            <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(124,58,237,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-primary)', flexShrink: 0 }}>
              <MessageSquare size={18} strokeWidth={1.5} />
            </div>
            <span style={{ flex: 1, fontSize: 14, fontWeight: 500, color: 'var(--color-text-primary)' }}>{chat.title}</span>
            <span style={{ fontSize: 15, fontWeight: 700, color: '#10B981', flexShrink: 0 }}>{chat.score}</span>
            <ArrowRight size={16} style={{ color: 'rgba(107,107,138,0.40)', flexShrink: 0 }} />
          </button>
        ))}
      </div>
      <button
        onClick={() => router.push('/dashboard/chat/r1')}
        style={{ marginTop: 32, display: 'flex', alignItems: 'center', gap: 8, padding: '12px 24px', borderRadius: 12, fontSize: 14, fontWeight: 600, border: 'none', cursor: 'pointer', background: 'linear-gradient(135deg, #7C3AED, #A855F7)', color: 'white', boxShadow: '0 4px 16px rgba(124,58,237,0.30)', transition: 'all 200ms ease' }}
        className="hover:translate-y-[-1px] hover:brightness-105"
      >
        <Sparkles size={15} />New Optimization Session
      </button>
    </div>
  );
}
