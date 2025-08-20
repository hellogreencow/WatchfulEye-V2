import React from 'react';
import { cn } from '../lib/utils';

type WatchfulEyeLogoProps = {
  className?: string;
  showText?: boolean;
  textClassName?: string;
  size?: number; // height in px
};

export default function WatchfulEyeLogo({
  className,
  showText = true,
  textClassName,
  size = 24,
}: WatchfulEyeLogoProps) {
  const height = size;
  const width = Math.round(size * 2.2);
  return (
    <div className={cn('flex items-center', className)} style={{ height }}>
      <svg
        width={width}
        height={height}
        viewBox="0 0 64 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0"
      >
        {/* Outer eye */}
        <path
          d="M2 16 Q16 2 32 2 Q48 2 62 16 Q48 30 32 30 Q16 30 2 16 Z"
          stroke="currentColor"
          strokeWidth="4"
          fill="none"
          strokeLinejoin="round"
        />
        {/* Pupil ring */}
        <circle cx="32" cy="16" r="6" stroke="currentColor" strokeWidth="4" fill="none" />
      </svg>
      {showText && (
        <span className={cn('ml-2 font-extrabold tracking-tight', textClassName)} style={{ lineHeight: `${height}px` }}>
          WatchfulEye
        </span>
      )}
    </div>
  );
}


