import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Debounce a value — useful for search inputs that drive API calls.
 * The returned value only updates after `delay` ms of no new changes.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debouncedValue;
}

/**
 * Returns a stable debounced version of the callback.
 * The callback fires after `delay` ms of no new calls.
 * Useful for event handlers (scroll, resize, input onChange → API).
 */
export function useDebouncedCallback<T extends (...args: any[]) => any>(
  fn: T,
  delay: number,
): (...args: Parameters<T>) => void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  return useCallback((...args: Parameters<T>) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      fnRef.current(...args);
    }, delay);
  }, [delay]);
}

/**
 * Returns a stable throttled version of the callback.
 * The callback fires at most once per `limit` ms.
 * Useful for scroll/resize handlers or price tick handlers.
 */
export function useThrottledCallback<T extends (...args: any[]) => any>(
  fn: T,
  limit: number,
): (...args: Parameters<T>) => void {
  const lastRunRef = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  return useCallback((...args: Parameters<T>) => {
    const now = Date.now();
    if (now - lastRunRef.current >= limit) {
      lastRunRef.current = now;
      fnRef.current(...args);
    }
  }, [limit]);
}
