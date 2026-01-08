import { motion } from 'motion/react';
import { Eye } from 'lucide-react';

interface EyeIconProps {
  className?: string;
}

// Simple spinning eye - just the lucide Eye icon spinning horizontally in 3D
export function Eye3D({ className = "w-6 h-6" }: EyeIconProps) {
  return (
    <motion.div
      style={{
        perspective: '1000px',
      }}
      className={className}
    >
      <motion.div
        animate={{
          rotateY: [0, 360],
        }}
        transition={{
          duration: 8,
          repeat: Infinity as any,
          ease: "linear",
        }}
        style={{
          transformStyle: 'preserve-3d',
        }}
      >
        <Eye className={className} />
      </motion.div>
    </motion.div>
  );
}

export const AnimatedEyeIcon = Eye3D;
export const EyeIcon = Eye3D;