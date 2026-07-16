'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Copy, Wand2, Bookmark, TrendingUp, Clock, ArrowRight,
  CheckCircle2, AlertTriangle, Minus, GitCompareArrows,
  Sparkles, Code, Search, Megaphone, BookOpen, Image as ImageIcon,
  Film, PlaySquare, ChevronDown
} from 'lucide-react';
import VersionHeader from './VersionHeader';
import VersionHistoryDrawer from './VersionHistoryDrawer';

// ── Types ──────────────────────────────────────────────────────────────────────
interface Dimension {
  id: string;
  label: string;
  status: 'good' | 'warning' | 'neutral';
  icon: React.ElementType;
  desc: string;
  score: number;
}

interface PromptVersion {
  versionNumber: number;
  optimizedPrompt: string;
  overallScore: number;
  dimensions: Dimension[];
  wordsAfter: number;
  tokensAfter: number;
  timestamp: string;
  tweakNote?: string;
  isStarred?: boolean;
}

interface OptimizationSession {
  id: string;
  originalPrompt: string;
  mode: string;
  modeIcon: React.ElementType;
  wordsBefore: number;
  tokensBefore: number;
  createdAt: string;
  versions: PromptVersion[];
}

// ── Mock Sessions ──────────────────────────────────────────────────────────────
const MOCK_SESSIONS: Record<string, OptimizationSession> = {
  r1: {
    id: 'r1',
    originalPrompt: 'Write a viral Twitter thread about AI in healthcare',
    mode: 'Marketing',
    modeIcon: Megaphone,
    wordsBefore: 10,
    tokensBefore: 14,
    createdAt: '2 min ago',
    versions: [
      {
        versionNumber: 1,
        optimizedPrompt: 'Role: Social media copywriter.\n\nTask: Write a Twitter thread about AI in healthcare.\n\nFormat: Use numbered tweets. Keep each under 280 characters.',
        overallScore: 62,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Task is defined but generic.', score: 70 },
          { id: 'context', label: 'Context', status: 'warning', icon: AlertTriangle, desc: 'No specific healthcare area.', score: 55 },
          { id: 'role', label: 'Role', status: 'good', icon: CheckCircle2, desc: 'Basic persona assigned.', score: 68 },
          { id: 'format', label: 'Format', status: 'neutral', icon: Minus, desc: 'Minimal structure.', score: 58 },
          { id: 'constraints', label: 'Constraints', status: 'warning', icon: AlertTriangle, desc: 'Only character limit given.', score: 52 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No examples provided.', score: 40 },
        ],
        wordsAfter: 28,
        tokensAfter: 42,
        timestamp: '5 min ago',
      },
      {
        versionNumber: 2,
        optimizedPrompt: 'Role: Viral social media strategist with expertise in healthcare technology.\n\nTask: Write a 10-tweet Twitter thread about how AI is transforming healthcare. Each tweet under 280 characters.\n\nFormat:\n• Start with a provocative hook\n• Use data points and real examples\n• Include relevant emojis\n• End with a call-to-action\n\nTone: Conversational yet authoritative.',
        overallScore: 81,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Clear task with tweet count.', score: 85 },
          { id: 'context', label: 'Context', status: 'good', icon: CheckCircle2, desc: 'Healthcare tech focus specified.', score: 78 },
          { id: 'role', label: 'Role', status: 'good', icon: CheckCircle2, desc: 'Specific expert persona.', score: 88 },
          { id: 'format', label: 'Format', status: 'good', icon: CheckCircle2, desc: 'Structure with bullets.', score: 82 },
          { id: 'constraints', label: 'Constraints', status: 'warning', icon: AlertTriangle, desc: 'Tone defined but no content boundaries.', score: 72 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No example tweets given.', score: 55 },
        ],
        wordsAfter: 58,
        tokensAfter: 82,
        timestamp: '4 min ago',
        tweakNote: 'More specific and add formatting requirements',
      },
      {
        versionNumber: 3,
        optimizedPrompt: 'Role: You are a viral social media strategist with expertise in healthcare technology trends.\n\nTask: Write a 10-tweet Twitter thread about how AI is transforming healthcare. Each tweet must be under 280 characters.\n\nFormat:\n• Start with a provocative hook tweet that challenges conventional wisdom\n• Use data points and real examples (cite sources)\n• Include relevant emojis for visual engagement\n• End with a call-to-action for discussion\n\nTone: Conversational yet authoritative. Avoid jargon. Write for a general audience.\n\nConstraints: No medical advice. Focus on trends, not specific products.',
        overallScore: 94,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Task is precisely defined with character limits.', score: 95 },
          { id: 'context', label: 'Context', status: 'good', icon: CheckCircle2, desc: 'Healthcare AI context well established.', score: 92 },
          { id: 'role', label: 'Role', status: 'good', icon: CheckCircle2, desc: 'Specific expert persona assigned.', score: 96 },
          { id: 'format', label: 'Format', status: 'good', icon: CheckCircle2, desc: 'Thread structure with bullet requirements.', score: 94 },
          { id: 'constraints', label: 'Constraints', status: 'good', icon: CheckCircle2, desc: 'Clear boundaries on content scope.', score: 91 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No examples provided, but format is clear.', score: 88 },
        ],
        wordsAfter: 89,
        tokensAfter: 124,
        timestamp: '2 min ago',
        tweakNote: 'Add constraints and audience targeting',
      },
      // Generate 50 mock versions to test virtualization
      ...Array.from({ length: 50 }).map((_, i) => ({
        versionNumber: 4 + i,
        optimizedPrompt: `This is a generated mock prompt for version ${4 + i}. It includes some test content to simulate length and variety.\n\nRole: Social Media Strategist\n\nTask: Test virtualization performance.\n\nNote: Auto-generated for UI testing.`,
        overallScore: 60 + ((i * 17 + 23) % 40),
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good' as const, icon: CheckCircle2, desc: 'Auto-generated', score: 85 },
          { id: 'context', label: 'Context', status: 'good' as const, icon: CheckCircle2, desc: 'Auto-generated', score: 80 },
          { id: 'role', label: 'Role', status: 'good' as const, icon: CheckCircle2, desc: 'Auto-generated', score: 85 },
          { id: 'format', label: 'Format', status: 'good' as const, icon: CheckCircle2, desc: 'Auto-generated', score: 80 },
          { id: 'constraints', label: 'Constraints', status: 'warning' as const, icon: AlertTriangle, desc: 'Auto-generated', score: 70 },
          { id: 'examples', label: 'Examples', status: 'neutral' as const, icon: Minus, desc: 'Auto-generated', score: 50 },
        ],
        wordsAfter: 45,
        tokensAfter: 60,
        timestamp: `${i + 1}m ago`,
        tweakNote: i % 3 === 0 ? 'Tweak auto generated' : undefined,
        isStarred: i % 10 === 0,
      })),
    ],
  },
  r2: {
    id: 'r2',
    originalPrompt: 'Debug my React useEffect infinite loop issue',
    mode: 'Coding',
    modeIcon: Code,
    wordsBefore: 8,
    tokensBefore: 11,
    createdAt: '1 hour ago',
    versions: [
      {
        versionNumber: 1,
        optimizedPrompt: 'Help me fix an infinite loop in my React useEffect hook. The component re-renders endlessly when I update state inside the effect.\n\nProvide common causes and solutions with code examples.',
        overallScore: 58,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Problem stated clearly.', score: 65 },
          { id: 'context', label: 'Context', status: 'warning', icon: AlertTriangle, desc: 'No code context provided.', score: 48 },
          { id: 'role', label: 'Role', status: 'neutral', icon: Minus, desc: 'No expert persona.', score: 30 },
          { id: 'format', label: 'Format', status: 'neutral', icon: Minus, desc: 'Basic output request.', score: 52 },
          { id: 'constraints', label: 'Constraints', status: 'warning', icon: AlertTriangle, desc: 'No tech stack version info.', score: 60 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No code samples.', score: 45 },
        ],
        wordsAfter: 30,
        tokensAfter: 44,
        timestamp: '1h 5m ago',
      },
      {
        versionNumber: 2,
        optimizedPrompt: 'Role: Senior React developer and debugging expert.\n\nContext: I have a React functional component using useEffect that creates an infinite re-render loop. The component fetches data and updates state.\n\nTask: Diagnose and fix the infinite loop. Provide:\n1. Common root causes (dependency array issues, object references, state updates)\n2. Step-by-step debugging approach\n3. Corrected code pattern with explanation\n4. Best practices to prevent this\n\nFormat: Use TypeScript code blocks. Include before/after comparisons.\n\nConstraints: React 18+, functional components only.',
        overallScore: 88,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Debugging steps clearly requested.', score: 90 },
          { id: 'context', label: 'Context', status: 'good', icon: CheckCircle2, desc: 'React version specified.', score: 88 },
          { id: 'role', label: 'Role', status: 'good', icon: CheckCircle2, desc: 'Senior developer persona.', score: 92 },
          { id: 'format', label: 'Format', status: 'good', icon: CheckCircle2, desc: 'Numbered output with code blocks.', score: 86 },
          { id: 'constraints', label: 'Constraints', status: 'good', icon: CheckCircle2, desc: 'Tech constraints well defined.', score: 85 },
          { id: 'examples', label: 'Examples', status: 'warning', icon: AlertTriangle, desc: 'Before/after requested but no input.', score: 78 },
        ],
        wordsAfter: 78,
        tokensAfter: 108,
        timestamp: '1h ago',
        tweakNote: 'Add role, structure, and constraints',
      },
    ],
  },
  r3: {
    id: 'r3',
    originalPrompt: 'Cinematic shot of neon rain on cyberpunk streets',
    mode: 'Cinematic Video',
    modeIcon: Film,
    wordsBefore: 9,
    tokensBefore: 12,
    createdAt: '3 hours ago',
    versions: [
      {
        versionNumber: 1,
        optimizedPrompt: 'A cinematic shot of a cyberpunk city street at night with neon rain. Include neon lights, wet streets, and a dark atmosphere. High resolution, photorealistic.',
        overallScore: 52,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'neutral', icon: Minus, desc: 'Basic scene description.', score: 55 },
          { id: 'context', label: 'Context', status: 'warning', icon: AlertTriangle, desc: 'No aesthetic references.', score: 42 },
          { id: 'role', label: 'Role', status: 'neutral', icon: Minus, desc: 'No director or style persona.', score: 20 },
          { id: 'format', label: 'Format', status: 'warning', icon: AlertTriangle, desc: 'Flat text, no structure.', score: 38 },
          { id: 'constraints', label: 'Constraints', status: 'warning', icon: AlertTriangle, desc: 'Resolution mentioned, no aspect ratio.', score: 50 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No reference images or films.', score: 48 },
        ],
        wordsAfter: 28,
        tokensAfter: 38,
        timestamp: '3h 10m ago',
      },
      {
        versionNumber: 2,
        optimizedPrompt: 'Subject: A bustling cyberpunk city street at night, torrential neon-lit rain.\n\nLighting: Magenta and cyan neon reflections on wet asphalt. Holographic ads glow.\n\nCamera: Wide establishing shot, anamorphic lens.\n\nTechnical: 8K, photorealistic, volumetric lighting, Unreal Engine 5, Blade Runner aesthetic.',
        overallScore: 76,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Scene elements described.', score: 80 },
          { id: 'context', label: 'Context', status: 'good', icon: CheckCircle2, desc: 'Blade Runner reference added.', score: 75 },
          { id: 'role', label: 'Role', status: 'neutral', icon: Minus, desc: 'No director persona.', score: 40 },
          { id: 'format', label: 'Format', status: 'good', icon: CheckCircle2, desc: 'Sectioned by element.', score: 82 },
          { id: 'constraints', label: 'Constraints', status: 'good', icon: CheckCircle2, desc: 'Tech specs and engine specified.', score: 80 },
          { id: 'examples', label: 'Examples', status: 'good', icon: CheckCircle2, desc: 'Film reference anchors style.', score: 78 },
        ],
        wordsAfter: 52,
        tokensAfter: 72,
        timestamp: '3h 5m ago',
        tweakNote: 'Add structure and technical specs',
      },
      {
        versionNumber: 3,
        optimizedPrompt: 'Subject & Setting: A cinematic, ultra-wide establishing shot of a bustling cyberpunk city street at night. Torrential neon-lit rain cascades down, each droplet catching magenta and cyan reflections off the slick, hyper-detailed asphalt.\n\nLighting & Atmosphere: Towering holographic advertisements pulse with light, casting vibrant chromatic glows over silhouetted pedestrians carrying translucent glowing umbrellas. Dense atmospheric fog interweaves with the rain, creating volumetric god-rays from streetlights.\n\nCamera & Composition: A lone figure in a dark trench coat stands at a crosswalk, their face illuminated by the warm glow of a ramen stall. Anamorphic lens, shallow depth of field.\n\nTechnical: 8K resolution, photorealistic, volumetric lighting, Unreal Engine 5 render, Blade Runner 2049 aesthetic, Roger Deakins cinematography, --ar 21:9 --v 6.',
        overallScore: 91,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Scene elements described precisely.', score: 93 },
          { id: 'context', label: 'Context', status: 'good', icon: CheckCircle2, desc: 'Genre and aesthetic references provided.', score: 90 },
          { id: 'role', label: 'Role', status: 'neutral', icon: Minus, desc: 'No director persona, but style refs suffice.', score: 72 },
          { id: 'format', label: 'Format', status: 'good', icon: CheckCircle2, desc: 'Structured by scene elements.', score: 95 },
          { id: 'constraints', label: 'Constraints', status: 'good', icon: CheckCircle2, desc: 'Technical specs and aspect ratio defined.', score: 92 },
          { id: 'examples', label: 'Examples', status: 'good', icon: CheckCircle2, desc: 'Blade Runner + Deakins reference.', score: 94 },
        ],
        wordsAfter: 112,
        tokensAfter: 156,
        timestamp: '3h ago',
        tweakNote: 'More detail, atmosphere, and cinematographer reference',
      },
    ],
  },
  r4: {
    id: 'r4',
    originalPrompt: 'Explain quantum entanglement to a 10-year-old',
    mode: 'Research',
    modeIcon: Search,
    wordsBefore: 8,
    tokensBefore: 11,
    createdAt: '5 hours ago',
    versions: [
      {
        versionNumber: 1,
        optimizedPrompt: 'Explain quantum entanglement in simple terms that a child could understand. Use an analogy. Keep it short.',
        overallScore: 48,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'neutral', icon: Minus, desc: 'Topic clear but vague request.', score: 55 },
          { id: 'context', label: 'Context', status: 'warning', icon: AlertTriangle, desc: 'No age level specified.', score: 40 },
          { id: 'role', label: 'Role', status: 'neutral', icon: Minus, desc: 'No persona.', score: 15 },
          { id: 'format', label: 'Format', status: 'warning', icon: AlertTriangle, desc: 'No length or structure.', score: 38 },
          { id: 'constraints', label: 'Constraints', status: 'neutral', icon: Minus, desc: '"Keep it short" is vague.', score: 55 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No analogy examples.', score: 35 },
        ],
        wordsAfter: 18,
        tokensAfter: 24,
        timestamp: '5h 10m ago',
      },
      {
        versionNumber: 2,
        optimizedPrompt: 'Role: You are a science communicator who specializes in explaining complex physics concepts to children using everyday analogies.\n\nTask: Explain quantum entanglement to a 10-year-old student.\n\nRequirements:\n• Use a relatable analogy (e.g., magic coins, twin siblings)\n• Keep vocabulary at a 5th-grade reading level\n• Maximum 200 words\n• Include one "wow factor" statement about real-world implications\n• End with a simple question to check understanding\n\nTone: Enthusiastic, wonder-filled, encouraging.\n\nAvoid: Mathematical formulas, technical jargon, wave function terminology.',
        overallScore: 76,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Target audience and topic clearly defined.', score: 85 },
          { id: 'context', label: 'Context', status: 'good', icon: CheckCircle2, desc: 'Reading level and age group specified.', score: 80 },
          { id: 'role', label: 'Role', status: 'good', icon: CheckCircle2, desc: 'Science communicator persona assigned.', score: 82 },
          { id: 'format', label: 'Format', status: 'good', icon: CheckCircle2, desc: 'Word limit and structure requirements given.', score: 78 },
          { id: 'constraints', label: 'Constraints', status: 'warning', icon: AlertTriangle, desc: 'Avoidance list could be more specific.', score: 65 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'Analogy suggestions given but no full example.', score: 62 },
        ],
        wordsAfter: 72,
        tokensAfter: 98,
        timestamp: '5h ago',
        tweakNote: 'Add role, structure, and age-appropriate constraints',
      },
    ],
  },
  r5: {
    id: 'r5',
    originalPrompt: 'Generate a product launch email sequence',
    mode: 'Marketing',
    modeIcon: Megaphone,
    wordsBefore: 6,
    tokensBefore: 9,
    createdAt: 'Yesterday',
    versions: [
      {
        versionNumber: 1,
        optimizedPrompt: 'Write a series of emails for launching a new product. Include teaser, launch, and follow-up emails.',
        overallScore: 42,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'neutral', icon: Minus, desc: 'Basic structure hinted.', score: 50 },
          { id: 'context', label: 'Context', status: 'warning', icon: AlertTriangle, desc: 'No product type specified.', score: 30 },
          { id: 'role', label: 'Role', status: 'neutral', icon: Minus, desc: 'No marketer persona.', score: 15 },
          { id: 'format', label: 'Format', status: 'warning', icon: AlertTriangle, desc: 'No per-email structure.', score: 38 },
          { id: 'constraints', label: 'Constraints', status: 'neutral', icon: Minus, desc: 'No length or tone constraints.', score: 50 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No sample emails.', score: 45 },
        ],
        wordsAfter: 20,
        tokensAfter: 28,
        timestamp: 'Yesterday',
      },
      {
        versionNumber: 2,
        optimizedPrompt: 'Role: Email marketing strategist with 10+ years of SaaS launch experience.\n\nTask: Create a 5-email product launch drip sequence for a B2B SaaS productivity tool.\n\nSequence Structure:\n• Email 1 (Day -7): Teaser — build anticipation\n• Email 2 (Day -3): Story — the problem you solve\n• Email 3 (Day 0): Launch — full reveal with CTA\n• Email 4 (Day +2): Social proof — early user reactions\n• Email 5 (Day +5): Urgency — limited-time launch pricing\n\nFor Each Email Provide:\n- Subject line (A/B variants)\n- Preview text\n- Body copy (150–200 words)\n- Primary CTA button text\n\nTone: Professional but human. No corporate jargon.\n\nConstraints: Mobile-optimized formatting. Each email must stand alone.',
        overallScore: 83,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Email sequence structure clearly defined.', score: 88 },
          { id: 'context', label: 'Context', status: 'good', icon: CheckCircle2, desc: 'B2B SaaS context established.', score: 82 },
          { id: 'role', label: 'Role', status: 'good', icon: CheckCircle2, desc: 'Email strategist persona assigned.', score: 86 },
          { id: 'format', label: 'Format', status: 'good', icon: CheckCircle2, desc: 'Per-email deliverables specified.', score: 85 },
          { id: 'constraints', label: 'Constraints', status: 'warning', icon: AlertTriangle, desc: 'Mobile formatting noted but no specific rules.', score: 75 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No example emails provided.', score: 68 },
        ],
        wordsAfter: 108,
        tokensAfter: 148,
        timestamp: 'Yesterday',
        tweakNote: 'Full structure with role, deliverables, and constraints',
      },
    ],
  },
  r6: {
    id: 'r6',
    originalPrompt: 'YouTube thumbnail prompt for tech review video',
    mode: 'YouTube Shorts',
    modeIcon: PlaySquare,
    wordsBefore: 7,
    tokensBefore: 10,
    createdAt: 'Yesterday',
    versions: [
      {
        versionNumber: 1,
        optimizedPrompt: 'Create a YouTube thumbnail for a tech review video with bold text and an excited person holding the product.',
        overallScore: 45,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'neutral', icon: Minus, desc: 'Basic concept clear.', score: 52 },
          { id: 'context', label: 'Context', status: 'warning', icon: AlertTriangle, desc: 'No specific product or style.', score: 38 },
          { id: 'role', label: 'Role', status: 'neutral', icon: Minus, desc: 'No designer persona.', score: 15 },
          { id: 'format', label: 'Format', status: 'warning', icon: AlertTriangle, desc: 'No dimensions or composition details.', score: 40 },
          { id: 'constraints', label: 'Constraints', status: 'neutral', icon: Minus, desc: 'No readability constraints.', score: 48 },
          { id: 'examples', label: 'Examples', status: 'neutral', icon: Minus, desc: 'No reference thumbnails.', score: 42 },
        ],
        wordsAfter: 20,
        tokensAfter: 28,
        timestamp: 'Yesterday',
      },
      {
        versionNumber: 2,
        optimizedPrompt: 'Create a YouTube thumbnail image for a tech gadget review video.\n\nComposition:\n• Person with exaggerated shocked/excited facial expression, positioned left-of-center\n• Product (latest smartphone/laptop) held at a dynamic angle, slightly toward camera\n• Background: diagonal split — electric blue (#0066FF) on left, vibrant orange (#FF6600) on right\n\nText Overlay:\n• Large bold white text "GAME CHANGER!" with black drop shadow, positioned top-right\n• Small "vs" badge in red circle, bottom corner\n\nStyle: Hyper-saturated colors, studio lighting on face, shallow DOF on background, 1280×720.\n\nConstraints: Must be readable at small sizes (mobile). Maximum 3 words in text overlay. No fine print.',
        overallScore: 79,
        dimensions: [
          { id: 'clarity', label: 'Clarity', status: 'good', icon: CheckCircle2, desc: 'Visual composition precisely described.', score: 85 },
          { id: 'context', label: 'Context', status: 'good', icon: CheckCircle2, desc: 'Platform and format context given.', score: 82 },
          { id: 'role', label: 'Role', status: 'neutral', icon: Minus, desc: 'No designer persona.', score: 60 },
          { id: 'format', label: 'Format', status: 'good', icon: CheckCircle2, desc: 'Sectioned by composition elements.', score: 84 },
          { id: 'constraints', label: 'Constraints', status: 'good', icon: CheckCircle2, desc: 'Mobile readability and word limit specified.', score: 80 },
          { id: 'examples', label: 'Examples', status: 'warning', icon: AlertTriangle, desc: 'Color hex codes given but no reference image.', score: 72 },
        ],
        wordsAfter: 85,
        tokensAfter: 118,
        timestamp: 'Yesterday',
        tweakNote: 'Full visual composition breakdown with constraints',
      },
    ],
  },
};

const DEFAULT_SESSION: OptimizationSession = {
  id: 'default',
  originalPrompt: 'No session found.',
  mode: 'General',
  modeIcon: Sparkles,
  wordsBefore: 0,
  tokensBefore: 0,
  createdAt: '',
  versions: [
    {
      versionNumber: 1,
      optimizedPrompt: 'Please select a recent optimization from the sidebar.',
      overallScore: 0,
      dimensions: [],
      wordsAfter: 0,
      tokensAfter: 0,
      timestamp: '',
    },
  ],
};

// ── Helpers ────────────────────────────────────────────────────────────────────
function scoreColor(s: number) {
  if (s >= 80) return 'var(--color-success, #10B981)';
  if (s >= 55) return 'var(--color-primary, #7C3AED)';
  return '#F59E0B';
}

function scoreLabel(s: number) {
  if (s >= 90) return 'Excellent';
  if (s >= 75) return 'Good';
  if (s >= 55) return 'Fair';
  return 'Needs Work';
}

function useCountUp(target: number, active: boolean, duration = 1200): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!active) { setValue(0); return; }
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

// ── Component ──────────────────────────────────────────────────────────────────
export default function ChatView({ chatId }: { chatId: string | null }) {
  const session = chatId && MOCK_SESSIONS[chatId] ? MOCK_SESSIONS[chatId] : DEFAULT_SESSION;

  const [activeVersionIndex, setActiveVersionIndex] = useState(session.versions.length - 1);
  const [compareMode, setCompareMode] = useState(false);
  const [compareIndex, setCompareIndex] = useState(0);

  // Selector state
  const [selectedStyle, setSelectedStyle] = useState('None');
  const [isStyleOpen, setIsStyleOpen] = useState(false);
  const [selectedTarget, setSelectedTarget] = useState('Claude');
  const [selectedEngine, setSelectedEngine] = useState('Claude Sonnet 4.5');
  const [isTargetOpen, setIsTargetOpen] = useState(false);

  const styleDropdownRef = useRef<HTMLDivElement>(null);
  const targetDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (styleDropdownRef.current && !styleDropdownRef.current.contains(event.target as Node)) {
        setIsStyleOpen(false);
      }
      if (targetDropdownRef.current && !targetDropdownRef.current.contains(event.target as Node)) {
        setIsTargetOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const styleOptions = [
    { label: 'None', color: '#94A3B8' },
    { label: 'Cinematic Noir', color: '#FBBF24' },
    { label: 'Editorial Warm', color: '#F97316' },
    { label: 'Product Launch Voice', color: '#38BDF8' },
  ];

  const targetModels = [
    'ChatGPT', 'Claude', 'Gemini', 'Grok', 'Midjourney', 'VEO', 'DALL-E', 'Stable Diffusion'
  ];
  const optimizerEngines = ['Claude Sonnet 4.5', 'GPT-5.2'];
  const [ready, setReady] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [hoveredVersionIndex, setHoveredVersionIndex] = useState<number | null>(null);

  const [sessionVersions, setSessionVersions] = useState(session.versions);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const s = chatId && MOCK_SESSIONS[chatId] ? MOCK_SESSIONS[chatId] : DEFAULT_SESSION;
    setSessionVersions(s.versions);
    setActiveVersionIndex(s.versions.length - 1);
    setCompareMode(false);
    setCompareIndex(0);
    setReady(false);
    setIsHistoryOpen(false);
    const t = setTimeout(() => setReady(true), 120);
    return () => clearTimeout(t);
  }, [chatId]);

  const displayVersionIndex = hoveredVersionIndex !== null ? hoveredVersionIndex : activeVersionIndex;
  const version = sessionVersions[displayVersionIndex];
  const activeVersion = sessionVersions[activeVersionIndex];
  const bestIndex = sessionVersions.reduce((best, v, i) => v.overallScore > sessionVersions[best].overallScore ? i : best, 0);

  const animatedScore = useCountUp(activeVersion.overallScore, ready);
  const radius = 44;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (animatedScore / 100) * circ;

  const ModeIcon = session.modeIcon;

  const handleVersionSelect = (index: number) => {
    setActiveVersionIndex(index);
  };

  const handleToggleStar = (index: number) => {
    setSessionVersions(prev => prev.map((v, i) => i === index ? { ...v, isStarred: !v.isStarred } : v));
  };

  // Render a prompt panel
  const renderOptimizedPanel = (v: PromptVersion, label: string) => (
    <div style={{
      flex: 1, background: '#FFFFFF', borderRadius: 20, padding: 24,
      boxShadow: '0 4px 20px rgba(109,40,217,0.06), 0 1px 3px rgba(0,0,0,0.03)',
      border: '1px solid rgba(124,58,237,0.12)', display: 'flex', flexDirection: 'column',
      position: 'relative', overflow: 'hidden', minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 9999,
          fontSize: 12, fontWeight: 700, letterSpacing: '0.3px',
          background: 'linear-gradient(135deg, rgba(124,58,237,0.12), rgba(168,85,247,0.15))',
          color: '#6D28D9', border: '1px solid rgba(124,58,237,0.18)',
        }}>
          <Wand2 size={13} />
          <span>{label}</span>
        </div>
        <span style={{ fontSize: 20, fontWeight: 800, color: scoreColor(v.overallScore) }}>
          {v.overallScore}
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', maxHeight: 380, paddingRight: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {v.optimizedPrompt.split('\n').map((line, i) => {
          const isHeader = /^(Role|Task|Context|Format|Tone|Constraints|Requirements|Subject|Lighting|Camera|Technical|Composition|Style|Text|Sequence|For Each|Avoid)[\s&:]/i.test(line.trim());
          const isBullet = line.trim().startsWith('•') || line.trim().startsWith('-') || /^\d+[.)]/.test(line.trim());
          return (
            <React.Fragment key={i}>
              {line.trim() === '' ? (
                <div style={{ height: 6 }} />
              ) : isHeader ? (
                <p style={{ fontSize: 13, fontWeight: 700, color: '#3B1082', marginTop: 4, marginBottom: 2 }}>{line}</p>
              ) : isBullet ? (
                <p style={{ fontSize: 13.5, lineHeight: 1.6, color: '#334155', paddingLeft: 12 }}>{line}</p>
              ) : (
                <p style={{ fontSize: 13.5, lineHeight: 1.6, color: '#334155', margin: 0 }}>{line}</p>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {v.tweakNote && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginTop: 16, paddingTop: 14,
          borderTop: '1px dashed rgba(124,58,237,0.16)', fontSize: 12, color: '#6D28D9', fontWeight: 600,
        }}>
          <Wand2 size={13} style={{ flexShrink: 0 }} />
          <span>{v.tweakNote}</span>
        </div>
      )}
    </div>
  );

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%', flex: 1, overflowY: 'auto',
      padding: '20px 48px ', background: 'var(--color-canvas, #FAFBFC)', gap: 28,
    }}>
      {/* Header Bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 20px', background: 'rgba(255,255,255,0.85)', borderRadius: 16,
        border: '1px solid rgba(124,58,237,0.10)', boxShadow: '0 2px 12px rgba(109,40,217,0.04)',
        backdropFilter: 'blur(12px)',
        maxWidth: 1100, margin: '0 auto', width: '100%', boxSizing: 'border-box'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 7, padding: '6px 14px', borderRadius: 9999,
            fontSize: 12.5, fontWeight: 700, background: 'rgba(124,58,237,0.11)', color: '#6D28D9',
          }}>
            <ModeIcon size={14} />
            <span>{session.mode}</span>
          </div>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#64748B', fontWeight: 500 }}>
            <Clock size={13} />
            {session.createdAt}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {sessionVersions.length > 1 && (
            <button
              onClick={() => { setCompareMode(!compareMode); if (!compareMode) setCompareIndex(0); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 10,
                fontSize: 12.5, fontWeight: 600, cursor: 'pointer', transition: 'all 160ms ease',
                background: compareMode ? 'linear-gradient(135deg, #6D28D9, #7C3AED)' : 'rgba(124,58,237,0.07)',
                color: compareMode ? 'white' : '#6D28D9', border: '1px solid rgba(124,58,237,0.15)',
              }}
            >
              <GitCompareArrows size={14} />
              <span>{compareMode ? 'Exit Compare' : 'Compare'}</span>
            </button>
          )}

          {/* Style dropdown */}
          <div style={{ position: 'relative' }} ref={styleDropdownRef}>
            <button
              onClick={() => setIsStyleOpen(!isStyleOpen)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '7px 14px', borderRadius: 10,
                fontSize: 12.5, fontWeight: 600, background: 'rgba(255,255,255,0.90)',
                border: '1px solid rgba(124,58,237,0.15)', color: '#334155', cursor: 'pointer',
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: styleOptions.find(o => o.label === selectedStyle)?.color }} />
              Style <span style={{ color: '#CBD5E1' }}>|</span> <span style={{ color: '#1E293B' }}>{selectedStyle}</span>
              <ChevronDown size={14} style={{ color: '#94A3B8' }} />
            </button>
            {isStyleOpen && (
              <div style={{
                position: 'absolute', top: 'calc(100% + 6px)', right: 0, width: 220, background: '#FFFFFF',
                borderRadius: 14, boxShadow: '0 10px 30px rgba(0,0,0,0.12)', border: '1px solid rgba(124,58,237,0.12)',
                padding: 6, zIndex: 50,
              }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#94A3B8', padding: '6px 10px 4px', letterSpacing: '0.6px' }}>STYLE MEMORY</div>
                {styleOptions.map(opt => (
                  <div
                    key={opt.label} onClick={() => { setSelectedStyle(opt.label); setIsStyleOpen(false); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 8,
                      fontSize: 12.5, fontWeight: 600, color: selectedStyle === opt.label ? '#6D28D9' : '#334155',
                      background: selectedStyle === opt.label ? 'rgba(124,58,237,0.08)' : 'transparent', cursor: 'pointer',
                    }}
                    className="hover:bg-[rgba(124,58,237,0.05)]"
                  >
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: opt.color }} />
                    {opt.label}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Target dropdown */}
          <div style={{ position: 'relative' }} ref={targetDropdownRef}>
            <button
              onClick={() => setIsTargetOpen(!isTargetOpen)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '7px 14px', borderRadius: 10,
                fontSize: 12.5, fontWeight: 600, background: 'rgba(255,255,255,0.90)',
                border: '1px solid rgba(124,58,237,0.15)', color: '#334155', cursor: 'pointer',
              }}
            >
              Target <span style={{ color: '#CBD5E1' }}>|</span> <span style={{ color: '#1E293B' }}>{selectedTarget}</span>
              <ChevronDown size={14} style={{ color: '#94A3B8' }} />
            </button>
            {isTargetOpen && (
              <div style={{
                position: 'absolute', top: 'calc(100% + 6px)', right: 0, width: 240, background: '#FFFFFF',
                borderRadius: 14, boxShadow: '0 10px 30px rgba(0,0,0,0.12)', border: '1px solid rgba(124,58,237,0.12)',
                padding: 6, zIndex: 50,
              }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#94A3B8', padding: '6px 10px 4px', letterSpacing: '0.6px' }}>TARGET AI MODEL</div>
                {targetModels.map(model => (
                  <div
                    key={model} onClick={() => { setSelectedTarget(model); setIsTargetOpen(false); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 8,
                      fontSize: 12.5, fontWeight: 600, color: selectedTarget === model ? '#6D28D9' : '#334155',
                      background: selectedTarget === model ? 'rgba(124,58,237,0.08)' : 'transparent', cursor: 'pointer',
                    }}
                    className="hover:bg-[rgba(124,58,237,0.05)]"
                  >
                    {selectedTarget === model ? <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#A855F7' }} /> : <span style={{ width: 6 }} />}
                    {model}
                  </div>
                ))}
                <div style={{ height: 1, background: '#F1F5F9', margin: '6px 4px' }} />
                <div style={{ fontSize: 10, fontWeight: 700, color: '#94A3B8', padding: '6px 10px 4px', letterSpacing: '0.6px' }}>OPTIMIZER ENGINE</div>
                {optimizerEngines.map(engine => (
                  <div
                    key={engine} onClick={() => { setSelectedEngine(engine); setIsTargetOpen(false); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 8,
                      fontSize: 12.5, fontWeight: 600, color: selectedEngine === engine ? '#6D28D9' : '#334155',
                      background: selectedEngine === engine ? 'rgba(124,58,237,0.08)' : 'transparent', cursor: 'pointer',
                    }}
                    className="hover:bg-[rgba(124,58,237,0.05)]"
                  >
                    {selectedEngine === engine ? <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#A855F7' }} /> : <span style={{ width: 6 }} />}
                    {engine}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 1100, margin: '0 auto', width: '100%' }}>
        {/* Version Header Timeline */}
        {!compareMode && (
          <VersionHeader
            versions={sessionVersions.map((v, idx) => ({
              versionNumber: v.versionNumber,
              overallScore: v.overallScore,
              timestamp: v.timestamp,
              originalIndex: idx
            }))}
            activeIndex={activeVersionIndex}
            bestIndex={bestIndex}
            hoveredIndex={hoveredVersionIndex}
            onOpenHistory={() => setIsHistoryOpen(true)}
            onSelectVersion={handleVersionSelect}
            onHoverVersion={setHoveredVersionIndex}
          />
        )}

        {/* Compare vs Normal */}
        {compareMode ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
              <select
                value={compareIndex} onChange={e => setCompareIndex(Number(e.target.value))}
                style={{ padding: '8px 16px', borderRadius: 10, border: '1px solid rgba(124,58,237,0.25)', background: '#FFFFFF', fontWeight: 600 }}
              >
                {sessionVersions.map((v, i) => (
                  <option key={i} value={i}>v{v.versionNumber} — Score {v.overallScore}</option>
                ))}
              </select>
              <span style={{ fontWeight: 700, color: '#94A3B8', fontSize: 13 }}>vs</span>
              <select
                value={activeVersionIndex} onChange={e => handleVersionSelect(Number(e.target.value))}
                style={{ padding: '8px 16px', borderRadius: 10, border: '1px solid rgba(124,58,237,0.25)', background: '#FFFFFF', fontWeight: 600 }}
              >
                {sessionVersions.map((v, i) => (
                  <option key={i} value={i}>v{v.versionNumber} — Score {v.overallScore}</option>
                ))}
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              {renderOptimizedPanel(sessionVersions[compareIndex], `v${sessionVersions[compareIndex].versionNumber}`)}
              {renderOptimizedPanel(sessionVersions[displayVersionIndex], `v${sessionVersions[displayVersionIndex].versionNumber}`)}
            </div>
          </div>
        ) : (
          <>
            {/* Score Overview Strip */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: '#FFFFFF', borderRadius: 20, padding: '24px 28px',
              border: '1px solid rgba(124,58,237,0.12)', boxShadow: '0 4px 20px rgba(109,40,217,0.06)',
              flexWrap: 'wrap', gap: 20,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
                {/* Score Ring */}
                <div style={{ position: 'relative', width: 100, height: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg width="100" height="100" style={{ transform: 'rotate(-90deg)' }}>
                    <defs>
                      <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor="#7C3AED" />
                        <stop offset="100%" stopColor="#A855F7" />
                      </linearGradient>
                      <filter id="ringGlow" x="-30%" y="-30%" width="160%" height="160%">
                        <feGaussianBlur stdDeviation="3" result="blur" />
                        <feMerge>
                          <feMergeNode in="blur" />
                          <feMergeNode in="SourceGraphic" />
                        </feMerge>
                      </filter>
                    </defs>
                    <circle cx="50" cy="50" r={radius} fill="none" stroke="rgba(124,58,237,0.06)" strokeWidth="7" />
                    <circle
                      cx="50" cy="50" r={radius} fill="none" stroke="url(#ringGrad)" strokeWidth="7"
                      strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={offset}
                      filter="url(#ringGlow)" style={{ transition: 'stroke-dashoffset 1.4s ease-out' }}
                    />
                  </svg>
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ fontSize: 26, fontWeight: 800, color: scoreColor(version.overallScore) }}>{animatedScore}</span>
                  </div>
                </div>

                {/* Score Info */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <span style={{ fontSize: 22, fontWeight: 800, color: '#1E293B' }}>{scoreLabel(version.overallScore)}</span>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 12px', background: 'rgba(16,185,129,0.10)', color: '#10B981', borderRadius: 9999, fontSize: 12, fontWeight: 700, width: 'fit-content' }}>
                    <TrendingUp size={13} />
                    <span>+{version.overallScore - sessionVersions[0].overallScore} pts from v1</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: '#64748B', fontWeight: 600, marginTop: 2 }}>
                    <span>Original <strong style={{ color: '#1E293B' }}>{sessionVersions[0].overallScore}</strong></span>
                    <ArrowRight size={14} style={{ color: '#94A3B8' }} />
                    <span>v{version.versionNumber} <strong style={{ color: scoreColor(version.overallScore) }}>{version.overallScore}</strong></span>
                  </div>
                </div>
              </div>

              {/* Word/Token Stats */}
              <div style={{ display: 'flex', gap: 20 }}>
                <div style={{ padding: '12px 20px', background: 'rgba(124,58,237,0.04)', borderRadius: 14, border: '1px solid rgba(124,58,237,0.10)', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#64748B' }}>Words</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: '#94A3B8' }}>{session.wordsBefore}</span>
                  <ArrowRight size={12} style={{ color: '#94A3B8' }} />
                  <span style={{ fontSize: 15, fontWeight: 800, color: '#6D28D9' }}>{version.wordsAfter}</span>
                </div>
                <div style={{ padding: '12px 20px', background: 'rgba(124,58,237,0.04)', borderRadius: 14, border: '1px solid rgba(124,58,237,0.10)', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#64748B' }}>Tokens</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: '#94A3B8' }}>~{session.tokensBefore}</span>
                  <ArrowRight size={12} style={{ color: '#94A3B8' }} />
                  <span style={{ fontSize: 15, fontWeight: 800, color: '#6D28D9' }}>~{version.tokensAfter}</span>
                </div>
              </div>
            </div>

            {/* Side-by-side prompt comparison */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              {renderOptimizedPanel(version, `Optimized · v${version.versionNumber}`)}

              {/* Original panel */}
              <div style={{
                background: '#FFFFFF', borderRadius: 20, padding: 24,
                boxShadow: '0 4px 20px rgba(109,40,217,0.04)', border: '1px solid rgba(124,58,237,0.10)',
                display: 'flex', flexDirection: 'column',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 18 }}>
                  <div style={{
                    display: 'inline-flex', alignItems: 'center', padding: '6px 14px', borderRadius: 9999,
                    fontSize: 12, fontWeight: 700, background: '#F1F5F9', color: '#64748B',
                  }}>
                    <span>Original</span>
                  </div>
                </div>
                <div style={{ flex: 1, fontSize: 13.5, lineHeight: 1.6, color: '#475569' }}>
                  {session.originalPrompt}
                </div>
              </div>
            </div>

            {/* Score Breakdown Dimensions Grid */}
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 800, color: '#1E293B', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                Score Breakdown
                <span style={{ fontSize: 12, fontWeight: 700, background: 'rgba(124,58,237,0.10)', color: '#7C3AED', padding: '2px 8px', borderRadius: 9999 }}>v{version.versionNumber}</span>
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
                {version.dimensions.map((dim, i) => {
                  const Icon = dim.icon;
                  const score = dim.score;
                  return (
                    <div
                      key={dim.id}
                      style={{
                        background: '#FFFFFF', borderRadius: 16, padding: 18,
                        border: '1px solid rgba(124,58,237,0.10)', boxShadow: '0 2px 10px rgba(109,40,217,0.03)',
                        display: 'flex', flexDirection: 'column', gap: 10, position: 'relative', overflow: 'hidden',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{
                            width: 28, height: 28, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: dim.status === 'good' ? 'rgba(16,185,129,0.12)' : dim.status === 'warning' ? 'rgba(245,158,11,0.12)' : 'rgba(148,163,184,0.12)',
                            color: dim.status === 'good' ? '#10B981' : dim.status === 'warning' ? '#F59E0B' : '#64748B',
                          }}>
                            <Icon size={15} strokeWidth={2.2} />
                          </div>
                          <span style={{ fontSize: 14, fontWeight: 700, color: '#1E293B' }}>{dim.label}</span>
                        </div>
                        <span style={{ fontSize: 16, fontWeight: 800, color: scoreColor(score) }}>{score}</span>
                      </div>

                      <div style={{ height: 6, background: '#F1F5F9', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', width: `${score}%`, background: scoreColor(score),
                          borderRadius: 99, transition: 'width 0.8s ease-out',
                        }} />
                      </div>
                      <p style={{ fontSize: 12.5, color: '#64748B', margin: 0, lineHeight: 1.4 }}>{dim.desc}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>

      <VersionHistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        versions={sessionVersions.map((v) => ({
          versionNumber: v.versionNumber,
          overallScore: v.overallScore,
          timestamp: v.timestamp,
          isStarred: v.isStarred,
          tweakNote: v.tweakNote,
        }))}
        activeIndex={activeVersionIndex}
        onSelect={handleVersionSelect}
        onToggleStar={handleToggleStar}
        onHoverVersion={setHoveredVersionIndex}
      />
    </div>
  );
}
