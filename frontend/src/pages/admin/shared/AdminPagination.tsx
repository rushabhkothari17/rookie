import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface AdminPaginationProps {
  page: number;
  totalPages: number;
  total: number;
  perPage: number;
  onPage: (p: number) => void;
}

export function AdminPagination({ page, totalPages, total, perPage, onPage }: AdminPaginationProps) {
  if (total <= perPage && totalPages <= 1) return null;
  const from = (page - 1) * perPage + 1;
  const to = Math.min(page * perPage, total);
  return (
    <div className="flex items-center justify-between pt-3 border-t border-slate-100 mt-2">
      <span className="text-xs text-slate-500">{from}–{to} of {total}</span>
      <div className="flex items-center gap-1">
        <Button size="sm" variant="outline" className="h-7 w-7 p-0" onClick={() => onPage(page - 1)} disabled={page <= 1}>
          <ChevronLeft size={14} />
        </Button>
        <span className="text-xs text-slate-600 px-2">Page {page} of {totalPages}</span>
        <Button size="sm" variant="outline" className="h-7 w-7 p-0" onClick={() => onPage(page + 1)} disabled={page >= totalPages}>
          <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  );
}
