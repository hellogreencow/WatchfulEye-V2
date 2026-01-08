import { motion } from 'motion/react';
import { ArrowUpRight, Clock, Globe, Zap, Shield, TrendingUp } from 'lucide-react';
import { useMemo, useState, useEffect } from 'react';
import axios from 'axios';
import { Navigation } from './Navigation';
import { ThemeProvider } from '../../lib/theme-context';
import { useNavigate } from 'react-router-dom';

// Resolve API base URL (same logic as Dashboard)
function resolveApiBaseUrl(): string {
  const fallback = '/api';
  const raw = (process.env.REACT_APP_API_URL || '').trim();
  if (!raw) return fallback;

  const isBrowser = typeof window !== 'undefined';
  const pageHost = isBrowser ? window.location.hostname : '';
  const isLocalPage = pageHost === 'localhost' || pageHost === '127.0.0.1';

  let candidate = raw;

  try {
    if (/^https?:\/\//i.test(candidate)) {
      const u = new URL(candidate);
      const isLocalTarget = u.hostname === 'localhost' || u.hostname === '127.0.0.1';
      if (isLocalTarget && !isLocalPage) return fallback;

      if (!u.pathname || u.pathname === '/') {
        u.pathname = '/api';
      }
      candidate = u.toString();
    }
  } catch {
    // If parsing fails, fall back to the raw string
  }

  candidate = candidate.replace(/\/$/, '');
  if (!candidate.startsWith('http') && !candidate.startsWith('/')) {
    candidate = `/${candidate}`;
  }
  return candidate;
}

const API_BASE_URL = resolveApiBaseUrl();

interface Article {
  id: string;
  title: string;
  source: string;
  created_at: string;
  sentiment_score: number;
  sentiment_confidence: number;
  category: string;
  description: string;
  url?: string;
}

type CategoryItem = { name: string; display_name?: string; count?: number };

export function NewsPage() {
  const navigate = useNavigate();
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>(''); // '' => All
  const [promptArticle, setPromptArticle] = useState<Article | null>(null);

  const hasAuthToken = useMemo(() => !!localStorage.getItem('auth_token'), []);
  const pendingKey = useMemo(() => 'we_pending_ai_article_v1', []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_BASE_URL}/categories`);
        const cats = (res.data?.categories || []) as CategoryItem[];
        if (!cancelled) setCategories(cats);
      } catch {
        if (!cancelled) setCategories([]);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const fetchArticles = async () => {
      try {
        setLoading(true);
        const params = new URLSearchParams();
        params.append('limit', '12');
        params.append('include_analysis', 'false');
        if (selectedCategory) params.append('category', selectedCategory);
        
        const response = await axios.get(`${API_BASE_URL}/articles?${params}`);
        const fetchedArticles = response.data.data || [];
        setArticles(fetchedArticles);
      } catch (error) {
        console.error('Failed to fetch articles:', error);
        setArticles([]);
      } finally {
        setLoading(false);
      }
    };

    fetchArticles();
  }, [selectedCategory]);

  const getTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const getSentimentLabel = (score: number | undefined | null): string => {
    if (score === null || score === undefined) return 'Neutral';
    if (score > 0.1) return 'Positive';
    if (score < -0.1) return 'Negative';
    return 'Neutral';
  };

  const getImpactLevel = (sentimentScore: number, confidence: number): 'Critical' | 'High' | 'Medium' => {
    const absScore = Math.abs(sentimentScore);
    if (absScore > 0.5 && confidence > 0.8) return 'Critical';
    if (absScore > 0.3 && confidence > 0.7) return 'High';
    return 'Medium';
  };

  const beginAiAnalysis = (article: Article) => {
    try {
      localStorage.setItem(pendingKey, JSON.stringify(article));
    } catch {
      // ignore
    }
    navigate(hasAuthToken ? '/dashboard' : '/login');
  };

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background text-foreground pt-24 pb-20 px-6">
        <Navigation />
        <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-8">
          <div>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="inline-flex items-center gap-2 px-3 py-1 border border-primary/30 bg-primary/5 mb-6"
            >
              <div className="w-2 h-2 bg-primary animate-pulse" />
              <span className="text-xs font-mono text-primary uppercase tracking-wider">Live Intelligence Feed</span>
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-5xl md:text-7xl font-light tracking-tight mb-4"
            >
              Global <span className="text-primary">Briefing</span>
            </motion.h1>
          </div>

          {/* Filters */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="flex flex-wrap gap-2"
          >
            {[{ name: '', display_name: 'All' } as CategoryItem, ...categories].map((cat) => (
              <button
                key={cat.name || '__all__'}
                onClick={() => setSelectedCategory(cat.name || '')}
                className={`px-4 py-2 text-xs uppercase tracking-wider border transition-all ${
                  selectedCategory === (cat.name || '')
                    ? 'border-primary bg-primary/10 text-primary' 
                    : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
                }`}
              >
                {cat.display_name || cat.name || 'All'}
              </button>
            ))}
          </motion.div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-primary text-lg">Loading intelligence feed...</div>
          </div>
        )}

        {/* News Grid */}
        {!loading && articles.length === 0 && (
          <div className="text-center py-20 text-muted-foreground">
            No articles found{selectedCategory ? ` for ${selectedCategory}` : ''}.
          </div>
        )}

        {!loading && articles.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {articles.map((item, index) => {
              const impact = getImpactLevel(item.sentiment_score || 0, item.sentiment_confidence || 0);
              const sentiment = getSentimentLabel(item.sentiment_score);
              
              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 * index }}
                  className="group relative bg-card/40 border border-border hover:border-primary/50 transition-colors overflow-hidden cursor-pointer"
                  role="button"
                  tabIndex={0}
                  onClick={() => setPromptArticle(item)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') setPromptArticle(item);
                  }}
                >
                  {/* Content */}
                  <div className="p-6 relative">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        <span>{getTimeAgo(item.created_at)}</span>
                      </div>
                      <div className={`flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 border ${
                        impact === 'Critical' ? 'border-red-500/30 text-red-400 bg-red-500/5' :
                        impact === 'High' ? 'border-orange-500/30 text-orange-400 bg-orange-500/5' :
                        'border-primary/30 text-primary bg-primary/5'
                      }`}>
                        {impact === 'Critical' && <Zap className="w-3 h-3" />}
                        {impact === 'High' && <TrendingUp className="w-3 h-3" />}
                        {impact === 'Medium' && <Globe className="w-3 h-3" />}
                        {impact} Impact
                      </div>
                    </div>

                    {/* Category Tag */}
                    <div className="mb-3">
                      <span className="px-2 py-1 bg-background/80 backdrop-blur-md border border-border text-[10px] uppercase tracking-widest text-foreground">
                        {item.category || 'News'}
                      </span>
                    </div>

                    <h3 className="text-xl font-light leading-snug mb-3 group-hover:text-[#4A9FD8] transition-colors">
                      {item.title}
                    </h3>
                    
                    <p className="text-sm text-muted-foreground leading-relaxed mb-6 border-b border-border pb-6">
                      {item.description || 'No description available.'}
                    </p>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Shield className="w-3 h-3 text-primary" />
                        <span className="text-xs text-muted-foreground">AI Analysis: {sentiment}</span>
                      </div>
                      {item.url && (
                        <a 
                          href={item.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-primary hover:text-primary/80"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <ArrowUpRight className="w-4 h-4 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Hover Effect Line */}
                  <div className="absolute bottom-0 left-0 w-full h-0.5 bg-primary scale-x-0 group-hover:scale-x-100 transition-transform duration-500 origin-left" />
                </motion.div>
              );
            })}
          </div>
        )}
        </div>

        {/* Click Prompt */}
        {promptArticle && (
          <div className="fixed inset-0 z-[70] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-background border border-border rounded-lg overflow-hidden">
              <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                    {promptArticle.source || 'Source'} • {getTimeAgo(promptArticle.created_at)}
                  </div>
                  <div className="mt-1 text-lg font-semibold text-foreground">
                    {promptArticle.title}
                  </div>
                </div>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => setPromptArticle(null)}
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>
              <div className="px-5 py-4">
                <div className="text-sm text-muted-foreground">
                  Choose how you want to proceed:
                </div>
                <div className="mt-4 flex flex-col sm:flex-row gap-3">
                  <button
                    type="button"
                    onClick={() => beginAiAnalysis(promptArticle)}
                    className="flex-1 px-4 py-2 border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 transition-colors font-mono text-xs tracking-widest uppercase"
                  >
                    {hasAuthToken ? 'AI Deep Analysis' : 'Login for AI Deep Analysis'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (promptArticle.url) window.open(promptArticle.url, '_blank', 'noopener,noreferrer');
                      setPromptArticle(null);
                    }}
                    className="flex-1 px-4 py-2 border border-border bg-card/40 hover:bg-card/60 transition-colors font-mono text-xs tracking-widest uppercase text-foreground disabled:opacity-50"
                    disabled={!promptArticle.url}
                    title={promptArticle.url ? 'Open source' : 'No source URL available'}
                  >
                    Read Source
                  </button>
                </div>
                {!promptArticle.url && (
                  <div className="mt-3 text-xs text-muted-foreground">
                    No source URL on this item; use AI analysis to dig in, or browse more in Briefings.
                  </div>
                )}
              </div>
              <div className="px-5 py-3 border-t border-border flex justify-between">
                <button
                  type="button"
                  className="text-xs font-mono text-muted-foreground hover:text-foreground uppercase tracking-widest"
                  onClick={() => setPromptArticle(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="text-xs font-mono text-primary hover:underline uppercase tracking-widest"
                  onClick={() => {
                    setPromptArticle(null);
                    navigate('/news');
                  }}
                >
                  View all briefings
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ThemeProvider>
  );
}
