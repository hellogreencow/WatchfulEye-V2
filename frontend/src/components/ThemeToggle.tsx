import React, { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    const saved = localStorage.getItem('we_theme');
    if (saved === 'dark') return true;
    if (saved === 'light') return false;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
      localStorage.setItem('we_theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('we_theme', 'light');
    }
  }, [isDark]);

  return (
    <button
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={() => setIsDark(prev => !prev)}
      className="fixed bottom-4 right-4 z-[10000] rounded-full border border-slate-200 dark:border-slate-700 bg-white/90 dark:bg-slate-800/90 backdrop-blur px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-200 shadow hover:shadow-md transition"
    >
      {isDark ? 'Light' : 'Dark'} Mode
    </button>
  );
}


