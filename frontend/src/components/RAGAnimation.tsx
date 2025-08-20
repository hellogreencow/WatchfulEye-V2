import React, { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

type RAGAnimationProps = {
  className?: string;
  steps?: string[];
  cycleMs?: number;
};

/**
 * Lightweight, delightful animation that visualizes a RAG pipeline:
 * - Query radar pulse
 * - Candidate articles orbiting and lighting up as "matched"
 * - Semantic ranking shimmer
 * - Composition wave
 */
export default function RAGAnimation({
  className,
  steps = [
    'Searching the article graph',
    'Ranking by semantic similarity',
    'Extracting factual passages',
    'Composing a concise briefing',
  ],
  cycleMs = 1100,
}: RAGAnimationProps) {
  const [stepIdx, setStepIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setStepIdx((i) => (i + 1) % steps.length);
    }, cycleMs);
    return () => clearInterval(id);
  }, [steps.length, cycleMs]);

  const nodes = useMemo(() => {
    // Precompute positions for 8 orbiting nodes
    return Array.from({ length: 8 }).map((_, i) => {
      const angle = (i / 8) * Math.PI * 2;
      const radius = 34 + (i % 2 ? 6 : 0);
      return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
    });
  }, []);

  return (
    <div
      className={
        'flex items-center gap-3 px-4 py-2 text-sm text-slate-600 dark:text-slate-300 ' +
        (className || '')
      }
      aria-live="polite"
      aria-busy="true"
    >
      {/* Graph viz */}
      <div className="relative w-24 h-24 shrink-0">
        {/* Radar pulse */}
        <motion.div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-blue-500/20"
          animate={{ scale: [1, 1.8, 1] , opacity: [0.7, 0, 0.7] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
        />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-blue-500 shadow-sm" />

        {/* Orbiting candidate docs */}
        {nodes.map((n, i) => (
          <motion.div
            key={i}
            className="absolute w-2.5 h-2.5 rounded-full"
            style={{ left: '50%', top: '50%', marginLeft: n.x, marginTop: n.y }}
            initial={{ scale: 0.8, opacity: 0.6 }}
            animate={{
              scale: [0.8, 1.05, 0.8],
              opacity: [0.6, 0.95, 0.6],
              backgroundColor:
                i % 3 === stepIdx % 3
                  ? ['#93c5fd', '#3b82f6', '#93c5fd']
                  : ['#94a3b8', '#cbd5e1', '#94a3b8'],
            }}
            transition={{ duration: 1.4 + (i % 3) * 0.1, repeat: Infinity }}
          />
        ))}

        {/* Ranking shimmer ring */}
        <motion.div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-blue-300/40"
          style={{ width: 86, height: 86 }}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 10, ease: 'linear' }}
        />
      </div>

      {/* Step text + progress dots */}
      <div className="min-w-[200px]">
        <AnimatePresence mode="wait">
          <motion.div
            key={stepIdx}
            initial={{ y: 6, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -6, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="text-[13px] leading-snug"
          >
            {steps[stepIdx]}
          </motion.div>
        </AnimatePresence>
        <div className="mt-1 flex gap-1.5">
          {steps.map((_, i) => (
            <motion.span
              key={i}
              className="inline-block w-1.5 h-1.5 rounded-full"
              animate={{
                backgroundColor: i === stepIdx ? '#3b82f6' : '#94a3b8',
                scale: i === stepIdx ? 1.2 : 1,
              }}
              transition={{ duration: 0.2 }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}


