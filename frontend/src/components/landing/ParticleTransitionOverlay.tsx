import { useEffect, useRef } from 'react';

type Mode = 'dissolve' | 'reveal';
type Variant = 'eye' | 'login';

type Particle = {
  sx: number;
  sy: number;
  ex: number;
  ey: number;
  color: string;
  size: number;
};

function easeInOutCubic(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function clamp01(n: number) {
  return Math.max(0, Math.min(1, n));
}

function makeEyeTargets(width: number, height: number) {
  const cx = width / 2;
  const cy = height / 2;
  const scale = Math.min(width, height) * 0.35;
  const targets: Array<{ x: number; y: number; color: string; size: number }> = [];

  const create = (x: number, y: number, color: string, size: number) => targets.push({ x, y, color, size });

  // Upper / lower eyelid (lighter density than hero)
  for (let i = -55; i <= 55; i += 2) {
    const p = i / 55;
    const x = p * scale;
    const yTop = -Math.cos(p * Math.PI / 2) * scale * 0.45;
    const yBot = Math.cos(p * Math.PI / 2) * scale * 0.45;
    create(cx + x, cy + yTop, '#0284C7', 1.6);
    create(cx + x, cy + yBot, '#22c55e', 1.6);
  }

  // Iris ring
  for (let deg = 0; deg < 360; deg += 6) {
    const rad = (deg * Math.PI) / 180;
    const r = scale * 0.22;
    create(cx + Math.cos(rad) * r, cy + Math.sin(rad) * r, '#0284C7', 1.8);
  }

  // Pupil fill
  for (let r = 0; r < scale * 0.075; r += 3) {
    for (let deg = 0; deg < 360; deg += 18) {
      const rad = (deg * Math.PI) / 180;
      create(cx + Math.cos(rad) * r, cy + Math.sin(rad) * r, '#ffffff', 1.4);
    }
  }

  // Ambient field
  for (let i = 0; i < 140; i++) {
    const x = cx + (Math.random() - 0.5) * width * 1.2;
    const y = cy + (Math.random() - 0.5) * height * 1.2;
    create(x, y, Math.random() > 0.6 ? '#0284C7' : '#1e293b', 1.2);
  }

  return targets;
}

function makeLoginTargets(width: number, height: number) {
  // Approximate the login card bounds (centered) so particles can "form" it.
  // Keep density moderate to avoid jank on low-power devices.
  const cx = width / 2;
  const cy = height / 2;

  const cardW = Math.min(460, width * 0.92);
  const cardH = Math.min(620, height * 0.86);
  const left = cx - cardW / 2;
  const right = cx + cardW / 2;
  const top = cy - cardH / 2;
  const bottom = cy + cardH / 2;

  const targets: Array<{ x: number; y: number; color: string; size: number }> = [];
  const create = (x: number, y: number, color: string, size: number) => targets.push({ x, y, color, size });

  // Border points (rectangle outline)
  const step = Math.max(10, Math.floor(Math.min(cardW, cardH) / 40));
  for (let x = left; x <= right; x += step) {
    create(x, top, '#0284C7', 1.4);
    create(x, bottom, '#22c55e', 1.4);
  }
  for (let y = top; y <= bottom; y += step) {
    create(left, y, '#22c55e', 1.4);
    create(right, y, '#0284C7', 1.4);
  }

  // Corner accents
  create(left, top, '#ffffff', 1.6);
  create(right, top, '#ffffff', 1.6);
  create(left, bottom, '#ffffff', 1.6);
  create(right, bottom, '#ffffff', 1.6);

  // Sparse interior shimmer (gives the impression the panel is "materializing")
  const interiorCount = 160;
  for (let i = 0; i < interiorCount; i++) {
    const x = left + Math.random() * cardW;
    const y = top + Math.random() * cardH;
    create(x, y, Math.random() > 0.6 ? '#0284C7' : '#1e293b', 1.2);
  }

  return targets;
}

export function ParticleTransitionOverlay({
  active,
  mode,
  variant = 'eye',
  durationMs = 750,
  onComplete,
}: {
  active: boolean;
  mode: Mode;
  variant?: Variant;
  durationMs?: number;
  onComplete?: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = window.innerWidth;
    let height = window.innerHeight;
    const dpr = Math.min(1.5, window.devicePixelRatio || 1);

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();
    window.addEventListener('resize', resize);

    const cx = width / 2;
    const cy = height / 2;

    const targets = (mode === 'reveal' && variant === 'login') ? makeLoginTargets(width, height) : makeEyeTargets(width, height);
    const particles: Particle[] = targets.map((t) => {
      // End positions: fling outward
      const ang = Math.random() * Math.PI * 2;
      const dist = Math.min(width, height) * (0.55 + Math.random() * 0.8);
      const ex = cx + Math.cos(ang) * dist;
      const ey = cy + Math.sin(ang) * dist;

      const start = mode === 'dissolve' ? { x: t.x, y: t.y } : { x: ex, y: ey };
      const end = mode === 'dissolve' ? { x: ex, y: ey } : { x: t.x, y: t.y };

      return {
        sx: start.x,
        sy: start.y,
        ex: end.x,
        ey: end.y,
        color: t.color,
        size: t.size,
      };
    });

    const startTime = performance.now();
    // Cache the vignette gradient per run to avoid recreating it every frame.
    const vignette = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(width, height) * 0.6);
    vignette.addColorStop(0, 'rgba(0,0,0,0.5)');
    vignette.addColorStop(1, 'rgba(0,0,0,0)');

    const tick = (now: number) => {
      const rawT = (now - startTime) / durationMs;
      const t = clamp01(rawT);
      const e = easeInOutCubic(t);

      // Background fade: for reveal we fade out to show the login underneath; for dissolve we fade in.
      const bgAlpha = mode === 'dissolve' ? Math.min(1, e * 1.2) : Math.max(0, 1 - e * 1.1);

      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = `rgba(2, 6, 23, ${0.92 * bgAlpha})`; // slate-950-ish
      ctx.fillRect(0, 0, width, height);

      // Soft vignette
      ctx.globalAlpha = bgAlpha;
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, width, height);
      ctx.globalAlpha = 1;

      // Particles
      const particleAlpha = mode === 'dissolve' ? (t < 0.15 ? t / 0.15 : 1 - t * 0.15) : (t < 0.85 ? 1 : (1 - t) / 0.15);
      ctx.globalAlpha = Math.max(0, Math.min(1, particleAlpha));

      particles.forEach((p, idx) => {
        const jitter = Math.sin((now * 0.004) + idx * 0.13) * 1.2;
        const x = p.sx + (p.ex - p.sx) * e + jitter;
        const y = p.sy + (p.ey - p.sy) * e - jitter;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });

      ctx.globalAlpha = 1;

      if (t >= 1) {
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
        onComplete?.();
        return;
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      window.removeEventListener('resize', resize);
    };
  }, [active, mode, variant, durationMs, onComplete]);

  if (!active) return null;

  return (
    <div className="fixed inset-0 z-[9999] pointer-events-none">
      <canvas ref={canvasRef} className="absolute inset-0" />
    </div>
  );
}


