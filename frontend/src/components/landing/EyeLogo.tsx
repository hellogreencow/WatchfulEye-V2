import { motion } from 'motion/react';
import { useEffect, useState } from 'react';

interface EyeLogoProps {
  size?: number;
  className?: string;
}

export function EyeLogo({ size = 40, className = '' }: EyeLogoProps) {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [pupilPos, setPupilPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useEffect(() => {
    const maxMove = size * 0.15;
    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;
    
    const deltaX = (mousePos.x - centerX) / centerX;
    const deltaY = (mousePos.y - centerY) / centerY;
    
    setPupilPos({
      x: deltaX * maxMove,
      y: deltaY * maxMove
    });
  }, [mousePos, size]);

  return (
    <div className={`relative ${className}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="w-full h-full">
        {/* Outer Eye Shape */}
        <ellipse
          cx="50"
          cy="50"
          rx="45"
          ry="30"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-cyan-400"
        />
        
        {/* Inner Iris */}
        <motion.g
          animate={{
            x: pupilPos.x,
            y: pupilPos.y
          }}
          transition={{ type: 'spring', stiffness: 150, damping: 15 }}
        >
          <circle
            cx="50"
            cy="50"
            r="12"
            fill="currentColor"
            className="text-cyan-500/20"
          />
          
          {/* Pupil */}
          <circle
            cx="50"
            cy="50"
            r="6"
            fill="currentColor"
            className="text-cyan-400"
          />
          
          {/* Highlight */}
          <circle
            cx="52"
            cy="47"
            r="2"
            fill="currentColor"
            className="text-white"
            opacity="0.8"
          />
        </motion.g>

        {/* Scan Line */}
        <motion.line
          x1="5"
          y1="50"
          x2="95"
          y2="50"
          stroke="currentColor"
          strokeWidth="0.5"
          className="text-cyan-400"
          animate={{
            y1: [30, 70, 30],
            y2: [30, 70, 30],
            opacity: [0.3, 0.6, 0.3]
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut'
          }}
        />
      </svg>
    </div>
  );
}
