export type SortBy = 'most-recent' | 'highest-score' | 'lowest-score' | 'oldest';

export interface HistoryItem {
  id: string;
  prompt: string;
  optimizedPrompt: string;
  category: string;
  score: number;
  isFavorite: boolean;
  targetModel: string;
  mode: string;
  createdAt: string;
  wordCount: { original: number; optimized: number };
  tokenCount: number;
}

export interface HistoryStats {
  totalPrompts: number;
  averageScore: number;
  thisWeekDelta: number;
  favoritesCount: number;
}

export interface HistoryFilters {
  search: string;
  category: string;
  sortBy: SortBy;
}

export interface PaginatedHistoryResponse {
  items: HistoryItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
