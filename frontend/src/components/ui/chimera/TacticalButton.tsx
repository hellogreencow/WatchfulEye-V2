import { ReactNode } from 'react';

interface TacticalButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'lethal' | 'glitch';
  children: ReactNode;
  className?: string;
}

export function TacticalButton({ variant = 'primary', children, className, ...props }: TacticalButtonProps) {
  const baseStyles = "relative h-10 px-4 flex items-center justify-center font-mono text-sm font-medium transition-all duration-200 active:scale-98 overflow-hidden uppercase tracking-wider";
  
  const variants = {
    primary: "bg-card border border-primary text-primary hover:bg-primary hover:text-background hover:shadow-neon",
    lethal: "bg-transparent border border-destructive text-destructive hover:bg-destructive hover:text-white hover:shadow-alert",
    glitch: "bg-card border border-primary text-primary hover:text-white overflow-hidden group"
  };

  if (variant === 'glitch') {
    return (
      <button className={`${baseStyles} ${variants.glitch} ${className}`} {...props}>
        <span className="relative z-10 group-hover:animate-pulse">{children}</span>
        <div className="absolute inset-0 bg-primary translate-y-full group-hover:translate-y-0 transition-transform duration-100" />
        {/* Glitch Overlay effects would go here, simplified for CSS performance */}
        <div className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 animate-pulse" />
      </button>
    );
  }

  return (
    <button className={`${baseStyles} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}
