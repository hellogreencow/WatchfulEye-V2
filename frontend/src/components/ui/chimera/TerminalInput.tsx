import { InputHTMLAttributes, useState } from 'react';

interface TerminalInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function TerminalInput({ label, className = '', style, ...props }: TerminalInputProps) {
  const [focused, setFocused] = useState(false);

  return (
    <div className="flex flex-col gap-1 w-full">
      {label && (
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest pl-1">
          {label}
        </label>
      )}
      <div className={`relative h-12 bg-input-background border transition-all duration-300 ${
        focused 
          ? 'border-primary shadow-neon' 
          : 'border-border'
      }`}>
        <input
          {...props}
          data-terminal-input="true"
          onFocus={(e) => {
            setFocused(true);
            props.onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            props.onBlur?.(e);
          }}
          style={{ ...style, color: '#1f2937' }}
          className={`w-full h-full bg-transparent px-4 font-mono text-sm placeholder:text-muted-foreground/50 focus:outline-none ${className} !text-gray-800 dark:!text-gray-800`}
        />
        {/* Decorative Corner accents */}
        <div className={`absolute top-0 left-0 w-2 h-2 border-t border-l transition-colors duration-300 ${focused ? 'border-primary' : 'border-transparent'}`} />
        <div className={`absolute bottom-0 right-0 w-2 h-2 border-b border-r transition-colors duration-300 ${focused ? 'border-primary' : 'border-transparent'}`} />
      </div>
    </div>
  );
}
