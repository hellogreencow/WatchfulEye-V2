import { createContext, useContext, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ParticleTransitionOverlay } from '../components/landing/ParticleTransitionOverlay';

type Mode = 'dissolve' | 'reveal';
type Variant = 'eye' | 'login';

type RouteTransitionContextType = {
  transitionTo: (path: string) => void;
};

const RouteTransitionContext = createContext<RouteTransitionContextType | undefined>(undefined);

export function RouteTransitionProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const [active, setActive] = useState(false);
  const [mode, setMode] = useState<Mode>('dissolve');
  const [variant, setVariant] = useState<Variant>('eye');
  const timersRef = useRef<number[]>([]);

  const clearTimers = () => {
    timersRef.current.forEach((t) => window.clearTimeout(t));
    timersRef.current = [];
  };

  const transitionTo = (path: string) => {
    clearTimers();
    setActive(true);
    setMode('dissolve');
    setVariant(path === '/login' ? 'login' : 'eye');

    // Let dissolve start, then navigate while particles are in flight.
    timersRef.current.push(
      window.setTimeout(() => {
        navigate(path);
        setMode('reveal');
      }, 260)
    );

    // End reveal
    timersRef.current.push(
      window.setTimeout(() => {
        setActive(false);
        clearTimers();
      }, 1100)
    );
  };

  return (
    <RouteTransitionContext.Provider value={{ transitionTo }}>
      {/* Single overlay across the entire app to prevent multiple canvases (and crashes). */}
      <ParticleTransitionOverlay
        active={active}
        mode={mode}
        variant={variant}
        durationMs={mode === 'dissolve' ? 650 : 750}
      />
      {children}
    </RouteTransitionContext.Provider>
  );
}

export function useRouteTransition() {
  const ctx = useContext(RouteTransitionContext);
  if (!ctx) throw new Error('useRouteTransition must be used within RouteTransitionProvider');
  return ctx;
}


