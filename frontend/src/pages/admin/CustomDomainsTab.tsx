/**
 * Custom Domains Tab - Wrapper for CustomDomainsSection as a standalone tab
 */
import { CustomDomainsSection } from "@/components/admin/CustomDomainsSection";

export function CustomDomainsTab() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Custom Domains</h2>
          <p className="text-sm text-slate-500">Configure custom domains for your store</p>
        </div>
      </div>
      <CustomDomainsSection />
    </div>
  );
}
