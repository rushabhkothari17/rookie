import { SettingRow } from "./websiteTabShared";

interface Props {
  structured: Record<string, any[]>;
  onStructuredSaved: (key: string, val: any) => void;
}

export function SysConfigSection({ structured, onStructuredSaved }: Props) {
  const operationsItems = structured["Operations"] || [];
  const featureFlagItems = structured["FeatureFlags"] || [];

  return (
    <>
      <h3 className="text-sm font-semibold text-slate-700 mb-1">System Configuration</h3>
      <p className="text-xs text-slate-400 mb-4">Configure global settings for your partner account.</p>

      {operationsItems.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
          <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">Operations</h4>
          {operationsItems.map((item: any) => (
            <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />
          ))}
        </div>
      )}

      {featureFlagItems.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
          <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">Feature Flags</h4>
          {featureFlagItems.map((item: any) => (
            <SettingRow key={item.key} item={item} onSaved={onStructuredSaved} />
          ))}
        </div>
      )}
    </>
  );
}
