import { Check, X } from "lucide-react";

export default function IncludedList({
  items,
  testId,
  variant = "included",
}: {
  items: string[];
  testId: string;
  variant?: "included" | "excluded";
}) {
  return (
    <ul className="space-y-2.5" data-testid={testId}>
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2.5">
          {variant === "included" ? (
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-500" />
          ) : (
            <X className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
          )}
          <span className="leading-relaxed">{item}</span>
        </li>
      ))}
    </ul>
  );
}
