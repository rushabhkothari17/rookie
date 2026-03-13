import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

/**
 * Top-bar progress indicator that appears during route transitions.
 * Triggers on every location change.
 */
export function PageLoader() {
  const location = useLocation();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(true);
    setProgress(20);

    const t1 = setTimeout(() => setProgress(60), 100);
    const t2 = setTimeout(() => setProgress(85), 300);
    const t3 = setTimeout(() => {
      setProgress(100);
      setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 300);
    }, 500);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [location.pathname]);

  if (!visible) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: "2px",
        zIndex: 9999,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${progress}%`,
          background: `linear-gradient(90deg, var(--aa-accent), var(--aa-primary))`,
          transition: progress === 100
            ? "width 0.2s ease-out"
            : "width 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
          boxShadow: "0 0 10px var(--aa-accent), 0 0 4px rgba(255,255,255,0.3)",
          borderRadius: "0 2px 2px 0",
        }}
      />
    </div>
  );
}
