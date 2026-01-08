import { useMemo, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { LogIn, UserPlus, X, Sun, Moon, LayoutDashboard, LogOut } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Eye3D } from './EyeIcon';
import { useTheme } from '../../lib/theme-context';
import axios from 'axios';

// Resolve API base URL (same logic as Dashboard/NewsPage)
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

type BriefingArticle = {
  id: string;
  title: string;
  source: string;
  created_at: string;
  url?: string;
  category?: string;
  sentiment_score?: number;
  sentiment_confidence?: number;
};

interface NavigationProps {
  onNavigate?: (view: 'home' | 'news' | 'login' | 'features') => void;
}

export function Navigation({ onNavigate }: NavigationProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const hasAuthToken = !!localStorage.getItem('auth_token');
  const isFigmaMode = process.env.REACT_APP_FIGMA_MODE === 'true';
  const [briefingsOpen, setBriefingsOpen] = useState(false);
  const [briefingsLoading, setBriefingsLoading] = useState(false);
  const [briefings, setBriefings] = useState<BriefingArticle[]>([]);

  const briefingsCacheKey = useMemo(() => 'we_landing_briefings_v1', []);

  const getTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffMins < 60) return `${diffMins}m`;
    if (diffHours < 24) return `${diffHours}h`;
    return `${diffDays}d`;
  };

  const loadBriefings = async () => {
    if (briefingsLoading) return;

    // Use cached results if available (avoid slowing landing nav)
    try {
      const raw = sessionStorage.getItem(briefingsCacheKey);
      if (raw) {
        const parsed = JSON.parse(raw) as { ts: number; items: BriefingArticle[] };
        if (parsed?.ts && Array.isArray(parsed.items)) {
          const ageMs = Date.now() - parsed.ts;
          if (ageMs < 2 * 60 * 1000) {
            setBriefings(parsed.items.slice(0, 5));
            return;
          }
        }
      }
    } catch {
      // ignore cache parse failures
    }

    setBriefingsLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('limit', '8'); // fetch a few extra, display 5
      params.append('timeframe', '24h');
      params.append('include_analysis', 'false');
      const res = await axios.get(`${API_BASE_URL}/articles?${params.toString()}`);
      const items = (res.data?.data || []) as BriefingArticle[];
      const curated = items.slice(0, 5);
      setBriefings(curated);
      try {
        sessionStorage.setItem(briefingsCacheKey, JSON.stringify({ ts: Date.now(), items: curated }));
      } catch {
        // ignore
      }
    } catch {
      setBriefings([]);
    } finally {
      setBriefingsLoading(false);
    }
  };

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleNavigate = (view: 'home' | 'news' | 'login' | 'features' | 'dashboard' | 'logout') => {
    if (onNavigate && view !== 'dashboard' && view !== 'logout') {
      onNavigate(view);
    } else {
      switch (view) {
        case 'home':
          navigate('/');
          break;
        case 'news':
          navigate('/news');
          break;
        case 'login':
          navigate('/login');
          break;
        case 'features':
          navigate('/features');
          break;
        case 'dashboard':
          navigate('/dashboard');
          break;
        case 'logout':
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user_data');
          window.location.href = '/';
          break;
      }
    }
    setMobileMenuOpen(false);
    setBriefingsOpen(false);
  };

  // Don't show nav on login page or dashboard (dashboard has its own nav)
  const hideNav = location.pathname === '/login' || location.pathname === '/dashboard' || location.pathname.startsWith('/chimera');

  if (hideNav) {
    return null;
  }

  return (
    <>
      <motion.nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 w-full ${
          scrolled ? 'bg-background/95 backdrop-blur-2xl border-b border-border' : ''
        }`}
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
      >
        <div className="w-full px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between w-full">
            {/* Logo */}
            <motion.div 
              className="flex items-center gap-2 cursor-pointer"
              whileHover={{ scale: 1.02 }}
              onClick={() => {
                if (window.innerWidth < 768) {
                  setMobileMenuOpen(!mobileMenuOpen);
                } else {
                  handleNavigate('home');
                }
              }}
            >
              <Eye3D className="w-7 h-7 text-primary" />
              <span className="text-xl font-light tracking-tight text-foreground">
                WatchfulEye
              </span>
            </motion.div>

            {/* Nav Links - Desktop */}
            <div className="hidden md:flex items-center gap-6 ml-8">
              <div
                className="relative"
                onMouseEnter={() => {
                  setBriefingsOpen(true);
                  void loadBriefings();
                }}
                onMouseLeave={() => setBriefingsOpen(false)}
              >
                <button
                  onClick={() => handleNavigate('news')}
                  onFocus={() => {
                    setBriefingsOpen(true);
                    void loadBriefings();
                  }}
                  className="text-sm text-muted-foreground hover:text-primary transition-colors"
                  aria-haspopup="menu"
                  aria-expanded={briefingsOpen}
                >
                  Briefings
                </button>

                <AnimatePresence>
                  {briefingsOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 8, filter: 'blur(6px)' }}
                      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                      exit={{ opacity: 0, y: 6, filter: 'blur(6px)' }}
                      transition={{ duration: 0.15 }}
                      className="absolute left-0 top-full mt-3 w-[420px] bg-background/95 backdrop-blur-2xl border border-border rounded-lg shadow-xl overflow-hidden"
                      role="menu"
                    >
                      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                        <div className="text-[10px] font-mono font-bold tracking-widest uppercase text-muted-foreground">
                          Latest Briefings (24h)
                        </div>
                        <button
                          type="button"
                          className="text-[10px] font-mono font-bold tracking-widest uppercase text-primary hover:underline"
                          onClick={() => handleNavigate('news')}
                        >
                          View all
                        </button>
                      </div>

                      <div className="px-2 py-2">
                        {briefingsLoading ? (
                          <div className="px-3 py-3 text-xs text-muted-foreground font-mono">Loading…</div>
                        ) : briefings.length === 0 ? (
                          <div className="px-3 py-3 text-xs text-muted-foreground font-mono">
                            No briefings available.
                          </div>
                        ) : (
                          <div className="flex flex-col">
                            {briefings.map((a) => (
                              <a
                                key={a.id}
                                href={a.url || '/news'}
                                target={a.url ? '_blank' : undefined}
                                rel={a.url ? 'noreferrer' : undefined}
                                className="group px-3 py-2 rounded-md hover:bg-card/60 transition-colors"
                              >
                                <div className="flex items-center justify-between gap-3">
                                  <div className="text-sm text-foreground group-hover:text-primary transition-colors line-clamp-1">
                                    {a.title}
                                  </div>
                                  {a.created_at && (
                                    <div className="text-[10px] font-mono text-muted-foreground whitespace-nowrap">
                                      {getTimeAgo(a.created_at)}
                                    </div>
                                  )}
                                </div>
                                <div className="mt-0.5 text-[10px] font-mono text-muted-foreground flex items-center gap-2">
                                  <span className="uppercase tracking-widest">{a.source || 'SOURCE'}</span>
                                  {a.category ? <span className="opacity-70">• {a.category}</span> : null}
                                  {a.url ? <span className="opacity-70">• opens</span> : <span className="opacity-70">• details</span>}
                                </div>
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
              <button onClick={() => handleNavigate('features')} className="text-sm text-muted-foreground hover:text-primary transition-colors">Intelligence</button>
              {hasAuthToken && (
                <button onClick={() => handleNavigate('dashboard')} className="text-sm text-muted-foreground hover:text-primary transition-colors flex items-center gap-1">
                  <LayoutDashboard className="w-4 h-4" />
                  Dashboard
                </button>
              )}
            </div>

            <div className="flex-1" />

            {/* Auth Buttons - Desktop */}
            <div className="hidden md:flex items-center gap-3">
              <ThemeToggle />
              {hasAuthToken ? (
                <motion.button
                  className="px-6 py-2 text-sm bg-card border border-border hover:border-primary/40 hover:bg-card/80 transition-all flex items-center gap-2"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => handleNavigate('logout')}
                >
                  <LogOut className="w-4 h-4" />
                  <span>LOGOUT</span>
                </motion.button>
              ) : (
                <motion.button
                  className="px-6 py-2 text-sm bg-primary/10 text-primary border border-primary/20 hover:border-primary/40 hover:bg-primary/20 transition-all flex items-center gap-2"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => handleNavigate('login')}
                >
                  <UserPlus className="w-4 h-4" />
                  <span>ACCESS</span>
                </motion.button>
              )}
            </div>

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-muted-foreground hover:text-primary transition-colors"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <span className="text-xl">☰</span>}
            </button>
          </div>
        </div>
      </motion.nav>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            className="fixed inset-0 z-[60] bg-background/98 backdrop-blur-xl md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className="flex flex-col h-full">
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-border">
                <div className="flex items-center gap-2">
                  <Eye3D className="w-7 h-7 text-primary" />
                  <span className="text-xl font-light tracking-tight text-foreground">
                    WatchfulEye
                  </span>
                </div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-2 text-muted-foreground hover:text-primary transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              {/* Menu Items */}
              <div className="flex-1 flex flex-col justify-center px-6 space-y-8">
                <motion.button
                  onClick={() => handleNavigate('home')}
                  className="text-3xl text-foreground hover:text-primary transition-colors text-left font-light"
                  initial={{ x: -50, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.1 }}
                >
                  Home
                </motion.button>
                <motion.button
                  onClick={() => handleNavigate('news')}
                  className="text-3xl text-foreground hover:text-primary transition-colors text-left font-light"
                  initial={{ x: -50, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.2 }}
                >
                  Briefings
                </motion.button>
                <motion.button
                  onClick={() => handleNavigate('features')}
                  className="text-3xl text-foreground hover:text-primary transition-colors text-left font-light"
                  initial={{ x: -50, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.3 }}
                >
                  Intelligence
                </motion.button>
                {hasAuthToken && (
                  <motion.button
                    onClick={() => handleNavigate('dashboard')}
                    className="text-3xl text-foreground hover:text-primary transition-colors text-left font-light flex items-center gap-3"
                    initial={{ x: -50, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    transition={{ delay: 0.4 }}
                  >
                    <LayoutDashboard className="w-6 h-6" />
                    Dashboard
                  </motion.button>
                )}
              </div>

              {/* Auth Buttons */}
              <div className="px-6 pb-8 space-y-3">
                <div className="mb-4">
                  <ThemeToggle />
                </div>
                {hasAuthToken ? (
                  <motion.button
                    onClick={() => handleNavigate('logout')}
                    className="w-full px-6 py-3 text-sm bg-card border border-border hover:border-primary/40 hover:bg-card/80 transition-all flex items-center justify-center gap-2"
                    initial={{ y: 50, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.5 }}
                  >
                    <LogOut className="w-4 h-4" />
                    <span>LOGOUT</span>
                  </motion.button>
                ) : (
                  <motion.button
                    onClick={() => handleNavigate('login')}
                    className="w-full px-6 py-3 text-sm bg-primary/10 text-primary border border-primary/20 hover:border-primary/40 hover:bg-primary/20 transition-all flex items-center justify-center gap-2"
                    initial={{ y: 50, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.5 }}
                  >
                    <UserPlus className="w-4 h-4" />
                    <span>ACCESS</span>
                  </motion.button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  
  return (
    <motion.button
      onClick={toggleTheme}
      className="px-4 py-2 text-sm bg-card border border-border hover:border-primary/40 hover:bg-card/80 transition-all flex items-center gap-2"
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      aria-label="Toggle theme"
    >
      {theme === 'dark' ? (
        <>
          <Sun className="w-4 h-4 text-primary" />
          <span className="text-foreground">Light</span>
        </>
      ) : (
        <>
          <Moon className="w-4 h-4 text-primary" />
          <span className="text-foreground">Dark</span>
        </>
      )}
    </motion.button>
  );
}
