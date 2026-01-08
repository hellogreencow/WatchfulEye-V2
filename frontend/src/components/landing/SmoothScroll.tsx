import { ReactNode } from 'react';

interface SmoothScrollProps {
  children: ReactNode;
}

export function SmoothScroll({ children }: SmoothScrollProps) {
  // Simple wrapper - smooth scrolling can be handled via CSS
  return <div style={{ scrollBehavior: 'smooth' }}>{children}</div>;
}