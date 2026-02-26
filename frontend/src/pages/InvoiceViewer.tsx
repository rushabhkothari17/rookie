import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Printer, ArrowLeft, Mail, Loader2 } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────
interface InvoiceData {
  invoice_number: string;
  order: any;
  customer: any;
  address: any;
  partner: any;
  invoice_settings: any;
  items: any[];
}

const TEMPLATES = [
  { value: "classic",      label: "Classic" },
  { value: "modern",       label: "Modern" },
  { value: "minimal",      label: "Minimal" },
  { value: "professional", label: "Professional" },
  { value: "branded",      label: "Branded" },
];

// Custom HTML template renderer
function CustomHtmlTemplate({ html, d }: { html: string; d: InvoiceData }) {
  // Simple variable substitution for custom templates
  const o = d.order;
  const rendered = html
    .replace(/{{invoice_number}}/g, d.invoice_number)
    .replace(/{{partner_name}}/g, d.partner.name)
    .replace(/{{customer_name}}/g, d.customer.full_name)
    .replace(/{{customer_email}}/g, d.customer.email)
    .replace(/{{order_number}}/g, o.order_number || "")
    .replace(/{{order_total}}/g, `${o.currency || "USD"} ${(o.total || 0).toFixed(2)}`)
    .replace(/{{order_date}}/g, (o.created_at || "").slice(0, 10))
    .replace(/{{payment_terms}}/g, d.invoice_settings.payment_terms || "")
    .replace(/{{footer_notes}}/g, d.invoice_settings.footer_notes || "");
  return <div dangerouslySetInnerHTML={{ __html: rendered }} />;
}

// ── Shared helpers ─────────────────────────────────────────────────────────────
function fmt(v: number, currency = "USD") { return `${currency} ${v.toFixed(2)}`; }
function dateStr(s?: string) { return s ? s.slice(0, 10) : "—"; }

// ── Classic Template ──────────────────────────────────────────────────────────
function ClassicTemplate({ d }: { d: InvoiceData }) {
  const o = d.order;
  return (
    <div className="bg-white p-12 max-w-3xl mx-auto font-[serif] text-slate-800">
      <div className="flex justify-between items-start mb-10">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">INVOICE</h1>
          <p className="text-sm text-slate-500 mt-1">{d.invoice_number}</p>
        </div>
        <div className="text-right text-sm">
          <p className="font-bold text-lg text-slate-900">{d.partner.name}</p>
          <p className="text-slate-500">{dateStr(o.created_at)}</p>
          <p className="text-slate-500 mt-1">{d.invoice_settings.payment_terms}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-8 mb-10 text-sm">
        <div>
          <p className="text-xs uppercase tracking-wider text-slate-400 mb-2">Bill To</p>
          <p className="font-semibold">{d.customer.full_name}</p>
          {d.customer.company_name && <p>{d.customer.company_name}</p>}
          <p className="text-slate-500">{d.customer.email}</p>
          {d.address.line1 && <p className="text-slate-500">{d.address.line1}</p>}
          {(d.address.city || d.address.region) && <p className="text-slate-500">{[d.address.city, d.address.region, d.address.postal].filter(Boolean).join(", ")}</p>}
          {d.address.country && <p className="text-slate-500">{d.address.country}</p>}
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wider text-slate-400 mb-2">From</p>
          <p className="font-semibold">{d.partner.name}</p>
        </div>
      </div>
      <table className="w-full text-sm mb-8">
        <thead>
          <tr className="border-b-2 border-slate-800">
            <th className="text-left py-2">Description</th>
            <th className="text-right py-2">Qty</th>
            <th className="text-right py-2">Unit Price</th>
            <th className="text-right py-2">Amount</th>
          </tr>
        </thead>
        <tbody>
          {d.items.map((item, i) => (
            <tr key={i} className="border-b border-slate-200">
              <td className="py-2.5">{item.product_name || item.product_id}</td>
              <td className="text-right py-2.5">{item.quantity || 1}</td>
              <td className="text-right py-2.5">{fmt(item.unit_price || item.line_total || 0, o.currency)}</td>
              <td className="text-right py-2.5">{fmt(item.line_total || 0, o.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex justify-end">
        <div className="w-56 text-sm space-y-1.5">
          <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span>{fmt(o.subtotal || 0, o.currency)}</span></div>
          {o.discount_amount > 0 && <div className="flex justify-between text-green-700"><span>Discount</span><span>−{fmt(o.discount_amount, o.currency)}</span></div>}
          {o.fee > 0 && <div className="flex justify-between"><span className="text-slate-500">Processing Fee</span><span>{fmt(o.fee, o.currency)}</span></div>}
          {o.tax_amount > 0 && <div className="flex justify-between"><span className="text-slate-500">{o.tax_name || "Tax"}</span><span>{fmt(o.tax_amount, o.currency)}</span></div>}
          <div className="flex justify-between font-bold text-base border-t border-slate-800 pt-2 mt-2"><span>Total</span><span>{fmt(o.total || 0, o.currency)}</span></div>
        </div>
      </div>
      {d.invoice_settings.footer_notes && <p className="mt-10 text-xs text-slate-400 border-t pt-4">{d.invoice_settings.footer_notes}</p>}
    </div>
  );
}

// ── Modern Template ───────────────────────────────────────────────────────────
function ModernTemplate({ d }: { d: InvoiceData }) {
  const o = d.order;
  return (
    <div className="bg-white max-w-3xl mx-auto font-sans text-slate-800">
      <div className="bg-slate-900 text-white px-10 py-8 flex justify-between items-center">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400 mb-1">Invoice</p>
          <h1 className="text-2xl font-bold">{d.partner.name}</h1>
        </div>
        <div className="text-right">
          <p className="text-2xl font-light">{d.invoice_number}</p>
          <p className="text-slate-400 text-sm mt-1">{dateStr(o.created_at)}</p>
        </div>
      </div>
      <div className="px-10 py-8">
        <div className="grid grid-cols-2 gap-8 mb-8">
          <div className="bg-slate-50 rounded-xl p-5 text-sm">
            <p className="text-xs uppercase tracking-wider text-slate-400 mb-3">Bill To</p>
            <p className="font-bold text-slate-900">{d.customer.full_name}</p>
            {d.customer.company_name && <p className="text-slate-600">{d.customer.company_name}</p>}
            <p className="text-slate-500 mt-1">{d.customer.email}</p>
            {d.address.line1 && <p className="text-slate-500">{d.address.line1}, {d.address.city}</p>}
          </div>
          <div className="bg-slate-50 rounded-xl p-5 text-sm">
            <p className="text-xs uppercase tracking-wider text-slate-400 mb-3">Payment Terms</p>
            <p className="font-bold text-slate-900">{d.invoice_settings.payment_terms}</p>
            <p className="text-slate-500 mt-2">Status: <span className={`font-semibold ${o.status === "paid" ? "text-green-600" : "text-orange-600"}`}>{o.status}</span></p>
          </div>
        </div>
        <table className="w-full text-sm mb-8">
          <thead>
            <tr className="bg-slate-900 text-white">
              <th className="text-left px-4 py-2.5 rounded-tl-lg">Description</th>
              <th className="text-right px-4 py-2.5">Qty</th>
              <th className="text-right px-4 py-2.5">Rate</th>
              <th className="text-right px-4 py-2.5 rounded-tr-lg">Amount</th>
            </tr>
          </thead>
          <tbody>
            {d.items.map((item, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                <td className="px-4 py-3">{item.product_name || item.product_id}</td>
                <td className="px-4 py-3 text-right">{item.quantity || 1}</td>
                <td className="px-4 py-3 text-right">{fmt(item.unit_price || item.line_total || 0, o.currency)}</td>
                <td className="px-4 py-3 text-right font-medium">{fmt(item.line_total || 0, o.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex justify-end">
          <div className="w-60 text-sm space-y-1.5">
            <div className="flex justify-between py-1"><span className="text-slate-500">Subtotal</span><span>{fmt(o.subtotal || 0, o.currency)}</span></div>
            {o.discount_amount > 0 && <div className="flex justify-between py-1 text-green-700"><span>Discount</span><span>−{fmt(o.discount_amount, o.currency)}</span></div>}
            {o.fee > 0 && <div className="flex justify-between py-1"><span className="text-slate-500">Processing Fee</span><span>{fmt(o.fee, o.currency)}</span></div>}
            {o.tax_amount > 0 && <div className="flex justify-between py-1"><span className="text-slate-500">{o.tax_name || "Tax"}</span><span>{fmt(o.tax_amount, o.currency)}</span></div>}
            <div className="flex justify-between font-bold text-base bg-slate-900 text-white px-3 py-2.5 rounded-lg mt-2"><span>Total Due</span><span>{fmt(o.total || 0, o.currency)}</span></div>
          </div>
        </div>
        {d.invoice_settings.footer_notes && <p className="mt-8 text-xs text-slate-400 border-t pt-4">{d.invoice_settings.footer_notes}</p>}
      </div>
    </div>
  );
}

// ── Minimal Template ──────────────────────────────────────────────────────────
function MinimalTemplate({ d }: { d: InvoiceData }) {
  const o = d.order;
  return (
    <div className="bg-white p-16 max-w-2xl mx-auto font-sans text-slate-700">
      <div className="mb-16">
        <p className="text-3xl font-light text-slate-900">{d.invoice_number}</p>
        <p className="text-sm text-slate-400 mt-1">{dateStr(o.created_at)} · {d.partner.name}</p>
      </div>
      <div className="flex justify-between mb-12 text-sm">
        <div>
          <p className="font-semibold text-slate-900">{d.customer.full_name}</p>
          {d.customer.company_name && <p className="text-slate-500">{d.customer.company_name}</p>}
          <p className="text-slate-400">{d.customer.email}</p>
        </div>
        <div className="text-right">
          <p className="text-slate-400">{d.invoice_settings.payment_terms}</p>
        </div>
      </div>
      <div className="space-y-3 mb-12">
        {d.items.map((item, i) => (
          <div key={i} className="flex justify-between text-sm border-b border-slate-100 pb-3">
            <span>{item.product_name || item.product_id}</span>
            <span className="font-medium">{fmt(item.line_total || 0, o.currency)}</span>
          </div>
        ))}
      </div>
      <div className="space-y-2 text-sm ml-auto w-52">
        {o.discount_amount > 0 && <div className="flex justify-between text-green-600"><span>Discount</span><span>−{fmt(o.discount_amount, o.currency)}</span></div>}
        {o.fee > 0 && <div className="flex justify-between text-slate-400"><span>Fee</span><span>{fmt(o.fee, o.currency)}</span></div>}
        {o.tax_amount > 0 && <div className="flex justify-between text-slate-500"><span>{o.tax_name || "Tax"}</span><span>{fmt(o.tax_amount, o.currency)}</span></div>}
        <div className="flex justify-between text-lg font-semibold text-slate-900 pt-3 border-t"><span>Total</span><span>{fmt(o.total || 0, o.currency)}</span></div>
      </div>
      {d.invoice_settings.footer_notes && <p className="mt-16 text-xs text-slate-300">{d.invoice_settings.footer_notes}</p>}
    </div>
  );
}

// ── Professional Template ─────────────────────────────────────────────────────
function ProfessionalTemplate({ d }: { d: InvoiceData }) {
  const o = d.order;
  return (
    <div className="bg-white max-w-3xl mx-auto font-sans">
      <div className="bg-slate-800 px-8 py-6 flex justify-between items-start">
        <div>
          <p className="text-white font-bold text-xl">{d.partner.name}</p>
          <p className="text-slate-400 text-xs mt-1 uppercase tracking-widest">Invoice</p>
        </div>
        <div className="text-right">
          <p className="text-white font-mono text-sm">{d.invoice_number}</p>
          <p className="text-slate-400 text-xs mt-1">{dateStr(o.created_at)}</p>
        </div>
      </div>
      <div className="border border-slate-200 border-t-0">
        <div className="grid grid-cols-2 divide-x divide-slate-200 border-b border-slate-200">
          <div className="px-6 py-4 text-sm">
            <p className="text-xs font-bold uppercase text-slate-400 mb-2">Billed To</p>
            <p className="font-semibold text-slate-900">{d.customer.full_name}</p>
            {d.customer.company_name && <p className="text-slate-600">{d.customer.company_name}</p>}
            <p className="text-slate-500">{d.customer.email}</p>
            {d.address.line1 && <p className="text-slate-400 text-xs mt-1">{d.address.line1}, {[d.address.city, d.address.region, d.address.country].filter(Boolean).join(", ")}</p>}
          </div>
          <div className="px-6 py-4 text-sm">
            <p className="text-xs font-bold uppercase text-slate-400 mb-2">Details</p>
            <div className="space-y-1">
              <div className="flex justify-between"><span className="text-slate-500">Terms:</span><span className="font-medium">{d.invoice_settings.payment_terms}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Status:</span><span className={`font-medium ${o.status === "paid" ? "text-green-600" : "text-orange-600"}`}>{o.status}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Order #:</span><span className="font-mono text-xs">{o.order_number}</span></div>
            </div>
          </div>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr className="border-b border-slate-200">
              <th className="text-left px-6 py-2.5 text-xs font-bold text-slate-500 uppercase">Item</th>
              <th className="text-right px-4 py-2.5 text-xs font-bold text-slate-500 uppercase">Qty</th>
              <th className="text-right px-4 py-2.5 text-xs font-bold text-slate-500 uppercase">Rate</th>
              <th className="text-right px-6 py-2.5 text-xs font-bold text-slate-500 uppercase">Total</th>
            </tr>
          </thead>
          <tbody>
            {d.items.map((item, i) => (
              <tr key={i} className="border-b border-slate-100">
                <td className="px-6 py-3">{item.product_name || item.product_id}</td>
                <td className="px-4 py-3 text-right">{item.quantity || 1}</td>
                <td className="px-4 py-3 text-right">{fmt(item.unit_price || item.line_total || 0, o.currency)}</td>
                <td className="px-6 py-3 text-right font-medium">{fmt(item.line_total || 0, o.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex justify-end border-t border-slate-200 bg-slate-50">
          <div className="w-64 p-6 text-sm space-y-1.5">
            <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span>{fmt(o.subtotal || 0, o.currency)}</span></div>
            {o.discount_amount > 0 && <div className="flex justify-between text-green-600"><span>Discount</span><span>−{fmt(o.discount_amount, o.currency)}</span></div>}
            {o.fee > 0 && <div className="flex justify-between"><span className="text-slate-500">Fee</span><span>{fmt(o.fee, o.currency)}</span></div>}
            {o.tax_amount > 0 && <div className="flex justify-between"><span className="text-slate-500">{o.tax_name || "Tax"}</span><span>{fmt(o.tax_amount, o.currency)}</span></div>}
            <div className="flex justify-between font-bold text-base pt-2 border-t border-slate-300"><span>Total</span><span>{fmt(o.total || 0, o.currency)}</span></div>
          </div>
        </div>
        {d.invoice_settings.footer_notes && <div className="px-6 py-4 border-t border-slate-200 text-xs text-slate-400">{d.invoice_settings.footer_notes}</div>}
      </div>
    </div>
  );
}

// ── Branded Template ──────────────────────────────────────────────────────────
function BrandedTemplate({ d }: { d: InvoiceData }) {
  const o = d.order;
  return (
    <div className="bg-white max-w-3xl mx-auto font-sans">
      <div className="h-2 bg-gradient-to-r from-slate-800 via-slate-600 to-slate-400" />
      <div className="px-10 py-8">
        <div className="flex justify-between items-start mb-10">
          <div>
            <div className="h-12 w-12 rounded-xl bg-slate-900 flex items-center justify-center mb-3">
              <span className="text-white font-bold text-xl">{d.partner.name[0]}</span>
            </div>
            <p className="font-bold text-xl text-slate-900">{d.partner.name}</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-light text-slate-300">Invoice</p>
            <p className="text-slate-700 font-mono text-sm mt-1">{d.invoice_number}</p>
            <p className="text-slate-400 text-xs">{dateStr(o.created_at)}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-6 mb-8">
          <div className="rounded-xl border border-slate-100 bg-slate-50 p-5 text-sm">
            <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Bill To</p>
            <p className="font-semibold text-slate-900 text-base">{d.customer.full_name}</p>
            {d.customer.company_name && <p className="text-slate-600">{d.customer.company_name}</p>}
            <p className="text-slate-500 text-xs mt-1">{d.customer.email}</p>
            {d.address.line1 && <p className="text-slate-400 text-xs">{d.address.line1}</p>}
            {d.address.city && <p className="text-slate-400 text-xs">{[d.address.city, d.address.region, d.address.country].filter(Boolean).join(", ")}</p>}
          </div>
          <div className="rounded-xl bg-slate-900 text-white p-5 text-sm">
            <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Summary</p>
            <p className="text-2xl font-bold">{fmt(o.total || 0, o.currency)}</p>
            <p className="text-slate-400 text-xs mt-1">{d.invoice_settings.payment_terms}</p>
            <p className={`text-xs mt-2 font-semibold ${o.status === "paid" ? "text-green-400" : "text-orange-400"}`}>
              Status: {o.status?.toUpperCase()}
            </p>
          </div>
        </div>
        <div className="rounded-xl border border-slate-100 overflow-hidden mb-8">
          <table className="w-full text-sm">
            <thead className="bg-slate-900 text-white">
              <tr>
                <th className="text-left px-5 py-3">Description</th>
                <th className="text-right px-4 py-3">Qty</th>
                <th className="text-right px-4 py-3">Rate</th>
                <th className="text-right px-5 py-3">Total</th>
              </tr>
            </thead>
            <tbody>
              {d.items.map((item, i) => (
                <tr key={i} className={`border-t border-slate-100 ${i % 2 === 0 ? "" : "bg-slate-50"}`}>
                  <td className="px-5 py-3">{item.product_name || item.product_id}</td>
                  <td className="px-4 py-3 text-right text-slate-500">{item.quantity || 1}</td>
                  <td className="px-4 py-3 text-right text-slate-500">{fmt(item.unit_price || item.line_total || 0, o.currency)}</td>
                  <td className="px-5 py-3 text-right font-semibold">{fmt(item.line_total || 0, o.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex justify-end">
          <div className="w-64 text-sm space-y-1.5">
            <div className="flex justify-between text-slate-500"><span>Subtotal</span><span>{fmt(o.subtotal || 0, o.currency)}</span></div>
            {o.discount_amount > 0 && <div className="flex justify-between text-green-600"><span>Discount</span><span>−{fmt(o.discount_amount, o.currency)}</span></div>}
            {o.fee > 0 && <div className="flex justify-between text-slate-500"><span>Fee</span><span>{fmt(o.fee, o.currency)}</span></div>}
            {o.tax_amount > 0 && <div className="flex justify-between text-slate-500"><span>{o.tax_name || "Tax"}</span><span>{fmt(o.tax_amount, o.currency)}</span></div>}
            <div className="flex justify-between font-bold text-base bg-slate-900 text-white px-4 py-2.5 rounded-lg mt-2"><span>Total</span><span>{fmt(o.total || 0, o.currency)}</span></div>
          </div>
        </div>
        {d.invoice_settings.footer_notes && <p className="mt-8 text-xs text-slate-400 border-t pt-4">{d.invoice_settings.footer_notes}</p>}
      </div>
      <div className="h-1 bg-gradient-to-r from-slate-400 via-slate-600 to-slate-800" />
    </div>
  );
}

const TEMPLATE_MAP: Record<string, React.ComponentType<{ d: InvoiceData }>> = {
  classic: ClassicTemplate,
  modern: ModernTemplate,
  minimal: MinimalTemplate,
  professional: ProfessionalTemplate,
  branded: BrandedTemplate,
};

// ── Main InvoiceViewer Page ───────────────────────────────────────────────────
export default function InvoiceViewer() {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<InvoiceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [template, setTemplate] = useState("classic");
  const [customTemplates, setCustomTemplates] = useState<any[]>([]);
  const [sendingEmail, setSendingEmail] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!orderId) return;
    api.get(`/orders/${orderId}/invoice`)
      .then(r => {
        setData(r.data);
        setTemplate(r.data.invoice_settings?.template || "classic");
      })
      .catch(() => setError("Failed to load invoice. Make sure you have access to this order."))
      .finally(() => setLoading(false));

    // Try to load partner custom templates (admin only)
    api.get("/admin/taxes/invoice-templates-for-viewer")
      .then(r => setCustomTemplates(r.data.templates || []))
      .catch(() => {}); // Not available for customers — silently ignore
  }, [orderId]);

  const handlePrint = () => window.print();

  const handleEmailInvoice = async () => {
    if (!orderId) return;
    setSendingEmail(true);
    try {
      const r = await api.post(`/orders/${orderId}/send-invoice`, {});
      toast.success(`Invoice emailed to ${r.data.recipient}`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to send invoice email");
    } finally {
      setSendingEmail(false);
    }
  };

  // Build full template list (defaults + custom)
  const allTemplates = [
    ...TEMPLATES,
    ...customTemplates.map(t => ({ value: `custom:${t.id}`, label: `${t.name} (Custom)` })),
  ];

  // Determine what to render
  const isCustomTemplate = template.startsWith("custom:");
  const customTemplateId = isCustomTemplate ? template.slice("custom:".length) : null;
  const customTemplateData = customTemplates.find(t => t.id === customTemplateId);
  const TemplateComponent = !isCustomTemplate ? (TEMPLATE_MAP[template] || ClassicTemplate) : null;

  return (
    <>
      {/* Print styles — hides controls, shows only invoice */}
      <style>{`
        @media print {
          body * { visibility: hidden; }
          #invoice-printable, #invoice-printable * { visibility: visible; }
          #invoice-printable { position: fixed; left: 0; top: 0; width: 100%; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="min-h-screen bg-slate-100">
        {/* Controls bar */}
        <div className="no-print bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shadow-sm">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 transition-colors"
            data-testid="invoice-back-btn"
          >
            <ArrowLeft size={16} />Back
          </button>
          <div className="flex items-center gap-3">
            <Select value={template} onValueChange={setTemplate}>
              <SelectTrigger className="w-48 h-8 text-sm" data-testid="invoice-template-select">
                <SelectValue placeholder="Template" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="" disabled className="text-xs text-slate-400 font-semibold">— Default Templates —</SelectItem>
                {TEMPLATES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                {customTemplates.length > 0 && (
                  <>
                    <SelectItem value="" disabled className="text-xs text-slate-400 font-semibold">— Custom Templates —</SelectItem>
                    {customTemplates.map(t => (
                      <SelectItem key={`custom:${t.id}`} value={`custom:${t.id}`}>{t.name}</SelectItem>
                    ))}
                  </>
                )}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="outline"
              onClick={handleEmailInvoice}
              disabled={!data || sendingEmail}
              data-testid="invoice-email-btn"
            >
              {sendingEmail ? <Loader2 size={14} className="mr-1.5 animate-spin" /> : <Mail size={14} className="mr-1.5" />}
              {sendingEmail ? "Sending..." : "Email Invoice"}
            </Button>
            <Button size="sm" onClick={handlePrint} disabled={!data} data-testid="invoice-print-btn">
              <Printer size={14} className="mr-1.5" /> Print / Save PDF
            </Button>
          </div>
        </div>

        {/* Invoice content */}
        <div className="py-8 px-4">
          {loading && (
            <div className="text-center text-slate-500 py-20">Loading invoice...</div>
          )}
          {error && (
            <div className="text-center text-red-500 py-20">{error}</div>
          )}
          {data && (
            <div id="invoice-printable" ref={printRef} className="shadow-xl">
              {isCustomTemplate && customTemplateData ? (
                <CustomHtmlTemplate html={customTemplateData.html_body} d={data} />
              ) : TemplateComponent ? (
                <TemplateComponent d={data} />
              ) : null}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
