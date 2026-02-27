import SlideOver from "@/components/admin/SlideOver";
import CheckoutSectionsBuilder from "@/components/admin/CheckoutSectionsBuilder";
import FormSchemaBuilder from "@/components/FormSchemaBuilder";
import { AuthSlide, WebsiteData, AuthTile, Field, SectionDivider } from "./websiteTabShared";
import { Section } from "./websiteTabShared";

const SIGNUP_DEFAULT_SCHEMA = JSON.stringify([
  { id: "sf_full_name",    key: "full_name",    label: "Full Name",    type: "text", required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 0 },
  { id: "sf_company_name", key: "company_name", label: "Company Name", type: "text", required: false, placeholder: "", options: [], locked: true,  enabled: true,  order: 1 },
  { id: "sf_job_title",    key: "job_title",    label: "Job Title",    type: "text", required: false, placeholder: "", options: [], locked: true,  enabled: true,  order: 2 },
  { id: "sf_phone",        key: "phone",        label: "Phone",        type: "tel",  required: false, placeholder: "", options: [], locked: true,  enabled: true,  order: 3 },
  { id: "sf_address",      key: "address",      label: "Address",      type: "text", required: false, placeholder: "", options: [], locked: true,  enabled: true,  order: 4 },
]);

function getFieldCount(schema: string): number {
  try { return JSON.parse(schema || "[]").length; } catch { return 0; }
}

function getSlideTitle(key: AuthSlide | null): string {
  if (!key) return "";
  const map: Record<AuthSlide, string> = {
    login: "Login Page", signup: "Sign Up Page", verify_email: "Verify Email Page",
    portal: "Customer Portal", profile: "Profile Page",
    not_found: "404 Not Found Page", admin_panel: "Admin Panel",
    checkout_builder: "Checkout Page Builder", checkout_success: "Checkout Success",
    gocardless_callback: "GoCardless Callback Page",
    checkout_messages: "Checkout Messages",
    footer_basics: "Footer Text", footer_about: "About Us Section",
    footer_nav: "Navigation", footer_contact: "Contact Info", footer_social: "Social Media",
    documents_page: "Documents Page",
    store_hero: "Store Hero Banner",
    articles_hero: "Articles Hero Banner",
  };
  return map[key];
}

function getSlideDesc(key: AuthSlide | null): string {
  if (!key) return "";
  const map: Record<AuthSlide, string> = {
    login: "Text shown on the login page.", signup: "Text + custom fields on the registration page.",
    verify_email: "Text shown when customers verify their email.", portal: "Heading and subtitle on the customer portal.",
    profile: "Heading and subtitle on the profile page.", not_found: "Content for the 404 error page.",
    admin_panel: "Admin panel page heading, subtitle, and badge.",
    checkout_builder: "Build and configure checkout sections. Includes cart page settings.",
    checkout_success: "Success page content for Stripe and bank transfer payments.",
    gocardless_callback: "Processing, success, and error page text shown during GoCardless direct debit setup.",
    checkout_messages: "Customer-facing error and instruction messages during checkout.",
    footer_basics: "Tagline and copyright text shown in the footer.",
    footer_about: "About us section heading and descriptive text.",
    footer_nav: "Navigation section title and link labels.",
    footer_contact: "Contact details shown in the footer.",
    footer_social: "Social media platform links.",
    documents_page: "Customize the Documents page heading, subtitle, nav label, and upload instructions.",
    store_hero: "Hero banner label, title, and subtitle shown on the main store page.",
    articles_hero: "Hero banner label, title, and subtitle shown on the resources/articles page.",
  };
  return map[key];
}

interface Props {
  ws: WebsiteData;
  s: (key: keyof WebsiteData) => (v: string) => void;
  authSlide: AuthSlide | null;
  setAuthSlide: (slide: AuthSlide | null) => void;
  saveSection: (onDone?: () => void) => void;
  slideSaving: boolean;
  setActiveSection: (section: Section) => void;
}

export function AuthPagesSection({ ws, s, authSlide, setAuthSlide, saveSection, slideSaving, setActiveSection }: Props) {
  return (
    <>
      <div className="mb-2">
        <h3 className="text-sm font-semibold text-slate-700">Auth & Pages</h3>
        <p className="text-xs text-slate-400 mt-0.5">Click any tile to edit text, forms, or page content.</p>
      </div>

      <SectionDivider label="Authentication" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <AuthTile title="Login Page" description="Login title, subtitle, portal label" preview={ws.login_title || undefined} onEdit={() => setAuthSlide("login")} testId="auth-tile-login" />
        <AuthTile title="Sign Up Page" description={`Register page + ${getFieldCount(ws.signup_form_schema)} form fields`} preview={ws.register_title || undefined} onEdit={() => setAuthSlide("signup")} testId="auth-tile-signup" />
        <AuthTile title="Verify Email" description="Verification page content" preview={ws.verify_email_title || undefined} onEdit={() => setAuthSlide("verify_email")} testId="auth-tile-verify-email" />
      </div>

      <SectionDivider label="App Pages" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <AuthTile title="Customer Portal" preview={ws.portal_title || undefined} description="Portal heading & subtitle" onEdit={() => setAuthSlide("portal")} testId="auth-tile-portal" />
        <AuthTile title="Profile Page" preview={ws.profile_title || undefined} description="Profile heading & subtitle" onEdit={() => setAuthSlide("profile")} testId="auth-tile-profile" />
        <AuthTile title="Admin Panel" preview={ws.admin_page_title || "Admin Control Centre"} description="Admin panel heading, subtitle, and badge text" onEdit={() => setAuthSlide("admin_panel")} testId="auth-tile-admin-panel" />
        <AuthTile title="404 Not Found" preview={ws.page_404_title || undefined} description="Error page content" onEdit={() => setAuthSlide("not_found")} testId="auth-tile-404" />
        <AuthTile title="Documents Page" description="Page heading, subtitle, nav label, upload text" preview={ws.documents_page_title || undefined} onEdit={() => setAuthSlide("documents_page")} testId="auth-tile-documents" />
      </div>

      <SectionDivider label="Hero Banners" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <AuthTile title="Store Hero Banner" description="Label, title, subtitle on main store page" preview={ws.hero_title || undefined} onEdit={() => setAuthSlide("store_hero")} testId="auth-tile-store-hero" />
        <AuthTile title="Articles Hero Banner" description="Label, title, subtitle on resources page" preview={ws.articles_hero_title || undefined} onEdit={() => setAuthSlide("articles_hero")} testId="auth-tile-articles-hero" />
      </div>

      <SectionDivider label="Checkout Flow" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <AuthTile title="Checkout Page Builder" description="Dynamic sections + cart page settings" onEdit={() => setAuthSlide("checkout_builder")} testId="auth-tile-checkout-builder" />
        <AuthTile title="Checkout Success" preview={ws.checkout_success_title || undefined} description="Page after successful payment or bank transfer" onEdit={() => setAuthSlide("checkout_success")} testId="auth-tile-checkout-success" />
      </div>

      <SectionDivider label="Messages" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <AuthTile title="Checkout Messages" description="Cart, payment errors & messages" onEdit={() => setAuthSlide("checkout_messages")} testId="auth-tile-checkout-messages" />
      </div>

      <SectionDivider label="Footer & Navigation" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <AuthTile title="Footer Text" description="Tagline and copyright" preview={ws.footer_tagline || ws.footer_copyright || undefined} onEdit={() => setAuthSlide("footer_basics")} testId="footer-tile-basics" />
        <AuthTile title="About Us" description="About section heading and text" preview={ws.footer_about_title || undefined} onEdit={() => setAuthSlide("footer_about")} testId="footer-tile-about" />
        <AuthTile title="Navigation" description="Nav section title and link labels" preview={ws.footer_nav_title || undefined} onEdit={() => setAuthSlide("footer_nav")} testId="footer-tile-nav" />
        <AuthTile title="Contact Info" description="Email, phone, and address" preview={ws.contact_email || undefined} onEdit={() => setAuthSlide("footer_contact")} testId="footer-tile-contact" />
        <AuthTile title="Social Media" description="Social network links" preview={ws.footer_social_title || undefined} onEdit={() => setAuthSlide("footer_social")} testId="footer-tile-social" />
      </div>

      {/* Auth Slide Over */}
      <SlideOver
        open={authSlide !== null}
        onClose={() => setAuthSlide(null)}
        title={getSlideTitle(authSlide)}
        description={getSlideDesc(authSlide)}
        onSave={() => saveSection(() => setAuthSlide(null))}
        saving={slideSaving}
      >
        {authSlide === "login" && (
          <div className="space-y-4">
            <Field label="Portal label" hint='Small label above title (e.g. "Customer Portal")' value={ws.login_portal_label} onChange={s("login_portal_label")} testId="ws-login-portal" />
            <Field label="Title" value={ws.login_title} onChange={s("login_title")} testId="ws-login-title" />
            <Field label="Subtitle" value={ws.login_subtitle} onChange={s("login_subtitle")} testId="ws-login-subtitle" />
          </div>
        )}
        {authSlide === "signup" && (
          <div className="space-y-4">
            <Field label="Page title" value={ws.register_title} onChange={s("register_title")} testId="ws-register-title" />
            <Field label="Page subtitle" value={ws.register_subtitle} onChange={s("register_subtitle")} multiline testId="ws-register-subtitle" />
            <Field label="Form title" value={ws.signup_form_title} onChange={s("signup_form_title")} testId="ws-signup-title" />
            <Field label="Form subtitle" value={ws.signup_form_subtitle} onChange={s("signup_form_subtitle")} multiline testId="ws-signup-subtitle" />
            <div className="border-t border-slate-100 pt-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Feature Bullets (shown on left side of signup page)</p>
              <p className="text-xs text-slate-400 mb-3">Leave blank to use defaults.</p>
              <div className="space-y-2">
                <Field label="Bullet 1" value={ws.signup_bullet_1} onChange={s("signup_bullet_1")} placeholder="Access your orders and subscriptions" testId="ws-signup-bullet-1" />
                <Field label="Bullet 2" value={ws.signup_bullet_2} onChange={s("signup_bullet_2")} placeholder="Download invoices and documents" testId="ws-signup-bullet-2" />
                <Field label="Bullet 3" value={ws.signup_bullet_3} onChange={s("signup_bullet_3")} placeholder="Track project progress in real time" testId="ws-signup-bullet-3" />
                <Field label="CTA / Closing statement" hint='Bold callout line shown below bullets (e.g. "Get started in minutes")' value={ws.signup_cta} onChange={s("signup_cta")} placeholder="Get started in minutes" testId="ws-signup-cta" />
              </div>
            </div>
            <div className="border-t border-slate-100 pt-3">
              <FormSchemaBuilder title="Registration form fields" value={ws.signup_form_schema || SIGNUP_DEFAULT_SCHEMA} onChange={s("signup_form_schema")} />
            </div>
          </div>
        )}
        {authSlide === "verify_email" && (
          <div className="space-y-4">
            <Field label="Step label" value={ws.verify_email_label} onChange={s("verify_email_label")} testId="ws-ve-label" />
            <Field label="Title" value={ws.verify_email_title} onChange={s("verify_email_title")} testId="ws-ve-title" />
            <Field label="Subtitle / instructions" value={ws.verify_email_subtitle} onChange={s("verify_email_subtitle")} multiline testId="ws-ve-subtitle" />
          </div>
        )}
        {authSlide === "portal" && (
          <div className="space-y-4">
            <Field label="Page title" value={ws.portal_title} onChange={s("portal_title")} testId="ws-portal-title" />
            <Field label="Page subtitle" value={ws.portal_subtitle} onChange={s("portal_subtitle")} multiline testId="ws-portal-subtitle" />
          </div>
        )}
        {authSlide === "profile" && (
          <div className="space-y-4">
            <Field label="Breadcrumb label" value={ws.profile_label} onChange={s("profile_label")} testId="ws-profile-label" />
            <Field label="Page title" value={ws.profile_title} onChange={s("profile_title")} testId="ws-profile-title" />
            <Field label="Page subtitle" value={ws.profile_subtitle} onChange={s("profile_subtitle")} multiline testId="ws-profile-subtitle" />
          </div>
        )}
        {authSlide === "not_found" && (
          <div className="space-y-4">
            <Field label="Heading" value={ws.page_404_title} onChange={s("page_404_title")} testId="ws-404-title" />
            <Field label="Back link text" value={ws.page_404_link_text} onChange={s("page_404_link_text")} testId="ws-404-link" />
          </div>
        )}
        {authSlide === "admin_panel" && (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">Customise the header shown at the top of the admin panel dashboard.</p>
            <Field label="Badge text" hint='Small label above the title (e.g. "ADMINISTRATION")' value={ws.admin_page_badge} onChange={s("admin_page_badge")} testId="ws-admin-badge" />
            <Field label="Title" hint='Main heading (e.g. "Admin Control Centre")' value={ws.admin_page_title} onChange={s("admin_page_title")} testId="ws-admin-title" />
            <Field label="Subtitle" hint="Shown below the title" value={ws.admin_page_subtitle} onChange={s("admin_page_subtitle")} multiline testId="ws-admin-subtitle" />
          </div>
        )}
        {authSlide === "checkout_builder" && (
          <div className="space-y-5">
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Dynamic Sections</p>
              <p className="text-xs text-slate-400 mb-3">Build custom sections for the checkout page.</p>
              <CheckoutSectionsBuilder value={ws.checkout_sections} onChange={s("checkout_sections")} />
            </div>
            <div className="border-t border-slate-100 pt-4">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">Cart Page</p>
              <div className="space-y-3">
                <Field label="Cart heading" value={ws.cart_title} onChange={s("cart_title")} testId="ws-cart-title" />
                <Field label="Clear cart button text" value={ws.cart_clear_btn_text} onChange={s("cart_clear_btn_text")} testId="ws-cart-clear-btn" />
              </div>
            </div>
          </div>
        )}
        {authSlide === "checkout_success" && (
          <div className="space-y-4">
            <Field label="Page heading" value={ws.checkout_success_title} onChange={s("checkout_success_title")} testId="ws-cs-title" />
            <Field label="Payment successful message" value={ws.checkout_success_paid_msg} onChange={s("checkout_success_paid_msg")} testId="ws-cs-paid" />
            <Field label="Checking status message" value={ws.checkout_success_pending_msg} onChange={s("checkout_success_pending_msg")} testId="ws-cs-pending" />
            <Field label="Expired / not found message" value={ws.checkout_success_expired_msg} onChange={s("checkout_success_expired_msg")} testId="ws-cs-expired" />
            <div className="border-t border-slate-100 pt-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Next Steps Section</p>
              <div className="space-y-3">
                <Field label="Section title" value={ws.checkout_success_next_steps_title} onChange={s("checkout_success_next_steps_title")} testId="ws-cs-next-title" />
                <Field label="Step 1" value={ws.checkout_success_step_1} onChange={s("checkout_success_step_1")} testId="ws-cs-step-1" />
                <Field label="Step 2" value={ws.checkout_success_step_2} onChange={s("checkout_success_step_2")} testId="ws-cs-step-2" />
                <Field label="Step 3" value={ws.checkout_success_step_3} onChange={s("checkout_success_step_3")} testId="ws-cs-step-3" />
                <Field label="Portal link text" value={ws.checkout_portal_link_text} onChange={s("checkout_portal_link_text")} testId="ws-cs-portal-link" />
              </div>
            </div>
            <div className="border-t border-slate-100 pt-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Bank Transfer Instructions</p>
              <div className="space-y-3">
                <Field label="Success title" value={ws.bank_success_title} onChange={s("bank_success_title")} testId="ws-bank-success-title" />
                <Field label="Success message" value={ws.bank_success_message} onChange={s("bank_success_message")} multiline testId="ws-bank-success-msg" />
                <Field label="Instructions title" value={ws.bank_instructions_title} onChange={s("bank_instructions_title")} testId="ws-bank-inst-title" />
                <Field label="Instruction 1" value={ws.bank_instruction_1} onChange={s("bank_instruction_1")} testId="ws-bank-inst-1" />
                <Field label="Instruction 2" value={ws.bank_instruction_2} onChange={s("bank_instruction_2")} testId="ws-bank-inst-2" />
                <Field label="Instruction 3" value={ws.bank_instruction_3} onChange={s("bank_instruction_3")} testId="ws-bank-inst-3" />
                <Field label="Next steps title" value={ws.bank_next_steps_title} onChange={s("bank_next_steps_title")} testId="ws-bank-next-title" />
                <Field label="Next step 1" value={ws.bank_next_step_1} onChange={s("bank_next_step_1")} testId="ws-bank-next-1" />
                <Field label="Next step 2" value={ws.bank_next_step_2} onChange={s("bank_next_step_2")} testId="ws-bank-next-2" />
                <Field label="Next step 3" value={ws.bank_next_step_3} onChange={s("bank_next_step_3")} testId="ws-bank-next-3" />
              </div>
            </div>
          </div>
        )}
        {authSlide === "gocardless_callback" && (
          <div className="space-y-4">
            <Field label="Processing title" value={ws.gocardless_processing_title} onChange={s("gocardless_processing_title")} testId="ws-gc-proc-title" />
            <Field label="Processing subtitle" value={ws.gocardless_processing_subtitle} onChange={s("gocardless_processing_subtitle")} testId="ws-gc-proc-sub" />
            <Field label="Success title" value={ws.gocardless_success_title} onChange={s("gocardless_success_title")} testId="ws-gc-succ-title" />
            <Field label="Success message" value={ws.gocardless_success_message} onChange={s("gocardless_success_message")} multiline testId="ws-gc-succ-msg" />
            <Field label="Error title" value={ws.gocardless_error_title} onChange={s("gocardless_error_title")} testId="ws-gc-err-title" />
            <Field label="Error message" value={ws.gocardless_error_message} onChange={s("gocardless_error_message")} multiline testId="ws-gc-err-msg" />
            <Field label="Return button text" value={ws.gocardless_return_btn_text} onChange={s("gocardless_return_btn_text")} testId="ws-gc-return-btn" />
          </div>
        )}
        {authSlide === "checkout_messages" && (
          <div className="space-y-4">
            <Field label="Cart empty message" value={ws.msg_cart_empty} onChange={s("msg_cart_empty")} testId="ws-msg-cart-empty" />
            <Field label="Currency unsupported message" value={ws.msg_currency_unsupported} onChange={s("msg_currency_unsupported")} multiline testId="ws-msg-currency" />
            <Field label="No payment methods message" value={ws.msg_no_payment_methods} onChange={s("msg_no_payment_methods")} multiline testId="ws-msg-no-payment" />
          </div>
        )}
        {authSlide === "footer_basics" && (
          <div className="space-y-4">
            <Field label="Tagline" hint="Short line shown under your brand name" value={ws.footer_tagline} onChange={s("footer_tagline")} testId="ws-footer-tagline" />
            <Field label="Copyright text" hint='e.g. "© 2025 Acme Inc."' value={ws.footer_copyright} onChange={s("footer_copyright")} testId="ws-footer-copyright" />
          </div>
        )}
        {authSlide === "footer_about" && (
          <div className="space-y-4">
            <Field label="Section title" hint='Shown as heading (e.g. "About Us")' value={ws.footer_about_title} onChange={s("footer_about_title")} placeholder="About Us" testId="ws-footer-about-title" />
            <Field label="About us text" value={ws.footer_about_text} onChange={s("footer_about_text")} multiline testId="ws-footer-about-text" />
          </div>
        )}
        {authSlide === "footer_nav" && (
          <div className="space-y-4">
            <Field label="Navigation section title" value={ws.footer_nav_title} onChange={s("footer_nav_title")} placeholder="Navigation" testId="ws-footer-nav-title" />
            <div className="grid grid-cols-3 gap-3">
              <Field label="Store label" value={ws.nav_store_label} onChange={s("nav_store_label")} testId="ws-nav-store" />
              <Field label="Articles label" value={ws.nav_articles_label} onChange={s("nav_articles_label")} testId="ws-nav-articles" />
              <Field label="Portal label" value={ws.nav_portal_label} onChange={s("nav_portal_label")} testId="ws-nav-portal" />
            </div>
          </div>
        )}
        {authSlide === "footer_contact" && (
          <div className="space-y-4">
            <Field label="Contact section title" value={ws.footer_contact_title} onChange={s("footer_contact_title")} placeholder="Contact" testId="ws-footer-contact-title" />
            <Field label="Email" value={ws.contact_email} onChange={s("contact_email")} testId="ws-contact-email" />
            <Field label="Phone" value={ws.contact_phone} onChange={s("contact_phone")} testId="ws-contact-phone" />
            <Field label="Address" value={ws.contact_address} onChange={s("contact_address")} multiline testId="ws-contact-address" />
          </div>
        )}
        {authSlide === "footer_social" && (
          <div className="space-y-4">
            <Field label="Section title" value={ws.footer_social_title} onChange={s("footer_social_title")} placeholder="Follow Us" testId="ws-footer-social-title" />
            <div className="space-y-3">
              <Field label="X / Twitter URL" value={ws.social_twitter} onChange={s("social_twitter")} placeholder="https://x.com/yourhandle" testId="ws-social-twitter" />
              <Field label="LinkedIn URL" value={ws.social_linkedin} onChange={s("social_linkedin")} placeholder="https://linkedin.com/company/..." testId="ws-social-linkedin" />
              <Field label="Facebook URL" value={ws.social_facebook} onChange={s("social_facebook")} placeholder="https://facebook.com/..." testId="ws-social-facebook" />
              <Field label="Instagram URL" value={ws.social_instagram} onChange={s("social_instagram")} placeholder="https://instagram.com/..." testId="ws-social-instagram" />
              <Field label="YouTube URL" value={ws.social_youtube} onChange={s("social_youtube")} placeholder="https://youtube.com/@..." testId="ws-social-youtube" />
            </div>
          </div>
        )}
        {authSlide === "documents_page" && (
          <div className="space-y-4">
            <Field label="Nav tab label" hint='Label shown in the top navigation bar (defaults to "Documents")' value={ws.nav_documents_label} onChange={s("nav_documents_label")} testId="ws-docs-nav-label" />
            <Field label="Page title" hint='Main heading on the Documents page' value={ws.documents_page_title} onChange={s("documents_page_title")} testId="ws-docs-page-title" />
            <Field label="Page subtitle" hint="Description shown below the title" value={ws.documents_page_subtitle} onChange={s("documents_page_subtitle")} multiline testId="ws-docs-page-subtitle" />
            <div className="border-t border-slate-100 pt-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Upload Section</p>
              <div className="space-y-3">
                <Field label="Upload section label" value={ws.documents_page_upload_label} onChange={s("documents_page_upload_label")} testId="ws-docs-upload-label" />
                <Field label="Upload hint text" value={ws.documents_page_upload_hint} onChange={s("documents_page_upload_hint")} multiline testId="ws-docs-upload-hint" />
                <Field label="Empty state text" value={ws.documents_page_empty_text} onChange={s("documents_page_empty_text")} multiline testId="ws-docs-empty-text" />
              </div>
            </div>
          </div>
        )}
        {authSlide === "store_hero" && (
          <div className="space-y-4">
            <Field label="Label" hint='Small badge above title (e.g. "Welcome")' value={ws.hero_label} onChange={s("hero_label")} testId="ws-hero-label" />
            <Field label="Title" value={ws.hero_title} onChange={s("hero_title")} multiline testId="ws-hero-title" />
            <Field label="Subtitle" value={ws.hero_subtitle} onChange={s("hero_subtitle")} multiline testId="ws-hero-subtitle" />
          </div>
        )}
        {authSlide === "articles_hero" && (
          <div className="space-y-4">
            <Field label="Label" hint='Small badge above title (e.g. "Resources")' value={ws.articles_hero_label} onChange={s("articles_hero_label")} testId="ws-articles-hero-label" />
            <Field label="Title" value={ws.articles_hero_title} onChange={s("articles_hero_title")} testId="ws-articles-hero-title" />
            <Field label="Subtitle" value={ws.articles_hero_subtitle} onChange={s("articles_hero_subtitle")} multiline testId="ws-articles-hero-subtitle" />
          </div>
        )}
      </SlideOver>
    </>
  );
}
