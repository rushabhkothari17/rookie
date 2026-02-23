import { Link } from "react-router-dom";
import { useWebsite } from "@/contexts/WebsiteContext";
import { Mail, Phone, MapPin } from "lucide-react";

export default function AppFooter() {
  const ws = useWebsite();

  const navLinks = [
    { label: ws.nav_store_label || "Store", to: "/store" },
    { label: ws.nav_articles_label || "Articles", to: "/articles" },
    { label: ws.nav_portal_label || "Portal", to: "/portal" },
  ];

  return (
    <footer className="bg-slate-950 text-slate-400 mt-auto" data-testid="app-footer">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          {/* Brand */}
          <div className="space-y-3">
            <div className="text-white font-semibold text-base tracking-tight">
              {ws.store_name || "Brand"}
            </div>
            {ws.footer_tagline && (
              <p className="text-sm text-slate-400 leading-relaxed max-w-xs">{ws.footer_tagline}</p>
            )}
          </div>

          {/* Navigation */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Navigation</h4>
            <ul className="space-y-2">
              {navLinks.map((link) => (
                <li key={link.to}>
                  <Link
                    to={link.to}
                    className="text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Contact */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Contact</h4>
            <ul className="space-y-2">
              {ws.contact_email && (
                <li className="flex items-center gap-2 text-sm">
                  <Mail size={13} className="shrink-0 text-slate-500" />
                  <a href={`mailto:${ws.contact_email}`} className="hover:text-white transition-colors truncate">
                    {ws.contact_email}
                  </a>
                </li>
              )}
              {ws.contact_phone && (
                <li className="flex items-center gap-2 text-sm">
                  <Phone size={13} className="shrink-0 text-slate-500" />
                  <a href={`tel:${ws.contact_phone}`} className="hover:text-white transition-colors">
                    {ws.contact_phone}
                  </a>
                </li>
              )}
              {ws.contact_address && (
                <li className="flex items-start gap-2 text-sm">
                  <MapPin size={13} className="shrink-0 text-slate-500 mt-0.5" />
                  <span className="leading-relaxed">{ws.contact_address}</span>
                </li>
              )}
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        {ws.footer_copyright && (
          <div className="mt-10 pt-6 border-t border-slate-800">
            <p className="text-xs text-slate-600">{ws.footer_copyright}</p>
          </div>
        )}
      </div>
    </footer>
  );
}
