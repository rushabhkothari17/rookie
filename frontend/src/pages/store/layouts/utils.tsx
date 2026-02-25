import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import api from "@/lib/api";
import type { IntakeQuestion } from "./types";

// Evaluate visibility rules
export function evaluateVisibilityRule(rule: any, answers: Record<string, any>): boolean {
  if (!rule) return true;
  const { depends_on, operator, value } = rule;
  const answer = answers[depends_on];
  switch (operator) {
    case "equals": return String(answer ?? "") === String(value ?? "");
    case "not_equals": return String(answer ?? "") !== String(value ?? "");
    case "greater_than": return parseFloat(answer) > parseFloat(value);
    case "less_than": return parseFloat(answer) < parseFloat(value);
    case "contains": return Array.isArray(answer) ? answer.includes(value) : String(answer ?? "").includes(value);
    case "not_empty": return !!answer && answer !== "" && !(Array.isArray(answer) && answer.length === 0);
    default: return true;
  }
}

// Get enabled intake questions from schema
export function getEnabledIntakeQuestions(schema: any): IntakeQuestion[] {
  if (!schema?.questions) return [];
  const questions = schema.questions;

  // New flat array format
  if (Array.isArray(questions)) {
    return questions
      .filter((q: any) => q.enabled !== false)
      .sort((a: any, b: any) => (a.order ?? 0) - (b.order ?? 0));
  }

  // Legacy grouped format
  const result: IntakeQuestion[] = [];
  for (const qtype of ["dropdown", "multiselect", "single_line", "multi_line"]) {
    const qs = (questions[qtype] || [])
      .filter((q: any) => q.enabled)
      .sort((a: any, b: any) => (a.order ?? 0) - (b.order ?? 0));
    result.push(...qs.map((q: any) => ({ ...q, type: qtype })));
  }
  return result;
}

// Question label with optional tooltip
export function QuestionLabel({ q }: { q: IntakeQuestion }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-sm font-medium text-slate-700">
        {q.label}
        {q.required && <span className="text-red-500 ml-1">*</span>}
      </span>
      {q.tooltip_text && (
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-slate-400 hover:text-slate-600 cursor-help">
                <Info size={14} />
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs text-xs">
              {q.tooltip_text}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}

// Render intake field based on type
export function renderIntakeField(
  q: IntakeQuestion,
  value: any,
  onChange: (v: any) => void
) {
  const qtype = q.type;

  // HTML blocks are content dividers, not form fields
  if (qtype === "html_block") {
    return (
      <div className="py-1">
        {q.label && <h3 className="text-base font-semibold text-slate-800 mb-2">{q.label}</h3>}
        {q.content && (
          <div
            className="text-sm text-slate-600 prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: q.content }}
          />
        )}
      </div>
    );
  }

  if (qtype === "boolean") {
    return (
      <div className="flex gap-4" data-testid={`intake-${q.key}`}>
        {[{ label: "Yes", value: "yes" }, { label: "No", value: "no" }].map(opt => (
          <label key={opt.value} className="flex items-center gap-2 text-sm cursor-pointer select-none">
            <input
              type="radio"
              name={`boolean-${q.key}`}
              checked={String(value ?? "") === opt.value}
              onChange={() => onChange(opt.value)}
              className="accent-[#0f172a]"
            />
            {opt.label}
          </label>
        ))}
      </div>
    );
  }

  if (qtype === "date") {
    if (q.date_format === "date_range") {
      const dateVal = typeof value === "object" ? value : { from: "", to: "" };
      return (
        <div className="flex items-center gap-3" data-testid={`intake-${q.key}`}>
          <Input
            type="date"
            value={dateVal.from || ""}
            onChange={e => onChange({ ...dateVal, from: e.target.value })}
            className="flex-1"
          />
          <span className="text-slate-400 text-sm">to</span>
          <Input
            type="date"
            value={dateVal.to || ""}
            onChange={e => onChange({ ...dateVal, to: e.target.value })}
            className="flex-1"
          />
        </div>
      );
    }
    return (
      <Input
        type="date"
        value={value || ""}
        onChange={e => onChange(e.target.value)}
        data-testid={`intake-${q.key}`}
      />
    );
  }

  if (qtype === "file") {
    const uploaded = typeof value === "object" && value?.filename;
    return (
      <div data-testid={`intake-${q.key}`}>
        {uploaded && (
          <div className="flex items-center gap-2 text-sm text-slate-600 mb-2 p-2 bg-slate-50 rounded border border-slate-200">
            <span className="text-green-600">&#10003;</span> {value.filename}
            <button
              type="button"
              className="ml-auto text-slate-400 hover:text-red-500"
              onClick={() => onChange(null)}
            >
              Remove
            </button>
          </div>
        )}
        <input
          type="file"
          accept={q.accept || "*"}
          className="text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border file:border-slate-200 file:text-xs file:font-medium file:text-slate-700 file:bg-slate-50 hover:file:bg-slate-100"
          onChange={async e => {
            const file = e.target.files?.[0];
            if (!file) return;
            const maxBytes = (q.max_size_mb || 10) * 1024 * 1024;
            if (file.size > maxBytes) {
              alert(`File too large (max ${q.max_size_mb || 10} MB)`);
              return;
            }
            try {
              const formData = new FormData();
              formData.append("file", file);
              const res = await api.post("/uploads", formData, {
                headers: { "Content-Type": "multipart/form-data" }
              });
              onChange(res.data);
            } catch {
              alert("Upload failed. Please try again.");
            }
          }}
        />
        <p className="text-[10px] text-slate-400 mt-1">
          Files are stored temporarily for 24 hours
        </p>
      </div>
    );
  }

  if (qtype === "formula") {
    return (
      <div
        className="h-9 flex items-center px-3 rounded-md border border-slate-200 bg-slate-50 text-sm text-slate-500 italic"
        data-testid={`intake-${q.key}`}
      >
        Automatically calculated from other inputs
      </div>
    );
  }

  if (qtype === "number") {
    return (
      <Input
        type="number"
        min={q.min ?? 0}
        max={q.max}
        step={q.step ?? 1}
        value={value ?? (q.default_value ?? q.min ?? 0)}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        placeholder={q.helper_text || "Enter a number"}
        data-testid={`intake-${q.key}`}
      />
    );
  }

  if (qtype === "dropdown") {
    return (
      <Select value={value || ""} onValueChange={onChange}>
        <SelectTrigger data-testid={`intake-${q.key}`}>
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent>
          {(q.options || []).map(opt => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }

  if (qtype === "multiselect") {
    const selected: string[] = Array.isArray(value) ? value : [];
    return (
      <div className="space-y-2" data-testid={`intake-${q.key}`}>
        {(q.options || []).map(opt => (
          <label key={opt.value} className="flex items-center gap-2 text-sm cursor-pointer">
            <Checkbox
              checked={selected.includes(opt.value)}
              onCheckedChange={checked =>
                onChange(
                  checked
                    ? [...selected, opt.value]
                    : selected.filter(v => v !== opt.value)
                )
              }
            />
            {opt.label}
          </label>
        ))}
      </div>
    );
  }

  if (qtype === "multi_line") {
    return (
      <Textarea
        value={value || ""}
        onChange={e => onChange(e.target.value)}
        placeholder={q.helper_text || ""}
        rows={3}
        data-testid={`intake-${q.key}`}
      />
    );
  }

  // single_line default
  return (
    <Input
      value={value || ""}
      onChange={e => onChange(e.target.value)}
      placeholder={q.helper_text || ""}
      data-testid={`intake-${q.key}`}
    />
  );
}
