import type { HistoryItem, HistoryStats, HistoryFilters, PaginatedHistoryResponse } from '../types/history.types';

const delay = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

function hoursAgo(n: number): string {
  const d = new Date(); d.setHours(d.getHours() - n); return d.toISOString();
}
function daysAgo(n: number, extraHours = 0): string {
  const d = new Date(); d.setDate(d.getDate() - n); d.setHours(d.getHours() - extraHours); return d.toISOString();
}

const DUMMY_STATS: HistoryStats = { totalPrompts: 1284, averageScore: 84, thisWeekDelta: 42, favoritesCount: 156 };

function buildDummyItems(): HistoryItem[] {
  return [
    { id: 'hist-001', prompt: 'Write a blog post about AI tools for marketing automation including real-world examples and ROI metrics', optimizedPrompt: 'Write a 1,500-word expert blog post...', category: 'marketing', score: 92, isFavorite: false, targetModel: 'ChatGPT', mode: 'Marketing', createdAt: hoursAgo(2), wordCount: { original: 18, optimized: 84 }, tokenCount: 112 },
    { id: 'hist-002', prompt: 'Generate a script for a 5-minute YouTube video explaining quantum computing for beginners with analogies', optimizedPrompt: 'Create a complete 5-minute YouTube script...', category: 'youtube', score: 78, isFavorite: true, targetModel: 'GPT-4o', mode: 'YouTube Shorts', createdAt: hoursAgo(4), wordCount: { original: 16, optimized: 76 }, tokenCount: 98 },
    { id: 'hist-003', prompt: 'Optimize this React component for better performance using memoization and lazy loading techniques', optimizedPrompt: 'You are a senior React performance engineer...', category: 'coding', score: 95, isFavorite: false, targetModel: 'Claude Sonnet', mode: 'Coding', createdAt: daysAgo(1), wordCount: { original: 14, optimized: 92 }, tokenCount: 118 },
    { id: 'hist-004', prompt: 'Draft a series of 5 cold outreach emails for a SaaS product targeting marketing directors at mid-size companies', optimizedPrompt: 'You are an expert B2B copywriter...', category: 'email', score: 88, isFavorite: true, targetModel: 'ChatGPT', mode: 'Marketing', createdAt: daysAgo(3), wordCount: { original: 18, optimized: 88 }, tokenCount: 105 },
    { id: 'hist-005', prompt: 'Create a cinematic establishing shot prompt for a dystopian cityscape at golden hour for VEO', optimizedPrompt: 'Generate a photorealistic cinematic establishing shot...', category: 'cinematic', score: 97, isFavorite: true, targetModel: 'VEO', mode: 'Cinematic Video', createdAt: daysAgo(3, 4), wordCount: { original: 15, optimized: 96 }, tokenCount: 124 },
    { id: 'hist-006', prompt: 'Write a research summary on the latest developments in large language model alignment and safety', optimizedPrompt: 'Provide a comprehensive research summary...', category: 'research', score: 82, isFavorite: false, targetModel: 'Claude Sonnet', mode: 'Research', createdAt: daysAgo(5), wordCount: { original: 16, optimized: 74 }, tokenCount: 96 },
    { id: 'hist-007', prompt: 'Generate product photography prompt for a luxury watch on marble surface for commercial use', optimizedPrompt: 'Luxury timepiece product photograph...', category: 'image-gen', score: 91, isFavorite: false, targetModel: 'Midjourney', mode: 'Image Gen', createdAt: daysAgo(6), wordCount: { original: 13, optimized: 45 }, tokenCount: 58 },
    { id: 'hist-008', prompt: 'Create SEO-optimized meta description and title tags for a fintech startup homepage and blog', optimizedPrompt: 'Generate high-CTR keyword-rich meta tags...', category: 'seo', score: 73, isFavorite: false, targetModel: 'ChatGPT', mode: 'SEO', createdAt: daysAgo(7), wordCount: { original: 15, optimized: 62 }, tokenCount: 80 },
    { id: 'hist-009', prompt: 'Write a short story about a time traveler who accidentally prevents the invention of the internet', optimizedPrompt: 'Write a 1,200-word literary short story in the style of Kurt Vonnegut...', category: 'storytelling', score: 87, isFavorite: true, targetModel: 'Claude Sonnet', mode: 'Storytelling', createdAt: daysAgo(8), wordCount: { original: 18, optimized: 88 }, tokenCount: 112 },
    { id: 'hist-010', prompt: 'Debug and fix TypeScript type errors in a Next.js API route handler with proper error handling', optimizedPrompt: 'You are a senior TypeScript engineer...', category: 'coding', score: 94, isFavorite: false, targetModel: 'Claude Sonnet', mode: 'Coding', createdAt: daysAgo(9), wordCount: { original: 15, optimized: 78 }, tokenCount: 100 },
    { id: 'hist-011', prompt: 'Create a B-roll shot list for a brand documentary about a sustainable fashion startup in NYC', optimizedPrompt: 'Generate a 10-scene B-roll shot list...', category: 'cinematic', score: 89, isFavorite: false, targetModel: 'VEO', mode: 'Cinematic Video', createdAt: daysAgo(10), wordCount: { original: 16, optimized: 82 }, tokenCount: 105 },
    { id: 'hist-012', prompt: 'Analyze the competitive landscape for AI-powered project management tools in the enterprise market', optimizedPrompt: 'Conduct a structured competitive analysis...', category: 'research', score: 68, isFavorite: false, targetModel: 'Gemini', mode: 'Research', createdAt: daysAgo(12), wordCount: { original: 13, optimized: 58 }, tokenCount: 74 },
    { id: 'hist-013', prompt: 'Write a LinkedIn post announcing a Series A funding round of $12M for our AI startup', optimizedPrompt: 'Craft a high-engagement LinkedIn announcement post...', category: 'marketing', score: 83, isFavorite: true, targetModel: 'ChatGPT', mode: 'Marketing', createdAt: daysAgo(14), wordCount: { original: 14, optimized: 68 }, tokenCount: 88 },
    { id: 'hist-014', prompt: 'Generate a midjourney prompt for a surrealist oil painting of an underwater art deco city', optimizedPrompt: 'Surrealist underwater metropolis, Art Deco architecture...', category: 'image-gen', score: 96, isFavorite: true, targetModel: 'Midjourney', mode: 'Image Gen', createdAt: daysAgo(15), wordCount: { original: 14, optimized: 52 }, tokenCount: 68 },
    { id: 'hist-015', prompt: 'Explain retrieval augmented generation to a non-technical executive audience in simple terms', optimizedPrompt: 'Explain RAG clearly for a non-technical business audience...', category: 'general', score: 75, isFavorite: false, targetModel: 'Claude Sonnet', mode: 'General', createdAt: daysAgo(18), wordCount: { original: 14, optimized: 65 }, tokenCount: 84 },
    { id: 'hist-016', prompt: 'Create a 30-day content calendar for a B2B SaaS company in the HR tech space with post ideas', optimizedPrompt: 'Develop a comprehensive 30-day content calendar...', category: 'marketing', score: 86, isFavorite: false, targetModel: 'ChatGPT', mode: 'Marketing', createdAt: daysAgo(20), wordCount: { original: 17, optimized: 72 }, tokenCount: 92 },
  ];
}

let _items: HistoryItem[] | null = null;
function getItems(): HistoryItem[] {
  if (!_items) _items = buildDummyItems();
  return _items;
}

export async function fetchHistoryStats(): Promise<HistoryStats> {
  await delay(150);
  return { ...DUMMY_STATS };
}

export async function fetchHistory(page: number, pageSize: number, filters: HistoryFilters): Promise<PaginatedHistoryResponse> {
  await delay(200);
  let items = [...getItems()];
  if (filters.category === 'favorites') items = items.filter(i => i.isFavorite);
  else if (filters.category !== 'all') items = items.filter(i => i.category === filters.category);
  if (filters.search.trim()) {
    const q = filters.search.toLowerCase();
    items = items.filter(i => i.prompt.toLowerCase().includes(q) || i.mode.toLowerCase().includes(q) || i.targetModel.toLowerCase().includes(q));
  }
  switch (filters.sortBy) {
    case 'highest-score': items.sort((a, b) => b.score - a.score); break;
    case 'lowest-score':  items.sort((a, b) => a.score - b.score); break;
    case 'oldest':        items.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()); break;
    default:              items.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * pageSize;
  return { items: items.slice(start, start + pageSize), total, page: safePage, pageSize, totalPages };
}

export async function toggleFavorite(id: string, isFavorite: boolean): Promise<void> {
  await delay(80);
  const item = getItems().find(i => i.id === id);
  if (item) item.isFavorite = isFavorite;
}

export async function deleteHistoryItem(id: string): Promise<void> {
  await delay(100);
  _items = getItems().filter(i => i.id !== id);
}
