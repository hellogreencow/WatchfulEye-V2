import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { TerminalInput } from '../ui/chimera/TerminalInput';
import { TacticalButton } from '../ui/chimera/TacticalButton';
import { Activity, ShieldCheck, Eye } from 'lucide-react';
import { Eye3D } from './EyeIcon';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../Dashboard';

// Decryption Text Effect Component
const DecryptionText = ({ text, onComplete }: { text: string, onComplete?: () => void }) => {
  const [display, setDisplay] = useState("");
  const characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$#@%&*";

  useEffect(() => {
    let iteration = 0;
    const interval = setInterval(() => {
      setDisplay(
        text
          .split("")
          .map((letter, index) => {
            if (index < iteration) {
              return text[index];
            }
            return characters[Math.floor(Math.random() * characters.length)];
          })
          .join("")
      );

      if (iteration >= text.length) {
        clearInterval(interval);
        onComplete?.();
      }

      iteration += 1 / 2; // Speed of decoding
    }, 30);

    return () => clearInterval(interval);
  }, [text]);

  return <span className="font-mono text-primary">{display}</span>;
};

// Toggle Switch Component
const TacticalToggle = ({ label, active, onClick }: { label: string, active: boolean, onClick: () => void }) => (
  <div 
    onClick={onClick}
    className="flex items-center cursor-pointer group select-none"
  >
    <div className={`w-10 h-5 border border-border relative mr-3 transition-colors ${active ? 'border-primary' : ''}`}>
      <motion.div 
        className={`absolute top-0.5 bottom-0.5 w-4 bg-foreground transition-colors ${active ? 'bg-primary shadow-neon' : ''}`}
        animate={{ x: active ? 22 : 2 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
      />
    </div>
    <span className={`text-xs font-mono font-bold tracking-wider transition-colors ${active ? 'text-primary' : 'text-muted-foreground'}`}>
      {label}
    </span>
  </div>
);

export function Login({ onLogin }: { onLogin?: () => void }) {
  const navigate = useNavigate();
  const auth = useAuth();
  
  const [view, setView] = useState<'auth' | 'loading'>('auth');
  const [isRegistering, setIsRegistering] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  
  // Form fields
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [entranceReady, setEntranceReady] = useState(false);

  // Let the route transition overlay do its reveal, then bring the card in.
  useEffect(() => {
    const t = window.setTimeout(() => setEntranceReady(true), 320);
    return () => window.clearTimeout(t);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setView('loading');
    setLoadingStep(0);

    try {
      let success = false;
      
      if (isRegistering) {
        success = await auth.register(username, email, password, fullName);
      } else {
        success = await auth.login(username, password);
      }

      if (success) {
        // Show loading animation steps
        setTimeout(() => setLoadingStep(1), 800);
        setTimeout(() => setLoadingStep(2), 1800);
        setTimeout(() => {
          setLoadingStep(3);
          // Redirect after animation completes
          setTimeout(() => {
            // Store auth token for Dashboard to detect
            localStorage.setItem('auth_token', 'authenticated');
            if (onLogin) {
              onLogin();
            } else {
              window.location.href = '/dashboard';
            }
          }, 1000);
        }, 2800);
      } else {
        setError(auth.error || 'Authentication failed');
        setView('auth');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setView('auth');
    }
  };

  const switchMode = () => {
    setIsRegistering(!isRegistering);
    setError(null);
    setUsername("");
    setEmail("");
    setPassword("");
    setFullName("");
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center relative overflow-auto p-4">
      {/* Wireframe Background - Enhanced Animation */}
      <div className="absolute inset-0 z-0 opacity-20 pointer-events-none overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#09090B_100%)] z-10" />
        <motion.div 
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] border border-primary/20 rounded-full"
          animate={{ rotate: 360, scale: [1, 1.05, 1] }}
          transition={{ 
            rotate: { duration: 60, repeat: Infinity as any, ease: "linear" },
            scale: { duration: 8, repeat: Infinity as any, ease: "easeInOut" }
          }}
        >
          {/* Wireframe lines */}
          <div className="absolute inset-0 border-t border-b border-primary/10 rounded-full rotate-45" />
          <div className="absolute inset-0 border-l border-r border-primary/10 rounded-full -rotate-45" />
          <div className="absolute top-0 left-0 right-0 h-full border border-primary/10 rounded-[40%]" />
          <div className="absolute top-0 left-0 bottom-0 w-full border border-primary/10 rounded-[40%] rotate-90" />
          
          {/* Inner Scanning Ring */}
          <motion.div 
            className="absolute inset-[10%] border border-primary/30 rounded-full border-dashed"
            animate={{ rotate: -180 }}
            transition={{ duration: 40, repeat: Infinity as any, ease: "linear" }}
          />
        </motion.div>
      </div>

      <AnimatePresence mode="wait">
        {view === 'auth' ? (
          <motion.div
            key="auth-card"
            initial={{ opacity: 0, scale: 0.92, y: 14, filter: "blur(12px)" }}
            animate={{ opacity: entranceReady ? 1 : 0, scale: entranceReady ? 1 : 0.92, y: entranceReady ? 0 : 14, filter: entranceReady ? "blur(0px)" : "blur(12px)" }}
            exit={{ opacity: 0, scale: 1.1, filter: "blur(10px)" }}
            transition={{ duration: 0.55, ease: "easeOut" }}
            className="relative z-20 w-full max-w-md my-auto"
          >
            {/* Bio-Scan Auth Card */}
            <div className="bg-card/80 backdrop-blur-xl border border-border p-8 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-primary to-transparent opacity-50" />

              {/* Back to Landing */}
              <button
                type="button"
                onClick={() => navigate('/')}
                className="absolute top-4 left-4 inline-flex items-center gap-2 px-3 py-1.5 text-[10px] font-mono font-bold tracking-widest uppercase border border-border bg-card/40 hover:bg-card/60 text-muted-foreground hover:text-primary transition-colors"
                aria-label="Back to landing page"
              >
                <span aria-hidden="true">←</span>
                <span>Back</span>
              </button>
              
              <div className="flex flex-col items-center justify-center mb-8 gap-4">
                <div className="relative group">
                  {/* Outer Ring */}
                  <motion.div 
                    className="absolute -inset-4 border border-primary/30 rounded-full"
                    animate={{ rotate: 360, scale: [1, 1.1, 1] }}
                    transition={{ 
                      rotate: { duration: 10, repeat: Infinity as any, ease: "linear" },
                      scale: { duration: 3, repeat: Infinity as any, ease: "easeInOut" }
                    }}
                  />
                  {/* Middle Ring */}
                  <motion.div 
                    className="absolute -inset-2 border border-primary/50 rounded-full border-t-transparent border-l-transparent"
                    animate={{ rotate: -360 }}
                    transition={{ duration: 5, repeat: Infinity as any, ease: "linear" }}
                  />
                  
                  {/* The Eye Icon */}
                  <Eye3D className="w-16 h-16 text-primary relative z-10" />
                </div>

                {/* Logo Text */}
                <div className="flex items-center gap-1 font-bold tracking-tighter text-2xl">
                  <span>WATCHFUL</span><span className="text-primary drop-shadow-[0_0_10px_rgba(59,130,246,0.5)]">EYE</span>
                </div>
              </div>

              {/* Mode Toggle */}
              <div className="flex bg-card/50 border border-border rounded-lg p-1 mb-6">
                <button 
                  onClick={() => setIsRegistering(false)}
                  className={`flex-1 py-2 px-4 rounded-md text-xs font-mono font-bold transition-all ${
                    !isRegistering
                      ? 'bg-primary/20 text-primary border border-primary/30 shadow-neon'
                      : 'text-muted-foreground hover:text-primary'
                  }`}
                >
                  SIGN IN
                </button>
                <button 
                  onClick={() => setIsRegistering(true)}
                  className={`flex-1 py-2 px-4 rounded-md text-xs font-mono font-bold transition-all ${
                    isRegistering
                      ? 'bg-primary/20 text-primary border border-primary/30 shadow-neon'
                      : 'text-muted-foreground hover:text-primary'
                  }`}
                >
                  ENLIST
                </button>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 rounded-lg">
                  <p className="text-destructive text-xs font-mono">{error}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold tracking-widest text-primary">
                    {isRegistering ? 'ENLISTMENT PROTOCOL' : 'IDENTIFICATION REQUIRED'}
                  </h3>
                  <div className="w-2 h-2 bg-red-500 rounded-full animate-ping" />
                </div>

                <div className="space-y-4">
                  <TerminalInput 
                    label="OPERATOR_ID" 
                    placeholder="ENTER USERNAME..." 
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                  
                  {isRegistering && (
                    <>
                      <TerminalInput 
                        label="EMAIL_ADDRESS" 
                        placeholder="OPERATOR@DOMAIN.COM" 
                        type="email"
                        autoComplete="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                      />
                      <TerminalInput 
                        label="FULL_NAME" 
                        placeholder="JOHN DOE" 
                        autoComplete="name"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                      />
                    </>
                  )}
                  
                  <TerminalInput 
                    label="ACCESS_KEY" 
                    type="password" 
                    placeholder="••••••••••••" 
                    autoComplete={isRegistering ? "new-password" : "current-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>

                <TacticalButton 
                  variant="glitch" 
                  type="submit"
                  className="w-full"
                  disabled={auth.loading}
                >
                  {isRegistering ? 'INITIALIZE ENLISTMENT' : 'INITIALIZE UPLINK'}
                </TacticalButton>
              </form>

              <div className="mt-6 text-center">
                <button 
                  onClick={switchMode} 
                  className="text-xs font-mono text-muted-foreground hover:text-primary transition-colors"
                  type="button"
                >
                  {isRegistering ? 'ALREADY ENLISTED? SIGN IN' : 'NOT ENLISTED? REGISTER'}
                </button>
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 bg-background flex flex-col items-center justify-center"
          >
            {/* Eye Loading Animation */}
            <div className="relative mb-12">
              <motion.div
                 initial={{ scale: 0.8, opacity: 0 }}
                 animate={{ scale: 1, opacity: 1 }}
                 transition={{ duration: 0.5 }}
              >
                <Eye3D className="w-24 h-24 text-primary fill-primary/20" />
              </motion.div>
              <motion.div
                 className="absolute inset-0 border border-primary rounded-full scale-150 opacity-0"
                 animate={{ scale: [1, 2], opacity: [0.5, 0] }}
                 transition={{ duration: 1.5, repeat: Infinity as any }}
              />
            </div>

            <div className="font-mono text-sm space-y-2 text-center h-24">
               {loadingStep >= 0 && (
                 <div className="flex items-center gap-3 text-muted-foreground">
                   <Activity className="w-3 h-3 text-primary" />
                   <DecryptionText text="ESTABLISHING SECURE HANDSHAKE..." />
                 </div>
               )}
               {loadingStep >= 1 && (
                 <div className="flex items-center gap-3 text-muted-foreground">
                   <ShieldCheck className="w-3 h-3 text-primary" />
                   <DecryptionText text="VERIFYING BIOMETRIC HASH..." />
                 </div>
               )}
               {loadingStep >= 2 && (
                 <div className="flex items-center gap-3 text-primary font-bold">
                   <span className="w-3 h-3 block bg-primary shadow-neon animate-pulse" />
                   <DecryptionText text="ACCESS GRANTED. WELCOME, OPERATOR." />
                 </div>
               )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

