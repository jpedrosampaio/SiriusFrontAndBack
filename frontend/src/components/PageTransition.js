import { motion } from 'framer-motion';

export default function PageTransition({ children }) {
  // Route content must remain visible even when animation frames stop during
  // tab suspension, lazy loading or a native browser dialog.
  return (
    <div style={{ width: '100%' }}>
      {children}
    </div>
  );
}

// Stagger children animation
export function StaggerContainer({ children, className = '', delay = 0.05 }) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: { opacity: 0 },
        visible: {
          opacity: 1,
          transition: {
            staggerChildren: delay,
          },
        },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className = '' }) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 10 },
        visible: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.25, ease: 'easeOut' },
        },
      }}
    >
      {children}
    </motion.div>
  );
}

// Fade in on scroll
export function FadeInView({ children, className = '' }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 15 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  );
}
