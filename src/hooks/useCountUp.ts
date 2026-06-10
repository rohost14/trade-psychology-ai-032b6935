import { useEffect, useRef, useState } from 'react';

/**
 * Animates a number from 0 to `target` over `durationMs`.
 * Uses requestAnimationFrame for smooth 60fps easing.
 * Re-triggers whenever `target` changes.
 */
export function useCountUp(target: number, durationMs = 400): number {
  const [value, setValue] = useState(0);
  const startRef  = useRef<number | null>(null);
  const frameRef  = useRef<number>(0);
  const startVal  = useRef(0);

  useEffect(() => {
    startVal.current = 0;
    startRef.current = null;

    const easeOut = (t: number) => 1 - Math.pow(1 - t, 3); // cubic ease-out

    const tick = (now: number) => {
      if (startRef.current === null) startRef.current = now;
      const elapsed = now - startRef.current;
      const progress = Math.min(elapsed / durationMs, 1);
      const eased   = easeOut(progress);
      setValue(startVal.current + (target - startVal.current) * eased);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        setValue(target);
      }
    };

    cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, durationMs]);

  return value;
}
