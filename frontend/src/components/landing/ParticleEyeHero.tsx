import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { ArrowRight } from 'lucide-react';

interface Point {
  x: number;
  y: number;
  originX: number;
  originY: number;
  targetX: number;
  targetY: number;
  color: string;
  size: number;
  baseX?: number; // Store the original target for noise calculation
  baseY?: number;
}

export function ParticleEyeHero({ onNavigate }: { onNavigate: (view: 'home' | 'news' | 'login') => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [points, setPoints] = useState<Point[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = window.innerWidth;
    let height = window.innerHeight;

    const initPoints = () => {
      const newPoints: Point[] = [];
      const cx = width / 2;
      const cy = height / 2;
      const scale = Math.min(width, height) * 0.35;
      
      // Create Eye Shape Points - THICKER & DENSER
      
      // 1. Upper Eyelid (Multiple Layers for Thickness)
      for (let offset = -2; offset <= 2; offset += 1) {
          for (let i = -60; i <= 60; i++) {
            const progress = i / 60;
            const x = progress * scale;
            // Parabolic curve for eyelid
            const y = -Math.cos(progress * Math.PI / 2) * scale * 0.5 + (offset * 2); 
            newPoints.push(createPoint(cx + x, cy + y));
          }
      }
      
      // 2. Lower Eyelid (Multiple Layers)
      for (let offset = -2; offset <= 2; offset += 1) {
          for (let i = -60; i <= 60; i++) {
            const progress = i / 60;
            const x = progress * scale;
            const y = Math.cos(progress * Math.PI / 2) * scale * 0.5 + (offset * 2);
            newPoints.push(createPoint(cx + x, cy + y));
          }
      }
      
      // 3. Iris (Circle) - Denser
      // Multiple rings for thickness
      for (let rOffset = 0; rOffset < 15; rOffset += 2) {
          for (let i = 0; i < 360; i += 3) { // Step 3 for high density
            const rad = (i * Math.PI) / 180;
            const r = (scale * 0.25) - rOffset; // Inward thickness
            const x = Math.cos(rad) * r;
            const y = Math.sin(rad) * r;
            newPoints.push(createPoint(cx + x, cy + y, '#0284C7')); // Sky 600 (Deep Blue)
          }
      }

      // 4. Pupil (Filled Circle) - Denser
      for (let r = 0; r < scale * 0.1; r += 2) {
        for (let i = 0; i < 360; i += 10) {
           const rad = (i * Math.PI) / 180;
           const x = Math.cos(rad) * r;
           const y = Math.sin(rad) * r;
           newPoints.push(createPoint(cx + x, cy + y, '#ffffff')); // Pupil White
        }
      }

      // 5. Random "Noise" Data Points (Scattered field)
      for (let i = 0; i < 200; i++) {
        const x = (Math.random() - 0.5) * width * 1.5;
        const y = (Math.random() - 0.5) * height * 1.5;
        newPoints.push(createPoint(cx + x, cy + y, '#1e293b', true)); // Darker background noise
      }

      return newPoints;
    };

    const createPoint = (targetX: number, targetY: number, color?: string, isNoise: boolean = false): Point => {
      const angle = Math.random() * Math.PI * 2;
      const dist = Math.random() * 2000; // Start far away
      return {
        x: width / 2 + Math.cos(angle) * dist,
        y: height / 2 + Math.sin(angle) * dist,
        originX: width / 2 + Math.cos(angle) * dist,
        originY: height / 2 + Math.sin(angle) * dist,
        targetX,
        targetY,
        baseX: targetX,
        baseY: targetY,
        color: color || (Math.random() > 0.5 ? '#22c55e' : '#0284C7'), // Green or Sky 600
        size: isNoise ? Math.random() * 1.5 : Math.random() * 2.5 + 1, // Slightly larger particles
      };
    };

    let pts = initPoints();

    const render = () => {
      ctx.fillStyle = '#020617'; // Dark slate/black bg
      ctx.fillRect(0, 0, width, height);
      
      // Grid effect
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      for (let i = 0; i < width; i += 100) { ctx.moveTo(i, 0); ctx.lineTo(i, height); }
      for (let i = 0; i < height; i += 100) { ctx.moveTo(0, i); ctx.lineTo(width, i); }
      ctx.stroke();

      const time = Date.now() * 0.002;

      pts.forEach((p, index) => {
        // Calculate dynamic target with noise/jitter
        // We use the index to offset the phase so they don't move in unison
        const noiseX = Math.cos(time + index * 0.1) * 3; 
        const noiseY = Math.sin(time + index * 0.1) * 3;
        
        // If it's a "noise" point, it wanders more
        const currentTargetX = (p.baseX || p.targetX) + noiseX;
        const currentTargetY = (p.baseY || p.targetY) + noiseY;

        // Lerp towards dynamic target
        p.x += (currentTargetX - p.x) * 0.05; // Slightly faster convergence
        p.y += (currentTargetY - p.y) * 0.05;
        
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    const handleResize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width;
      canvas.height = height;
      pts = initPoints();
    };

    window.addEventListener('resize', handleResize);
    handleResize();
    render();

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden">
      <canvas ref={canvasRef} className="absolute inset-0 z-0" />
      
      {/* Overlay Gradient for Text Readability */}
      <div className="absolute inset-0 z-10 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-transparent" />
        <div 
          className="absolute inset-0 opacity-80" 
          style={{ background: 'radial-gradient(circle at center, rgba(0,0,0,0.8) 0%, transparent 70%)' }}
        />
      </div>

      {/* Content */}
      <div className="relative z-20 text-center max-w-4xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 1 }}
        >
          <h1 className="text-6xl md:text-8xl lg:text-9xl font-black tracking-tighter mb-6 text-white drop-shadow-[0_0_30px_rgba(0,0,0,0.8)]">
            THE EYE SEES ALL
          </h1>
          
          <p className="text-xl md:text-2xl text-blue-100/90 mb-12 max-w-2xl mx-auto font-light leading-relaxed drop-shadow-lg">
            Data points. Chaos. Noise. <br/>
            <span className="text-white font-bold">WatchfulEye</span> connects them into a singular intelligence picture.
          </p>

          <div className="flex items-center justify-center gap-6">
            <button 
              onClick={() => onNavigate('login')}
              className="group relative px-8 py-4 bg-white text-black font-bold uppercase tracking-widest text-sm hover:bg-blue-50 transition-colors rounded-sm shadow-[0_0_20px_rgba(255,255,255,0.3)]"
            >
              Initialize System
            </button>
          </div>
        </motion.div>
      </div>
      
      {/* Scrolling indicators */}
      <div className="absolute bottom-10 left-0 right-0 flex justify-center z-20">
        <div className="flex flex-col items-center gap-2 text-[10px] text-white/30 font-mono uppercase tracking-[0.2em]">
           <span>Scroll for Intel</span>
           <div className="h-12 w-px bg-gradient-to-b from-white/50 to-transparent" />
        </div>
      </div>
    </section>
  );
}
