import { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring } from 'motion/react';

export function CustomCursor() {
  const [isVisible, setIsVisible] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);

  const springConfig = { damping: 25, stiffness: 200, mass: 0.5 };
  const cursorXSpring = useSpring(cursorX, springConfig);
  const cursorYSpring = useSpring(cursorY, springConfig);

  useEffect(() => {
    // Disable custom cursor on mobile devices
    const checkMobile = () => {
      const mobile = window.innerWidth < 768 || ('ontouchstart' in window);
      setIsMobile(mobile);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);

    if (isMobile) {
      return () => window.removeEventListener('resize', checkMobile);
    }

    const moveCursor = (e: MouseEvent) => {
      cursorX.set(e.clientX);
      cursorY.set(e.clientY);
      setIsVisible(true);
    };

    const handleMouseEnter = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      // FIX: Ensure target is an element with closest method (avoids document/text node errors)
      if (!target || typeof target.closest !== 'function') return;

      if (target.tagName === 'BUTTON' || target.tagName === 'A' || target.closest('button') || target.closest('a')) {
        setIsHovering(true);
      }
    };

    const handleMouseLeave = () => {
      setIsHovering(false);
    };

    window.addEventListener('mousemove', moveCursor);
    document.addEventListener('mouseenter', handleMouseEnter, true);
    document.addEventListener('mouseleave', handleMouseLeave, true);
    document.addEventListener('mouseover', handleMouseEnter);

    return () => {
      window.removeEventListener('mousemove', moveCursor);
      window.removeEventListener('resize', checkMobile);
      document.removeEventListener('mouseenter', handleMouseEnter, true);
      document.removeEventListener('mouseleave', handleMouseLeave, true);
      document.removeEventListener('mouseover', handleMouseEnter);
    };
  }, [cursorX, cursorY, isMobile]);

  // Don't render cursor on mobile
  if (isMobile || !isVisible) return null;

  return (
    <>
      {/* Cursor Dot */}
      <motion.div
        className="fixed top-0 left-0 w-1 h-1 bg-[#0284C7] rounded-full pointer-events-none z-[9999]"
        style={{
          x: cursorXSpring,
          y: cursorYSpring,
          translateX: '-50%',
          translateY: '-50%',
        }}
      />

      {/* Cursor Ring */}
      <motion.div
        className="fixed top-0 left-0 border border-[#0284C7]/30 rounded-full pointer-events-none z-[9998]"
        style={{
          x: cursorXSpring,
          y: cursorYSpring,
          translateX: '-50%',
          translateY: '-50%',
        }}
        animate={{
          width: isHovering ? 40 : 24,
          height: isHovering ? 40 : 24,
          borderWidth: isHovering ? "2px" : "1px",
          opacity: isHovering ? 0.8 : 0.4,
        }}
        transition={{ duration: 0.2 }}
      />

      {/* Outer Glow */}
      <motion.div
        className="fixed top-0 left-0 bg-[#0284C7]/5 rounded-full pointer-events-none z-[9997] blur-xl"
        style={{
          x: cursorXSpring,
          y: cursorYSpring,
          translateX: '-50%',
          translateY: '-50%',
          width: 60,
          height: 60,
        }}
        animate={{
          opacity: isHovering ? 0.6 : 0.2,
        }}
      />
    </>
  );
}
