import { useEffect, useState, useRef } from "react";

/**
 * Animates a number from 0 to `target` over `duration` ms.
 * Only starts when the element enters the viewport.
 */
export function useCountUp(target: number, duration = 1000): number {
  const [count, setCount] = useState(0);
  const hasStarted = useRef(false);

  useEffect(() => {
    if (target === 0 || hasStarted.current) return;
    hasStarted.current = true;

    const startTime = performance.now();
    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutExpo
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setCount(Math.floor(eased * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [target, duration]);

  return count;
}
