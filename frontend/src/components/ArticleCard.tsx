import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ExternalLink, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp, Brain, Clock, Tag, Globe, AlertCircle, Copy, Share2, Bookmark } from 'lucide-react';
import { cn } from '../lib/utils';

interface ArticleSource {
  id: string | number;
  title: string;
  source: string;
  url?: string;
  description?: string;
  sentiment_score?: number;
  sentiment_confidence?: number;
  category?: string;
  created_at?: string;
  preview?: string;
}

interface ArticleCardProps {
  source: ArticleSource;
  index?: number;
  variant?: 'inline' | 'expanded' | 'context';
  onAnalyze?: (source: ArticleSource) => void;
  onSave?: (source: ArticleSource) => void;
  isSaved?: boolean;
}

// Helper to format time ago
function timeAgo(date: string | undefined): string {
  if (!date) return '';
  const now = new Date();
  const then = new Date(date);
  const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);
  
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Sentiment badge component
function SentimentBadge({ score, confidence }: { score?: number; confidence?: number }) {
  if (score === undefined) return null;
  
  const sentiment = score > 0.3 ? 'positive' : score < -0.3 ? 'negative' : 'neutral';
  const Icon = sentiment === 'positive' ? TrendingUp : sentiment === 'negative' ? TrendingDown : Minus;
  const color = sentiment === 'positive' ? 'text-green-600 bg-green-50' : sentiment === 'negative' ? 'text-red-600 bg-red-50' : 'text-gray-600 bg-gray-50';
  
  return (
    <div className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', color)}>
      <Icon className="w-3 h-3" />
      <span>{Math.round((score + 1) * 50)}%</span>
      {confidence && confidence > 0 && (
        <span className="opacity-60">({Math.round(confidence * 100)}%)</span>
      )}
    </div>
  );
}

// Inline citation card (compact)
export function InlineCitationCard({ source, index }: ArticleCardProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  
  return (
    <div 
      className="group relative inline-block"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <a 
        href={source.url || '#'} 
        target="_blank" 
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full hover:shadow-md hover:border-blue-300 dark:hover:border-blue-600 transition-all duration-200"
        onClick={(e) => {
          if (!source.url) e.preventDefault();
        }}
      >
        <span className="text-xs font-semibold text-blue-600 dark:text-blue-400">
          [{index !== undefined ? index + 1 : '•'}]
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3.5 h-3.5 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-[9px] text-slate-700 dark:text-slate-300">
            {(source.source || 'S').slice(0,1).toUpperCase()}
          </span>
          <span className="text-xs text-slate-600 dark:text-slate-400 font-medium truncate max-w-[120px]">
            {source.source}
          </span>
        </span>
        <ExternalLink className="w-3 h-3 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
      </a>
      
      {/* Rich tooltip on hover */}
      <AnimatePresence>
        {showTooltip && (
          <motion.div
            initial={{ opacity: 0, y: 5, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 5, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full left-0 mb-2 w-80 p-3 bg-white dark:bg-slate-800 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 z-50"
          >
            <h4 className="font-semibold text-sm text-slate-900 dark:text-slate-100 line-clamp-2 mb-2">
              {source.title}
            </h4>
            
            {(source.description || source.preview) && (
              <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-3 mb-2">
                {source.description || source.preview}
              </p>
            )}
            
            <div className="flex items-center gap-2 flex-wrap">
              {source.sentiment_score !== undefined && (
                <SentimentBadge score={source.sentiment_score} confidence={source.sentiment_confidence} />
              )}
              {source.category && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 dark:bg-slate-700 rounded-full text-xs">
                  <Tag className="w-3 h-3" />
                  {source.category}
                </span>
              )}
              {source.created_at && (
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  <Clock className="w-3 h-3 inline mr-1" />
                  {timeAgo(source.created_at)}
                </span>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Expanded article card (for "Ask in Chat" context)
export function ExpandedArticleCard({ source, onAnalyze, onSave, isSaved }: ArticleCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const handleCopy = () => {
    const text = `${source.title}\n${source.source}\n${source.description || ''}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-3 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow"
    >
      {/* Header */}
      <div className="p-3 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100 line-clamp-2 mb-1">
              {source.title}
            </h3>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400">
                <Globe className="w-3 h-3" />
                {source.source}
              </span>
              {source.sentiment_score !== undefined && (
                <SentimentBadge score={source.sentiment_score} confidence={source.sentiment_confidence} />
              )}
              {source.category && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-white/60 dark:bg-slate-800/60 rounded-full text-xs">
                  <Tag className="w-3 h-3" />
                  {source.category}
                </span>
              )}
              {source.created_at && (
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {timeAgo(source.created_at)}
                </span>
              )}
            </div>
          </div>
          
          {/* Actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={handleCopy}
              className="p-1.5 hover:bg-white/60 dark:hover:bg-slate-800/60 rounded-lg transition-colors"
              title="Copy"
            >
              {copied ? (
                <motion.div
                  initial={{ scale: 0.5 }}
                  animate={{ scale: 1 }}
                  className="text-green-600"
                >
                  ✓
                </motion.div>
              ) : (
                <Copy className="w-4 h-4 text-slate-500" />
              )}
            </button>
            
            {onSave && (
              <button
                onClick={() => onSave(source)}
                className="p-1.5 hover:bg-white/60 dark:hover:bg-slate-800/60 rounded-lg transition-colors"
                title="Save"
              >
                <Bookmark className={cn("w-4 h-4", isSaved ? "text-amber-600 fill-amber-600" : "text-slate-500")} />
              </button>
            )}
            
            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noreferrer"
                className="p-1.5 hover:bg-white/60 dark:hover:bg-slate-800/60 rounded-lg transition-colors"
                title="Open article"
              >
                <ExternalLink className="w-4 h-4 text-slate-500" />
              </a>
            )}
            
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1.5 hover:bg-white/60 dark:hover:bg-slate-800/60 rounded-lg transition-colors"
              title={expanded ? "Collapse" : "Expand"}
            >
              {expanded ? (
                <ChevronUp className="w-4 h-4 text-slate-500" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-500" />
              )}
            </button>
          </div>
        </div>
      </div>
      
      {/* Expandable content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-slate-200 dark:border-slate-700"
          >
            <div className="p-3 bg-white/50 dark:bg-slate-900/50">
              {(source.description || source.preview) && (
                <p className="text-sm text-slate-700 dark:text-slate-300 mb-3">
                  {source.description || source.preview}
                </p>
              )}
              
              {onAnalyze && (
                <button
                  onClick={() => onAnalyze(source)}
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors"
                >
                  <Brain className="w-3.5 h-3.5" />
                  Analyze Article
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// Single hoverable chip that reveals horizontally scrollable article previews
export function SourcesHoverChip({ sources, asOf, mode }: { sources: ArticleSource[]; asOf?: string | null; mode?: string | null }) {
  const [open, setOpen] = useState(false);
  const anchorRef = React.useRef<HTMLButtonElement | null>(null);
  const [panelWidth, setPanelWidth] = useState<number>(600);
  const panelRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    const el = panelRef.current;
    if (!el) return;
    try {
      const rect = el.getBoundingClientRect();
      setPanelWidth(rect.width || 600);
    } catch {}
  }, [open]);

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => { setOpen(true); }}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        ref={anchorRef}
        className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:shadow-sm transition"
        aria-label={`Sources (${sources?.length || 0})`}
      >
        <span className="text-xs font-medium text-slate-700 dark:text-slate-200">Sources</span>
        <span className="text-[11px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
          {sources?.length || 0}
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            ref={panelRef}
            className="fixed z-[1000] p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-xl"
            style={{
              width: 'min(92vw, 800px)',
              top: (() => {
                const rect = anchorRef.current?.getBoundingClientRect();
                const y = rect ? rect.bottom + 12 : 60;
                const h = typeof window !== 'undefined' ? window.innerHeight : 1000;
                return Math.min(y, h - 220);
              })(),
              left: (() => {
                const rect = anchorRef.current?.getBoundingClientRect();
                const vw = typeof window !== 'undefined' ? window.innerWidth : 1200;
                const desiredLeft = rect ? (rect.left + rect.width / 2 - panelWidth / 2) : 24;
                const clamped = Math.min(Math.max(desiredLeft, 8), vw - Math.min(panelWidth, 800) - 8);
                return clamped;
              })(),
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="text-[11px] text-slate-500">
                {mode === 'web' ? 'Web-backed' : 'Corpus only'}
                {asOf ? ` • As of ${new Date(asOf).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}
              </div>
              <div className="text-[11px] text-slate-500">Hover to preview • Scroll to browse</div>
            </div>

            <div className="flex gap-3 overflow-x-auto no-scrollbar py-1 pr-1">
              {sources?.map((source, idx) => (
                <div
                  key={(source.id as any) ?? idx}
                  className="min-w-[260px] max-w-[320px] flex-shrink-0 border border-slate-200 dark:border-slate-700 rounded-lg p-3 bg-white dark:bg-slate-900/40 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <a
                      href={source.url || '#'}
                      target="_blank"
                      rel="noreferrer"
                      className="font-semibold text-sm text-slate-900 dark:text-slate-100 hover:underline line-clamp-2"
                      onClick={(e) => { if (!source.url) e.preventDefault(); }}
                      title={source.title}
                    >
                      {source.title}
                    </a>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                  </div>

                  {(source.description || source.preview) && (
                    <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed max-h-32 overflow-y-auto">
                      {source.description || source.preview}
                    </div>
                  )}

                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    {source.sentiment_score !== undefined && (
                      <SentimentBadge score={source.sentiment_score} confidence={source.sentiment_confidence} />
                    )}
                    {source.category && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 dark:bg-slate-700 rounded-full text-[11px]">
                        <Tag className="w-3 h-3" />
                        {source.category}
                      </span>
                    )}
                    {source.created_at && (
                      <span className="text-[11px] text-slate-500">
                        <Clock className="w-3 h-3 inline mr-1" />
                        {timeAgo(source.created_at)}
                      </span>
                    )}
                    <span className="text-[11px] text-slate-500">
                      <Globe className="w-3 h-3 inline mr-1" />
                      {source.source}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Related articles grid - removed per user request
export function RelatedArticlesGrid({ articles, onSelect }: { articles: ArticleSource[]; onSelect?: (article: ArticleSource) => void }) {
  // Component disabled - Related Coverage removed
  return null;
}

// Mini sentiment indicator
function SentimentIndicator({ score }: { score: number }) {
  const sentiment = score > 0.3 ? 'positive' : score < -0.3 ? 'negative' : 'neutral';
  const Icon = sentiment === 'positive' ? TrendingUp : sentiment === 'negative' ? TrendingDown : Minus;
  const color = sentiment === 'positive' ? 'text-green-600' : sentiment === 'negative' ? 'text-red-600' : 'text-gray-400';
  
  return <Icon className={cn("w-3 h-3", color)} />;
}

// Named exports are already defined above
export default { InlineCitationCard, ExpandedArticleCard, RelatedArticlesGrid, SourcesHoverChip };
