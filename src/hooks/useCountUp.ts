import { useEffect, useRef, useState } from 'react';

export function useCountUp(target: number, durationMs = 400): number {
  const [value, setValue] = useState(0);
  const startRef    = useRef<number | null>(null);
  const frameRef    = useRef<number>(0);
  const startVal    = useRef(0);
  // Tracks the last value actually rendered — used as the start of the next
  // animation so rapid updates animate from the current position, not from 0.
  const displayedRef = useRef(0);

  useEffect(() => {
    startVal.current  = displayedRef.current;
    startRef.current  = null;

    const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

    const tick = (now: number) => {
      if (startRef.current === null) startRef.current = now;
      const elapsed  = now - startRef.current;
      const progress = Math.min(elapsed / durationMs, 1);
      const eased    = easeOut(progress);
      const current  = startVal.current + (target - startVal.current) * eased;
      displayedRef.current = current;
      setValue(current);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        displayedRef.current = target;
        setValue(target);
      }
    };

    cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, durationMs]);

  return value;
}
