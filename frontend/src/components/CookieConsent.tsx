import { useState, useEffect } from "react";
import { X, Cookie, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";

export function CookieConsent() {
  const [show, setShow] = useState(false);
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem("cookie_consent");
    if (!consent) {
      // Small delay before showing for better UX
      const timer = setTimeout(() => setShow(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem("cookie_consent", "accepted");
    setAccepted(true);
    setTimeout(() => setShow(false), 300);
  };

  const handleDecline = () => {
    localStorage.setItem("cookie_consent", "declined");
    setAccepted(true);
    setTimeout(() => setShow(false), 300);
  };

  if (!show) return null;

  return (
    <div
      className={`fixed bottom-0 left-0 right-0 z-50 transform transition-all duration-300 ease-out ${
        accepted ? "translate-y-full opacity-0" : "translate-y-0 opacity-100"
      }`}
      data-testid="cookie-consent-banner"
    >
      <div className="bg-slate-900 border-t border-slate-700 shadow-2xl">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            {/* Icon */}
            <div className="hidden sm:flex p-2 rounded-lg bg-slate-800 shrink-0">
              <Cookie className="h-5 w-5 text-amber-400" />
            </div>

            {/* Text */}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-slate-200 leading-relaxed">
                <span className="font-semibold text-white">We use cookies</span> to enhance your experience, 
                maintain your session, and analyze site usage. Essential cookies are required for basic 
                functionality. By continuing, you agree to our use of cookies.
              </p>
              <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                <Shield className="h-3 w-3" />
                Your privacy is protected. We never sell your data.
              </p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDecline}
                className="text-slate-400 hover:text-slate-200 hover:bg-slate-800 flex-1 sm:flex-none"
                data-testid="cookie-decline-btn"
              >
                Essential Only
              </Button>
              <Button
                size="sm"
                onClick={handleAccept}
                className="bg-amber-500 hover:bg-amber-600 text-slate-900 font-medium flex-1 sm:flex-none"
                data-testid="cookie-accept-btn"
              >
                Accept All
              </Button>
            </div>

            {/* Close button (mobile) */}
            <button
              onClick={handleDecline}
              className="absolute top-2 right-2 sm:hidden text-slate-500 hover:text-slate-300 p-1"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
