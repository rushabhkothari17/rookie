import { Check } from "lucide-react";

export default function IncludedList({
  items,
  testId,
}: {
  items: string[];
  testId: string;
}) {
  return (
    <ul className="space-y-2" data-testid={testId}>
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2">
          <Check className="mt-0.5 h-4 w-4 text-emerald-500" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
