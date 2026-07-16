'use client';

import React, { useState, useMemo } from 'react';
import {
  Search, Bookmark, BookmarkCheck, Sparkles, Code2, Megaphone, Palette,
  Video, Wand2, BookOpen, Briefcase, TrendingUp, Star, ChevronRight,
  Zap, Copy, Film,
} from 'lucide-react';

interface Template {
  id: string; title: string; description: string; category: string; tags: string[];
  model: string; modelColor: string; promptPreview: string;
  isFeatured?: boolean; isTrending?: boolean; isNew?: boolean; useCount?: number;
}

interface Category { id: string; label: string; icon: React.ElementType; }

const DUMMY_TEMPLATES: Template[] = [
  { id: 'tmpl-001', title: 'Cinematic Establishing Shot', description: 'A highly structured prompt template designed to generate photorealistic, sweeping landscape introductions with specific camera movement and lighting parameters for VEO.', category: 'veo', tags: ['VEO', 'Cinematic', 'Landscape'], model: 'VEO Video Model', modelColor: '#8B5CF6', promptPreview: 'Generate a [time of day] cinematic establishing shot of a [environment]. Camera movement: [slow pan/drone sweep]. Lighting: [volumetric/high-key]. Mood: [epic/serene].', isFeatured: true, isTrending: true, useCount: 4821 },
  { id: 'tmpl-002', title: 'React Component Generator', description: 'Strictly typed React functional component with props interface, hooks, and accessibility attributes auto-generated.', category: 'coding', tags: ['Coding', 'React'], model: 'Claude Sonnet', modelColor: '#0EA5E9', promptPreview: 'Create a fully typed React component called [ComponentName] that [functionality]. Include: TypeScript interface, hooks, aria labels.', isTrending: true, useCount: 3102 },
  { id: 'tmpl-003', title: 'SaaS Landing Hero Copy', description: 'High-converting Hero section copy with headline, sub-headline, CTA and social-proof block for SaaS products.', category: 'marketing', tags: ['Marketing', 'Copywriting'], model: 'ChatGPT', modelColor: '#10B981', promptPreview: 'Write a SaaS hero section for [product] targeting [ICP]. Tone: [confident/approachable]. Include headline, sub-headline, CTA, and 3 social-proof lines.', isTrending: true, useCount: 2780 },
  { id: 'tmpl-004', title: 'Midjourney Product Shoot', description: 'Studio lighting setup for modern electronics, generating clean product photography prompts with controlled depth of field.', category: 'ai-art', tags: ['AI Art', 'Midjourney'], model: 'Midjourney', modelColor: '#F59E0B', promptPreview: '[Product] on [surface], studio lighting, shallow depth of field, [color] background, commercial photography, 8k --ar 4:3 --style raw', isTrending: true, useCount: 2310 },
  { id: 'tmpl-005', title: 'YouTube Hook Generator', description: 'Generate first 30-second retention-optimized hooks with pattern interrupt, curiosity gap, and payoff structure.', category: 'youtube', tags: ['YouTube', 'Video'], model: 'GPT-4o', modelColor: '#EF4444', promptPreview: 'Write a 30-second YouTube hook for a video about [topic]. Use pattern interrupt, open a curiosity gap, and tease the payoff. Channel voice: [casual/authoritative].', isTrending: true, useCount: 1955 },
  { id: 'tmpl-006', title: 'API Documentation Writer', description: 'Generate clean, developer-friendly REST API documentation with request/response examples and error codes.', category: 'coding', tags: ['Coding', 'Documentation'], model: 'Claude Sonnet', modelColor: '#0EA5E9', promptPreview: 'Document this API endpoint: [endpoint]. Include: description, params table, request/response JSON, status codes, example in [language].', isNew: true, useCount: 890 },
  { id: 'tmpl-007', title: 'Storytelling Narrative Arc', description: 'Craft compelling narrative arcs using the 3-act structure with character development and emotional beats.', category: 'storytelling', tags: ['Storytelling', 'Creative'], model: 'Claude Sonnet', modelColor: '#0EA5E9', promptPreview: 'Write a [genre] short story about [character] who must [conflict]. Use 3-act structure. Tone: [dark/hopeful]. Word count: [500/1000].', useCount: 1420 },
  { id: 'tmpl-008', title: 'Investor Pitch Deck Script', description: 'Create slide-by-slide pitch deck scripts for Series A/B startups with problem, solution, market, and traction narrative.', category: 'business', tags: ['Business', 'Startup'], model: 'GPT-4o', modelColor: '#EF4444', promptPreview: 'Write a 10-slide pitch deck for [startup] in [industry]. Stage: [Seed/Series A]. Include: problem, solution, TAM, traction, team, ask.', useCount: 1135 },
  { id: 'tmpl-009', title: 'Brand Identity Prompt Pack', description: 'Generate consistent visual identity prompts for logos, color palettes, and brand guidelines across AI art tools.', category: 'ai-art', tags: ['AI Art', 'Branding'], model: 'DALL-E 3', modelColor: '#F59E0B', promptPreview: 'Logo for [brand] in [industry]. Style: [minimalist/bold]. Colors: [palette]. Format: vector-flat, white background, centered composition.', isNew: true, useCount: 678 },
  { id: 'tmpl-010', title: 'Cold Email Sequence', description: 'Write a 5-email cold outreach sequence with subject line variants, personalization hooks, and follow-up cadence.', category: 'marketing', tags: ['Marketing', 'Email'], model: 'ChatGPT', modelColor: '#10B981', promptPreview: 'Write 5-email cold sequence targeting [persona] at [company size]. Product: [description]. Pain point: [X]. CTA: [meeting/demo]. Tone: [direct/consultative].', useCount: 2100 },
  { id: 'tmpl-011', title: 'Short-Form Video Script', description: 'TikTok & Reels script generator with hook, value delivery, and viral CTA structure built in.', category: 'youtube', tags: ['YouTube', 'TikTok'], model: 'GPT-4o', modelColor: '#EF4444', promptPreview: 'Write a 60-second script for [platform] about [topic]. Hook in first 3s, deliver [main value] in middle, end with [CTA]. Tone: [energetic/calm].', useCount: 1750 },
  { id: 'tmpl-012', title: 'VEO B-Roll Scene Pack', description: 'Generate sets of complementary B-roll footage descriptions for documentary and brand video production.', category: 'veo', tags: ['VEO', 'B-Roll'], model: 'VEO Video Model', modelColor: '#8B5CF6', promptPreview: 'Generate 5 B-roll shots for a [brand/doc] video about [topic]. Each shot: camera angle, subject action, lighting, duration. Mood: [corporate/editorial].', isNew: true, useCount: 540 },
];

const CATEGORIES: Category[] = [
  { id: 'all', label: 'All', icon: Sparkles }, { id: 'youtube', label: 'YouTube', icon: Video },
  { id: 'coding', label: 'Coding', icon: Code2 }, { id: 'marketing', label: 'Marketing', icon: Megaphone },
  { id: 'ai-art', label: 'AI Art', icon: Palette }, { id: 'veo', label: 'VEO', icon: Film },
  { id: 'storytelling', label: 'Storytelling', icon: BookOpen }, { id: 'business', label: 'Business', icon: Briefcase },
];

const CATEGORY_ICON_MAP: Record<string, React.ElementType> = {
  coding: Code2, marketing: Megaphone, 'ai-art': Palette, veo: Film, youtube: Video, storytelling: BookOpen, business: Briefcase,
};

/* ── Template Card ── */
function TemplateCard({ template }: { template: Template }) {
  const [bookmarked, setBookmarked] = useState(false);
  const [copied,     setCopied]     = useState(false);
  const Icon = CATEGORY_ICON_MAP[template.category] || Sparkles;

  return (
    <div id={`template-card-${template.id}`} style={{
      background: '#FFFFFF', border: '1px solid rgba(124,58,237,0.10)', borderRadius: 20, padding: 24,
      display: 'flex', flexDirection: 'column', gap: 12, position: 'relative', overflow: 'hidden',
      boxShadow: '0 2px 10px rgba(109,40,217,0.05)', transition: 'transform 250ms ease, box-shadow 250ms ease, border-color 250ms ease',
    }}
    className="hover:translate-y-[-3px] hover:shadow-[0_8px_28px_rgba(109,40,217,0.10)] hover:!border-[rgba(124,58,237,0.18)]"
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: `${template.modelColor}18`, color: template.modelColor, border: `1px solid ${template.modelColor}25`,
        }}>
          <Icon size={17} strokeWidth={1.5} />
        </div>
        <button id={`bookmark-${template.id}`} onClick={e => { e.stopPropagation(); setBookmarked(!bookmarked); }}
          style={{
            width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 8, border: 'none', cursor: 'pointer', transition: 'all 200ms ease',
            background: bookmarked ? 'rgba(124,58,237,0.12)' : 'transparent',
            color: bookmarked ? 'var(--color-primary)' : 'rgba(107,107,138,0.45)',
          }}
          className={!bookmarked ? 'hover:!bg-[rgba(124,58,237,0.08)] hover:!text-[var(--color-primary)]' : ''}
        >
          {bookmarked ? <BookmarkCheck size={14} strokeWidth={2} /> : <Bookmark size={14} strokeWidth={2} />}
        </button>
      </div>

      <div>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)', margin: '0 0 6px', letterSpacing: -0.2 }}>{template.title}</h3>
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.5, margin: 0, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{template.description}</p>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {template.tags.slice(0, 2).map(tag => (
          <span key={tag} style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 9999, background: 'rgba(124,58,237,0.08)', color: 'var(--color-primary)' }}>{tag}</span>
        ))}
        {template.isNew && <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 9999, background: 'rgba(16,185,129,0.10)', color: '#059669', border: '1px solid rgba(16,185,129,0.20)' }}>New</span>}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: 8, borderTop: '1px solid rgba(124,58,237,0.07)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--color-text-secondary)' }}>
          <Star size={10} strokeWidth={2} />{template.useCount?.toLocaleString() ?? '0'}
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button id={`copy-${template.id}`} onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(template.promptPreview); setCopied(true); setTimeout(() => setCopied(false), 1800); }}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 7, fontSize: 12, fontWeight: 500, border: '1px solid rgba(124,58,237,0.14)', cursor: 'pointer', background: 'transparent', color: 'var(--color-text-secondary)', transition: 'all 180ms ease' }}
            className="hover:!bg-[rgba(124,58,237,0.06)] hover:!text-[var(--color-primary)] hover:!border-[rgba(124,58,237,0.22)]"
          ><Copy size={12} strokeWidth={2} />{copied ? 'Copied' : 'Copy'}</button>
          <button id={`use-${template.id}`}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer', background: 'linear-gradient(135deg, #7C3AED, #A855F7)', color: 'white', boxShadow: '0 3px 10px rgba(124,58,237,0.28)', transition: 'all 180ms ease' }}
            className="hover:translate-y-[-1px] hover:brightness-105"
          ><Zap size={12} strokeWidth={2} />Use</button>
        </div>
      </div>
    </div>
  );
}

/* ── Featured Hero ── */
function FeaturedHero({ template }: { template: Template }) {
  const [copied, setCopied] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);
  return (
    <div id="featured-template-hero" style={{
      borderRadius: 24, overflow: 'hidden', marginBottom: 40, position: 'relative',
      background: 'linear-gradient(135deg, #1a0a3d 0%, #2D1B69 40%, #0E0B18 100%)',
      boxShadow: '0 8px 32px rgba(109,40,217,0.22), 0 2px 8px rgba(0,0,0,0.12)',
      minHeight: 240,
    }}>
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 30% 50%, rgba(167,139,250,0.18) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(124,58,237,0.15) 0%, transparent 50%)' }} />
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', padding: '40px 48px', gap: 40 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.18)', borderRadius: 9999, padding: '4px 12px', fontSize: 12, fontWeight: 600, color: '#EDE9FE', marginBottom: 16 }}>
            <Film size={13} strokeWidth={2} /><span>{template.model}</span>
          </div>
          <h2 style={{ fontSize: 26, fontWeight: 800, color: '#EDE9FE', letterSpacing: -0.5, margin: '0 0 10px', lineHeight: 1.2 }}>{template.title}</h2>
          <p style={{ fontSize: 14, color: 'rgba(221,214,254,0.60)', margin: '0 0 20px', lineHeight: 1.5 }}>{template.description}</p>
          <div style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 10, padding: '14px 18px', fontSize: 13, color: 'rgba(221,214,254,0.75)', fontFamily: 'monospace', lineHeight: 1.5, marginBottom: 24 }}>
            {template.promptPreview}
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button id="hero-use-optimizer-btn" style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 20px', borderRadius: 10, fontSize: 14, fontWeight: 700, border: 'none', cursor: 'pointer', background: 'linear-gradient(135deg, #7C3AED, #A855F7)', color: 'white', boxShadow: '0 4px 16px rgba(124,58,237,0.45)', transition: 'all 200ms ease' }} className="hover:brightness-110 hover:translate-y-[-1px]">
              <Zap size={15} strokeWidth={2} />Use in Optimizer
            </button>
            <button id="hero-copy-btn" onClick={() => { navigator.clipboard.writeText(template.promptPreview); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
              style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 18px', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer', background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.20)', color: '#EDE9FE', transition: 'all 200ms ease' }} className="hover:!bg-[rgba(255,255,255,0.18)]">
              <Copy size={14} strokeWidth={2} />{copied ? 'Copied!' : 'Copy Prompt'}
            </button>
            <button id="hero-bookmark-btn" onClick={() => setBookmarked(!bookmarked)}
              style={{ width: 42, height: 42, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 10, cursor: 'pointer', border: '1px solid rgba(255,255,255,0.20)', background: bookmarked ? 'rgba(124,58,237,0.40)' : 'rgba(255,255,255,0.10)', color: '#EDE9FE', transition: 'all 200ms ease' }}>
              {bookmarked ? <BookmarkCheck size={16} strokeWidth={2} /> : <Bookmark size={16} strokeWidth={2} />}
            </button>
          </div>
        </div>
        <div style={{ flex: '0 0 280px', position: 'relative' }}>
          <div style={{ borderRadius: 16, overflow: 'hidden', boxShadow: '0 8px 32px rgba(0,0,0,0.30)', border: '1px solid rgba(255,255,255,0.10)' }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/cinematic-hero.png" alt="Cinematic establishing shot" style={{ width: '100%', height: 160, objectFit: 'cover', display: 'block' }} />
            <div style={{ position: 'absolute', bottom: 10, left: 10, display: 'flex', alignItems: 'center', gap: 5, background: 'rgba(0,0,0,0.60)', backdropFilter: 'blur(8px)', borderRadius: 8, padding: '5px 10px', fontSize: 11, fontWeight: 600, color: 'white' }}>
              <Film size={12} /><span>VEO</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main Page ── */
export default function TemplatesPage() {
  const [activeCategory, setActiveCategory] = useState('all');
  const [searchQuery,    setSearchQuery]    = useState('');

  const featuredTemplate = DUMMY_TEMPLATES.find(t => t.isFeatured)!;
  const filteredTemplates = useMemo(() => {
    let list = DUMMY_TEMPLATES.filter(t => !t.isFeatured);
    if (activeCategory !== 'all') list = list.filter(t => t.category === activeCategory);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(t => t.title.toLowerCase().includes(q) || t.description.toLowerCase().includes(q) || t.tags.some(tag => tag.toLowerCase().includes(q)));
    }
    return list;
  }, [activeCategory, searchQuery]);

  const trendingTemplates  = filteredTemplates.filter(t => t.isTrending);
  const allOtherTemplates  = filteredTemplates.filter(t => !t.isTrending);

  const sectionTitle: React.CSSProperties = { fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)', margin: 0 };

  return (
    <div id="templates-page" style={{ maxWidth: 1100, margin: '0 auto', padding: '0 48px 64px', paddingTop: 8, width: '100%', display: 'flex', flexDirection: 'column' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '32px 0 24px' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: -0.3, margin: '0 0 4px' }}>Templates Library</h1>
          <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', margin: 0 }}>Discover curated, high-performance prompts optimized for precision and scale</p>
        </div>
        <div style={{ position: 'relative' }}>
          <Search size={15} strokeWidth={1.8} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-secondary)', pointerEvents: 'none' }} />
          <input id="templates-search-input" type="text" placeholder="Search templates..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            style={{ padding: '9px 16px 9px 36px', fontSize: 13, background: '#FFFFFF', border: '1px solid rgba(124,58,237,0.12)', borderRadius: 10, outline: 'none', color: 'var(--color-text-primary)', width: 240, transition: 'border-color 200ms ease, box-shadow 200ms ease' }}
            className="focus:!border-[rgba(124,58,237,0.35)] focus:shadow-[0_0_0_3px_rgba(124,58,237,0.08)]"
          />
        </div>
      </div>

      {/* Category Chips */}
      <div id="categories-row" style={{ display: 'flex', gap: 8, marginBottom: 32, flexWrap: 'wrap' }}>
        {CATEGORIES.map(cat => {
          const Icon    = cat.icon;
          const active  = activeCategory === cat.id;
          return (
            <button key={cat.id} id={`category-chip-${cat.id}`} onClick={() => setActiveCategory(cat.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 9999, fontSize: 13, fontWeight: active ? 700 : 500, cursor: 'pointer', transition: 'all 200ms ease',
                background: active ? 'linear-gradient(135deg, #7C3AED, #A855F7)' : 'rgba(124,58,237,0.06)',
                color: active ? 'white' : 'var(--color-text-secondary)',
                border: active ? 'none' : '1px solid rgba(124,58,237,0.10)',
                boxShadow: active ? '0 4px 12px rgba(124,58,237,0.28)' : 'none',
              }}
              className={!active ? 'hover:!bg-[rgba(124,58,237,0.10)] hover:!text-[var(--color-text-primary)]' : ''}
            >
              <Icon size={14} strokeWidth={1.8} /><span>{cat.label}</span>
            </button>
          );
        })}
      </div>

      {/* Featured Hero */}
      {(activeCategory === 'all' || activeCategory === 'veo') && !searchQuery && <FeaturedHero template={featuredTemplate} />}

      {/* Trending */}
      {trendingTemplates.length > 0 && (
        <section id="trending-section" style={{ marginBottom: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <TrendingUp size={16} strokeWidth={2} style={{ color: 'var(--color-primary)' }} />
              <h2 style={sectionTitle}>Trending Templates</h2>
            </div>
            <button id="view-all-trending-btn" style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, fontWeight: 600, color: 'var(--color-primary)', background: 'none', border: 'none', cursor: 'pointer' }} className="hover:underline">
              View all <ChevronRight size={14} />
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 20 }}>
            {trendingTemplates.map(t => <TemplateCard key={t.id} template={t} />)}
          </div>
        </section>
      )}

      {/* All others */}
      {allOtherTemplates.length > 0 && (
        <section id="all-templates-section">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <Sparkles size={16} strokeWidth={2} style={{ color: 'var(--color-primary)' }} />
            <h2 style={sectionTitle}>{activeCategory === 'all' ? 'More Templates' : 'Templates'}</h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 20 }}>
            {allOtherTemplates.map(t => <TemplateCard key={t.id} template={t} />)}
          </div>
        </section>
      )}

      {/* Empty */}
      {filteredTemplates.length === 0 && (
        <div id="templates-empty-state" style={{ textAlign: 'center', padding: '64px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 60, height: 60, borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(124,58,237,0.08)', color: 'var(--color-primary)' }}><Search size={32} strokeWidth={1.2} /></div>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>No templates found</h3>
          <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', margin: 0 }}>Try adjusting your search or switching categories.</p>
          <button id="templates-reset-btn" onClick={() => { setSearchQuery(''); setActiveCategory('all'); }}
            style={{ marginTop: 8, padding: '8px 20px', borderRadius: 9, fontSize: 13, fontWeight: 600, border: '1px solid rgba(124,58,237,0.20)', cursor: 'pointer', background: 'transparent', color: 'var(--color-primary)' }}
            className="hover:bg-[rgba(124,58,237,0.06)]"
          >Clear filters</button>
        </div>
      )}
    </div>
  );
}
