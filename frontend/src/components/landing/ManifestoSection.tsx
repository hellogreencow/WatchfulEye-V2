import { motion, useScroll, useTransform } from 'motion/react';
import { useRef } from 'react';
import { Shield, Target, Zap, Lock, Brain } from 'lucide-react';
import { Navigation } from './Navigation';
import { ThemeProvider } from '../../lib/theme-context';

export function ManifestoSection() {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end start"]
  });

  const opacity = useTransform(scrollYProgress, [0, 0.2, 0.8, 1], [0, 1, 1, 0]);

  return (
    <ThemeProvider>
      <div className="relative min-h-screen bg-background text-foreground">
        <Navigation />
        <div ref={containerRef} className="relative bg-background py-32 overflow-hidden pt-24">
      {/* Background Elements */}
      <div className="absolute inset-0 z-0">
        <div className="absolute top-0 left-1/4 w-px h-full bg-foreground/5" />
        <div className="absolute top-0 right-1/4 w-px h-full bg-foreground/5" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6">
        
        {/* Section 1: The Lie */}
        <section className="mb-40 grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
           <div>
              <h2 className="text-sm font-mono text-red-500 uppercase tracking-[0.3em] mb-4">/// DISINFORMATION DETECTED</h2>
              <h3 className="text-4xl md:text-6xl font-black leading-tight mb-6">
                THE MARKET IS <br/>
                <span className="text-foreground/20">A THEATER.</span>
              </h3>
              <p className="text-xl text-muted-foreground leading-relaxed">
                CNBC is noise. Twitter is panic. The charts you see are history, not the future.
                Retail traders are fed data that is 15 minutes late and 100% manipulated.
              </p>
           </div>
           <div className="relative h-64 md:h-96 border border-border bg-card/40 backdrop-blur-sm rounded-lg flex items-center justify-center overflow-hidden">
              <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1611974765270-ca12586343bb?q=80&w=2070&auto=format&fit=crop')] bg-cover bg-center opacity-20 mix-blend-overlay grayscale" />
              <div className="text-center">
                 <div className="text-6xl font-black text-foreground/10">NOISE</div>
                 <div className="text-6xl font-black text-foreground/10">NOISE</div>
                 <div className="text-6xl font-black text-foreground/10">NOISE</div>
              </div>
           </div>
        </section>

        {/* Section 2: The Solution */}
        <section className="mb-40 grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
           <div className="order-2 md:order-1 relative h-64 md:h-96 border border-primary/20 bg-primary/5 backdrop-blur-sm rounded-lg flex items-center justify-center">
              <Shield className="w-32 h-32 text-primary opacity-20" />
              <div className="absolute inset-0 border-x border-primary/20 w-1/3 mx-auto" />
              <div className="absolute inset-0 border-y border-primary/20 h-1/3 my-auto" />
           </div>
           <div className="order-1 md:order-2 text-right">
              <h2 className="text-sm font-mono text-primary uppercase tracking-[0.3em] mb-4">/// SOLUTION: PRIVATIZED INTEL</h2>
              <h3 className="text-4xl md:text-6xl font-black leading-tight mb-6">
                BECOME THE <br/>
                <span className="text-primary">STATION CHIEF.</span>
              </h3>
              <p className="text-xl text-muted-foreground leading-relaxed">
                WatchfulEye hands you the tools previously reserved for hedge funds and intelligence agencies.
                Satellite data. Dark pool liquidations. Sentiment velocity.
              </p>
           </div>
        </section>

        {/* Section 3: The Tools */}
        <section className="text-center mb-24">
           <h2 className="text-sm font-mono text-muted-foreground uppercase tracking-[0.3em] mb-12">/// THE ARSENAL</h2>
           
           <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <motion.div 
                whileHover={{ y: -5 }}
                className="group relative border border-border bg-card/40 hover:border-primary/50 transition-all rounded-sm text-left overflow-hidden"
              >
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary/0 via-primary/50 to-primary/0 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="p-6">
                  <div className="text-[10px] font-mono text-primary/50 mb-4">PROTOCOL_01</div>
                  <h4 className="text-lg font-mono font-bold mb-3 text-foreground">TASKING_PROTOCOLS</h4>
                  <p className="text-muted-foreground text-xs font-mono leading-relaxed">
                    &gt; INITIATE CHIMERA <br/>
                    &gt; TARGET ASSET <br/>
                    &gt; COMPILE DOSSIER
                  </p>
                </div>
                <div className="px-6 py-2 bg-card/40 border-t border-border flex justify-between items-center text-[10px] font-mono text-muted-foreground">
                  <span>STATUS: ACTIVE</span>
                  <span className="text-primary group-hover:animate-pulse">_READY</span>
                </div>
              </motion.div>

              <motion.div 
                whileHover={{ y: -5 }}
                className="group relative border border-border bg-card/40 hover:border-purple-500/50 transition-all rounded-sm text-left overflow-hidden"
              >
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-500/0 via-purple-500/50 to-purple-500/0 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="p-6">
                  <div className="text-[10px] font-mono text-purple-500/50 mb-4">PROTOCOL_02</div>
                  <h4 className="text-lg font-mono font-bold mb-3 text-foreground">NARRATIVE_VELOCITY</h4>
                  <p className="text-muted-foreground text-xs font-mono leading-relaxed">
                    &gt; SCAN SOCIAL_GRAPH <br/>
                    &gt; DETECT ANOMALIES <br/>
                    &gt; PREDICT VIRALITY
                  </p>
                </div>
                <div className="px-6 py-2 bg-card/40 border-t border-border flex justify-between items-center text-[10px] font-mono text-muted-foreground">
                  <span>DATA: 14TB/DAY</span>
                  <span className="text-purple-500 group-hover:animate-pulse">_STREAMING</span>
                </div>
              </motion.div>

              <motion.div 
                whileHover={{ y: -5 }}
                className="group relative border border-border bg-card/40 hover:border-emerald-500/50 transition-all rounded-sm text-left overflow-hidden"
              >
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500/0 via-emerald-500/50 to-emerald-500/0 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="p-6">
                  <div className="text-[10px] font-mono text-emerald-500/50 mb-4">PROTOCOL_03</div>
                  <h4 className="text-lg font-mono font-bold mb-3 text-foreground">CONSENSUS_ENGINE</h4>
                  <p className="text-muted-foreground text-xs font-mono leading-relaxed">
                    &gt; AGGREGATE BETS <br/>
                    &gt; CALCULATE PROBABILITY <br/>
                    &gt; EXECUTE TRADE
                  </p>
                </div>
                <div className="px-6 py-2 bg-card/40 border-t border-border flex justify-between items-center text-[10px] font-mono text-muted-foreground">
                  <span>MARKET: OPEN</span>
                  <span className="text-emerald-500 group-hover:animate-pulse">_LIVE</span>
                </div>
              </motion.div>
           </div>
        </section>

      </div>
        </div>
      </div>
    </ThemeProvider>
  );
}