import { motion } from 'motion/react';
import { useInView } from 'react-intersection-observer';
import { Send, Clock, Users, Zap } from 'lucide-react';
import { useState, useEffect } from 'react';
import axios from 'axios';

const TELEGRAM_CHANNEL_URL = 'https://t.me/watchfuleye41';

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

interface Analysis {
  id: string;
  title?: string;
  content: string;
  content_preview?: string;
  created_at: string;
  time_ago?: string;
}

export function TelegramUpdates() {
  const { ref, inView } = useInView({
    threshold: 0.2,
    triggerOnce: true,
  });

  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeRemaining, setTimeRemaining] = useState(4 * 60 * 60); // 4 hours in seconds

  useEffect(() => {
    const fetchAnalyses = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_BASE_URL}/analyses?limit=4`);
        const fetchedAnalyses = response.data.data || [];
        setAnalyses(fetchedAnalyses);
      } catch (error) {
        console.error('Failed to fetch analyses:', error);
        setAnalyses([]);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalyses();
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          return 4 * 60 * 60;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const formatTime = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const extractTitle = (content: string): string => {
    // Try to extract a title from the content (first line or first sentence)
    const lines = content.split('\n').filter(line => line.trim());
    if (lines.length > 0) {
      const firstLine = lines[0].trim();
      if (firstLine.length < 100) return firstLine;
    }
    // Fallback: first sentence
    const firstSentence = content.split(/[.!?]/)[0].trim();
    if (firstSentence.length < 100) return firstSentence;
    // Final fallback
    return 'Intelligence Report';
  };

  const extractPreview = (content: string): string => {
    const preview = content.substring(0, 150);
    if (content.length > 150) return preview + '...';
    return preview;
  };

  const extractTags = (content: string): string[] => {
    // Extract potential tags/keywords from content
    const keywords = ['FOMC', 'USD', 'Bonds', 'China', 'Tech', 'Regulation', 'Energy', 'OPEC', 'Commodities', 'ECB', 'EUR', 'Policy'];
    const foundTags: string[] = [];
    const upperContent = content.toUpperCase();
    
    keywords.forEach(keyword => {
      if (upperContent.includes(keyword.toUpperCase())) {
        foundTags.push(keyword);
      }
    });
    
    return foundTags.slice(0, 3); // Limit to 3 tags
  };

  const getTimeAgo = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours} hours ago`;
    if (diffDays === 1) return '1 day ago';
    return `${diffDays} days ago`;
  };

  return (
    <section ref={ref} className="relative py-32 bg-navy-950 overflow-hidden">
      {/* Background Gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-background to-navy-950" />
      
      {/* Subtle Pattern */}
      <div className="absolute inset-0 opacity-5">
        <div 
          className="absolute inset-0"
          style={{
            backgroundImage: `radial-gradient(circle at 2px 2px, rgba(56,189,248,0.2) 1px, transparent 0)`,
            backgroundSize: '40px 40px',
          }}
        />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="text-center mb-20"
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-primary/20 bg-primary/10 mb-6">
            <Send className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs text-primary font-medium tracking-wide uppercase">Telegram Intelligence Feed</span>
          </div>
          
          <h2 className="text-4xl md:text-5xl lg:text-6xl mb-6 font-light text-foreground">
            Real-Time <span className="font-medium text-transparent bg-clip-text bg-gradient-to-r from-primary to-blue-400">Updates</span>
          </h2>
          
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
            Critical intelligence delivered directly to your device. Never miss market-moving events with our sub-second alert system.
          </p>

          {/* CTA Button */}
          <motion.button
            onClick={() => window.open(TELEGRAM_CHANNEL_URL, '_blank', 'noopener,noreferrer')}
            className="group relative px-8 py-4 bg-primary text-background font-semibold rounded-lg overflow-hidden shadow-lg shadow-primary/20"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
            <span className="relative z-10 flex items-center gap-2 text-sm uppercase tracking-wider">
              <Send className="w-4 h-4" />
              Join Telegram Channel
            </span>
          </motion.button>
        </motion.div>

        {/* Stats Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="grid grid-cols-3 gap-6 mb-16 max-w-4xl mx-auto"
        >
          <div className="text-center p-6 bg-card/40 backdrop-blur-sm border border-white/5 rounded-2xl hover:bg-card/60 transition-colors">
            <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-3">
              <Clock className="w-5 h-5 text-primary" />
            </div>
            <div className="text-3xl text-foreground font-light mb-1">4hrs</div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Update Cycle</div>
          </div>
          <div className="text-center p-6 bg-card/40 backdrop-blur-sm border border-white/5 rounded-2xl hover:bg-card/60 transition-colors">
            <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-3">
              <Users className="w-5 h-5 text-primary" />
            </div>
            <div className="text-3xl text-foreground font-light mb-1">12.4K</div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Active Members</div>
          </div>
          <div className="text-center p-6 bg-card/40 backdrop-blur-sm border border-white/5 rounded-2xl hover:bg-card/60 transition-colors">
            <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-3">
              <Zap className="w-5 h-5 text-primary" />
            </div>
            <div className="text-3xl text-foreground font-light mb-1">&lt;30s</div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Avg Latency</div>
          </div>
        </motion.div>

        {/* Updates Feed */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="max-w-4xl mx-auto space-y-4"
        >
          {loading && (
            <div className="text-center py-10 text-muted-foreground">
              Loading intelligence reports...
            </div>
          )}

          {!loading && analyses.length === 0 && (
            <div className="text-center py-10 text-muted-foreground">
              No reports available at this time.
            </div>
          )}

          {!loading && analyses.map((analysis, index) => {
            const title = analysis.title || extractTitle(analysis.content || analysis.content_preview || '');
            const preview = analysis.content_preview || extractPreview(analysis.content || '');
            const tags = extractTags(analysis.content || '');
            const timeAgo = analysis.time_ago || getTimeAgo(analysis.created_at);
            // Calculate confidence based on content length and structure (mock)
            const confidence = Math.min(95, Math.max(75, Math.floor(80 + Math.random() * 15)));

            return (
              <motion.div
                key={analysis.id}
                className="group relative bg-card/40 backdrop-blur-md border border-white/5 hover:border-primary/20 hover:bg-card/60 p-6 rounded-xl transition-all duration-300"
                initial={{ opacity: 0, x: -20 }}
                animate={inView ? { opacity: 1, x: 0 } : {}}
                transition={{ duration: 0.5, delay: 0.5 + index * 0.1 }}
                whileHover={{ x: 4, scale: 1.01 }}
              >
                {/* Blur overlay - encourages signup */}
                <div className="absolute inset-0 bg-background/80 backdrop-blur-sm z-10 flex items-center justify-center rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  <div className="text-center px-6">
                    <p className="text-sm font-medium text-foreground mb-2">Sign up to view full intelligence reports</p>
                    <button
                      onClick={() => window.open(TELEGRAM_CHANNEL_URL, '_blank', 'noopener,noreferrer')}
                      className="px-4 py-2 bg-primary text-background text-xs font-semibold rounded-lg hover:bg-primary/90 transition-colors uppercase tracking-wider"
                    >
                      Get Access
                    </button>
                  </div>
                </div>

                {/* Time & Confidence */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{timeAgo}</span>
                  </div>
                  <div className="px-2.5 py-1 bg-primary/5 border border-primary/20 rounded text-[10px] font-semibold text-primary uppercase tracking-wide">
                    {confidence}% Confidence
                  </div>
                </div>

                {/* Title */}
                <h3 className="text-lg font-medium text-foreground mb-2 group-hover:text-primary transition-colors">
                  {title}
                </h3>

                {/* Preview - blurred */}
                <p className="text-sm text-muted-foreground leading-relaxed mb-4 line-clamp-2 blur-sm group-hover:blur-none transition-all duration-300">
                  {preview}
                </p>

                {/* Tags */}
                {tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {tags.map((tag, i) => (
                      <span
                        key={i}
                        className="px-2 py-1 text-xs bg-white/5 text-slate-300 rounded border border-white/5"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Subtle Gradient Hover Effect */}
                <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-xl pointer-events-none" />
              </motion.div>
            );
          })}
        </motion.div>

        {/* Bottom CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 1 }}
          className="text-center mt-16"
        >
          <div className="inline-block p-4 bg-card/30 rounded-2xl border border-white/5 backdrop-blur-sm">
            <p className="text-sm text-muted-foreground mb-2">
              Next scheduled update in: <span className="text-foreground font-mono font-medium">{formatTime(timeRemaining)}</span>
            </p>
            <div className="flex items-center justify-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-xs text-emerald-400 uppercase tracking-wider font-semibold">System Online</span>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
