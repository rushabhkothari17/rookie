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

  const socialLinks = [
    { key: "twitter", label: "X / Twitter", url: ws.social_twitter, icon: "𝕏" },
    { key: "linkedin", label: "LinkedIn", url: ws.social_linkedin, icon: "in" },
    { key: "facebook", label: "Facebook", url: ws.social_facebook, icon: "f" },
    { key: "instagram", label: "Instagram", url: ws.social_instagram, icon: "ig" },
    { key: "youtube", label: "YouTube", url: ws.social_youtube, icon: "▶" },
  ].filter(s => s.url);

  const hasContact = ws.contact_email || ws.contact_phone || ws.contact_address;

  return (
    <footer className="bg-slate-950 text-slate-400 mt-auto" data-testid="app-footer">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-10">

          {/* Brand & About */}
          <div className="space-y-3 lg:col-span-1">
            <div className="text-white font-semibold text-base tracking-tight" data-testid="footer-brand-name">
              {ws.store_name || "Brand"}
            </div>
            {ws.footer_tagline && (
              <p className="text-sm text-slate-400 leading-relaxed max-w-xs" data-testid="footer-tagline">
                {ws.footer_tagline}
              </p>
            )}
            {ws.footer_about_text && (
              <div className="pt-1">
                {ws.footer_about_title && (
                  <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-2" data-testid="footer-about-title">
                    {ws.footer_about_title}
                  </p>
                )}
                <p className="text-sm text-slate-400 leading-relaxed max-w-xs" data-testid="footer-about-text">
                  {ws.footer_about_text}
                </p>
              </div>
            )}
          </div>

          {/* Navigation */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-widest text-slate-500" data-testid="footer-nav-title">
              {ws.footer_nav_title || "Navigation"}
            </h4>
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
          {hasContact && (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-widest text-slate-500" data-testid="footer-contact-title">
                {ws.footer_contact_title || "Contact"}
              </h4>
              <ul className="space-y-2">
                {ws.contact_email && (
                  <li className="flex items-center gap-2 text-sm">
                    <Mail size={13} className="shrink-0 text-slate-500" />
                    <a href={`mailto:${ws.contact_email}`} className="hover:text-white transition-colors truncate" data-testid="footer-email">
                      {ws.contact_email}
                    </a>
                  </li>
                )}
                {ws.contact_phone && (
                  <li className="flex items-center gap-2 text-sm">
                    <Phone size={13} className="shrink-0 text-slate-500" />
                    <a href={`tel:${ws.contact_phone}`} className="hover:text-white transition-colors" data-testid="footer-phone">
                      {ws.contact_phone}
                    </a>
                  </li>
                )}
                {ws.contact_address && (
                  <li className="flex items-start gap-2 text-sm">
                    <MapPin size={13} className="shrink-0 text-slate-500 mt-0.5" />
                    <span className="leading-relaxed" data-testid="footer-address">{ws.contact_address}</span>
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* Social Media */}
          {socialLinks.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-widest text-slate-500" data-testid="footer-social-title">
                {ws.footer_social_title || "Follow Us"}
              </h4>
              <ul className="space-y-2">
                {socialLinks.map((s) => (
                  <li key={s.key}>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-slate-400 hover:text-white transition-colors flex items-center gap-2"
                      data-testid={`footer-social-${s.key}`}
                    >
                      <span className="text-xs font-mono w-4 text-center text-slate-500">{s.icon}</span>
                      {s.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Bottom bar */}
        {ws.footer_copyright && (
          <div className="mt-10 pt-6 border-t border-slate-800">
            <p className="text-xs text-slate-600" data-testid="footer-copyright">{ws.footer_copyright}</p>
          </div>
        )}
      </div>
    </footer>
  );
}
