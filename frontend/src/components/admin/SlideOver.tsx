import { ReactNode, useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface SlideOverProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  onSave?: () => void;
  saving?: boolean;
}

export default function SlideOver({ open, onClose, title, description, children, onSave, saving }: SlideOverProps) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (open) document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [open, onClose]);

  return (
    <>
      <div
        className={`fixed inset-0 bg-black/40 z-40 transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`}
        onClick={onClose}
      />
      <div
        className={`fixed right-0 top-0 h-full w-[520px] max-w-full shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${open ? "translate-x-0" : "translate-x-full"}`}
        style={{ background: "var(--aa-card)", border: "1px solid var(--aa-border)" }}
        data-testid="slideover-panel"
      >
        <div className="flex items-start justify-between px-6 py-5 shrink-0" style={{ borderBottom: "1px solid var(--aa-border)" }}>
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--aa-text)" }}>{title}</h2>
            {description && <p className="text-xs mt-0.5" style={{ color: "var(--aa-muted)" }}>{description}</p>}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors ml-4 shrink-0"
            style={{ color: "var(--aa-muted)" }}
            data-testid="slideover-close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {children}
        </div>

        {onSave && (
          <div className="px-6 py-4 shrink-0" style={{ borderTop: "1px solid var(--aa-border)", background: "var(--aa-card)" }}>
            <Button
              onClick={onSave}
              disabled={saving}
              className="w-full"
              style={{ background: "var(--aa-primary)", color: "var(--aa-primary-text, #fff)" }}
              data-testid="slideover-save"
            >
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        )}
      </div>
    </>
  );
}
