import { useRef, useEffect, useState, useCallback, ReactNode } from "react";

interface Props {
  children: ReactNode;
  className?: string;
}

/**
 * Wraps a horizontally-scrollable container and shows a sticky scrollbar
 * fixed at the bottom of the viewport so users never need to scroll down
 * just to scroll the table horizontally.
 */
export function StickyTableScroll({ children, className = "" }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const ghostRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [barStyle, setBarStyle] = useState<React.CSSProperties>({});
  const syncing = useRef(false);

  const update = useCallback(() => {
    const wrap = wrapRef.current;
    const ghost = ghostRef.current;
    if (!wrap) return;

    const rect = wrap.getBoundingClientRect();
    const overflows = wrap.scrollWidth > wrap.clientWidth + 1;
    const inView = rect.top < window.innerHeight && rect.bottom > 50;

    setVisible(overflows && inView);
    setBarStyle({ left: rect.left, width: rect.width, bottom: 0 });

    if (ghost) ghost.style.width = `${wrap.scrollWidth}px`;
  }, []);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const ro = new ResizeObserver(update);
    ro.observe(wrap);
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update, { passive: true });
    update();
    return () => {
      ro.disconnect();
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [update]);

  const onWrapScroll = () => {
    if (syncing.current || !barRef.current || !wrapRef.current) return;
    syncing.current = true;
    barRef.current.scrollLeft = wrapRef.current.scrollLeft;
    syncing.current = false;
  };

  const onBarScroll = () => {
    if (syncing.current || !wrapRef.current || !barRef.current) return;
    syncing.current = true;
    wrapRef.current.scrollLeft = barRef.current.scrollLeft;
    syncing.current = false;
  };

  return (
    <>
      <div ref={wrapRef} className={`overflow-x-auto ${className}`} onScroll={onWrapScroll}>
        {children}
      </div>
      {visible && (
        <div
          ref={barRef}
          className="fixed z-50 overflow-x-scroll bg-white/80 backdrop-blur-sm border-t border-slate-200 shadow-sm"
          style={{ ...barStyle, height: 20 }}
          onScroll={onBarScroll}
        >
          <div ref={ghostRef} style={{ height: 1 }} />
        </div>
      )}
    </>
  );
}
