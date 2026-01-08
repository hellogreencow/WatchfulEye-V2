import { useNavigate } from 'react-router-dom';
import { Navigation } from './Navigation';
import { ParticleEyeHero } from './ParticleEyeHero';
import { ManifestoSection } from './ManifestoSection';
import { TelegramUpdates } from './TelegramUpdates';
import { FinalCTA } from './FinalCTA';
import { CustomCursor } from './CustomCursor';
import { SmoothScroll } from './SmoothScroll';
import { ThemeProvider } from '../../lib/theme-context';
import { Eye3D } from './EyeIcon';
import { useRouteTransition } from '../../lib/routeTransition';

function Footer() {
  const navigate = useNavigate();

  return (
    <footer className="relative py-12 md:py-20 bg-background border-t border-primary/20">
      <div className="max-w-7xl mx-auto px-4 md:px-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 md:gap-12 mb-8 md:mb-12">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-4 cursor-pointer" onClick={() => navigate('/')}>
              <Eye3D className="w-5 h-5 md:w-6 md:h-6 text-primary" />
              <span className="text-lg md:text-xl font-light tracking-tight text-foreground">
                WatchfulEye
              </span>
            </div>
            <p className="text-xs md:text-sm text-muted-foreground max-w-sm leading-relaxed">
              AI-powered geopolitical intelligence platform delivering real-time market-moving insights to institutional investors worldwide.
            </p>
          </div>

          <div>
            <h4 className="text-xs text-primary/80 mb-3 md:mb-4 uppercase tracking-widest font-mono">Platform</h4>
            <ul className="space-y-1.5 md:space-y-2 text-xs md:text-sm text-muted-foreground">
              <li onClick={() => navigate('/news')} className="hover:text-primary transition-colors cursor-pointer">Live Briefing</li>
              <li className="hover:text-primary transition-colors cursor-pointer">Intelligence Engine</li>
              <li className="hover:text-primary transition-colors cursor-pointer">API Access</li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs text-primary/80 mb-3 md:mb-4 uppercase tracking-widest font-mono">Company</h4>
            <ul className="space-y-1.5 md:space-y-2 text-xs md:text-sm text-muted-foreground">
              <li className="hover:text-primary transition-colors cursor-pointer">About</li>
              <li className="hover:text-primary transition-colors cursor-pointer">Security</li>
              <li className="hover:text-primary transition-colors cursor-pointer">Contact</li>
            </ul>
          </div>
        </div>

        <div className="pt-6 md:pt-8 border-t border-primary/10 flex flex-col md:flex-row items-center justify-between gap-3 md:gap-4 text-[10px] md:text-xs text-muted-foreground">
          <div>© 2025 WatchfulEye Intelligence Platform</div>
          <div className="flex items-center gap-4 md:gap-6">
            <span className="hover:text-primary transition-colors cursor-pointer">Privacy</span>
            <span className="hover:text-primary transition-colors cursor-pointer">Terms</span>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse shadow-neon" />
              <span className="text-primary/80 font-mono">SYSTEMS NOMINAL</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

export function LandingPage() {
  const navigate = useNavigate();
  const { transitionTo } = useRouteTransition();

  const handleNavigate = (view: 'home' | 'news' | 'login' | 'features') => {
    if (view === 'home') {
      navigate('/');
    } else if (view === 'news') {
      navigate('/news');
    } else if (view === 'login') {
      // Full-page particle dissolve → route transition → reveal
      transitionTo('/login');
    } else if (view === 'features') {
      navigate('/features');
    }
  };

  return (
    <ThemeProvider>
      <SmoothScroll>
        <div className="relative min-h-screen bg-background text-foreground overflow-x-hidden selection:bg-primary/30 selection:text-primary">
          {/* Custom Cursor */}
          <CustomCursor />

          {/* Navigation */}
          <Navigation onNavigate={handleNavigate} />

          {/* Landing Page Content */}
          <main className="relative z-10">
            <ParticleEyeHero onNavigate={handleNavigate} />
            <ManifestoSection />
            <TelegramUpdates />
            <FinalCTA onNavigate={handleNavigate} />
            <Footer />
          </main>
        </div>
      </SmoothScroll>
    </ThemeProvider>
  );
}

