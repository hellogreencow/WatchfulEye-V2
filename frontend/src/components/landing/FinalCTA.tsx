import { motion, useScroll, useTransform } from 'motion/react';
import { useInView } from 'react-intersection-observer';
import { ArrowRight } from 'lucide-react';
import { useRef } from 'react';

export function FinalCTA({ onNavigate }: { onNavigate: (view: 'home' | 'news' | 'login') => void }) {
  const containerRef = useRef<HTMLElement>(null);
  const { ref, inView } = useInView({
    threshold: 0.3,
    triggerOnce: true,
  });

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start end', 'end start'],
  });

  const scale = useTransform(scrollYProgress, [0, 0.5], [0.8, 1]);
  const opacity = useTransform(scrollYProgress, [0, 0.3], [0, 1]);

  return (
    <section ref={containerRef} className="relative py-32 bg-[#1A1C1E] overflow-hidden">
      {/* Animated Background */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#0284C7]/5 to-transparent" />
      </div>

      <motion.div
        ref={ref}
        style={{ scale, opacity }}
        className="relative z-10 max-w-4xl mx-auto px-6 text-center"
      >
        {/* Main Content */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
        >
          <h2 className="text-5xl md:text-7xl font-light mb-6">
            <span className="text-white">Deploy</span>{' '}
            <span className="text-[#4A9FD8]">Intelligence</span>
          </h2>
          
          <p className="text-xl text-[#A5A8AB] mb-12 font-light leading-relaxed">
            Request access to institutional-grade geopolitical analysis.
            <br />
            Limited availability.
          </p>

          {/* CTA Button */}
          <motion.button
            className="group relative px-12 py-6 bg-gradient-to-r from-[#4A9FD8] to-[#3B7FA6] text-white overflow-hidden"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onNavigate('login')}
          >
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-[#3B7FA6] to-[#4A9FD8]"
              initial={{ x: '-100%' }}
              whileHover={{ x: '100%' }}
              transition={{ duration: 0.5 }}
            />
            <span className="relative z-10 flex items-center gap-3 text-sm uppercase tracking-wider">
              Request Access
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </span>
          </motion.button>

          {/* Metadata */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={inView ? { opacity: 1 } : {}}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="mt-12 flex items-center justify-center gap-8 text-xs text-[#6B7075]"
          >
            <span>Enterprise Grade</span>
            <span>•</span>
            <span>24/7 Support</span>
            <span>•</span>
            <span>SOC 2 Compliant</span>
          </motion.div>
        </motion.div>
      </motion.div>
    </section>
  );
}