import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";

export type SortDirection = "asc" | "desc";

export type ColHeaderProps = {
  label: string;
  colKey: string;
  sortCol?: string;
  sortDir?: SortDirection;
  onSort: (col: string, dir: SortDirection) => void;
  onClearSort: () => void;
  filterType: "text" | "number-range" | "status" | "date-range" | "dropdown" | "none";
  filterValue?: any;
  onFilter?: (val: any) => void;
  onClearFilter?: () => void;
  align?: "left" | "right";
  /** For filterType="status": override the radio options. Defaults to [[all,All],[active,Active],[inactive,Inactive]] */
  statusOptions?: [string, string][];
};

function sortLabel(dir: SortDirection, filterType: string) {
  if (filterType === "number-range") return dir === "asc" ? "Low → High" : "High → Low";
  if (filterType === "date-range") return dir === "asc" ? "Oldest first" : "Newest first";
  return dir === "asc" ? "A → Z" : "Z → A";
}

export function ColHeader({
  label, colKey, sortCol, sortDir, onSort, onClearSort,
  filterType, filterValue, onFilter, onClearFilter,
  align = "left",
  statusOptions,
}: ColHeaderProps) {
  const isActive = sortCol === colKey;
  const effectiveOptions: [string, string][] =
    statusOptions ?? [["all", "All"], ["active", "Active"], ["inactive", "Inactive"]];

  const hasFilter =
    filterType === "none" ? false
    : filterType === "text" ? !!filterValue
    : filterType === "status" ? filterValue !== "all" && !!filterValue
    : filterType === "number-range" ? !!(filterValue?.min || filterValue?.max)
    : !!(filterValue?.from || filterValue?.to);

  const SortIcon = isActive ? (sortDir === "asc" ? ChevronUp : ChevronDown) : ChevronsUpDown;

  return (
    <th className={`px-4 py-3 text-${align}`}>
      <Popover>
        <PopoverTrigger asChild>
          <button className="flex items-center gap-1 text-xs font-medium uppercase text-slate-500 hover:text-slate-700 group">
            {label}
            <span className="relative inline-flex">
              <SortIcon size={12} className={isActive ? "text-slate-700" : "text-slate-400 group-hover:text-slate-600"} />
              {hasFilter && <span className="absolute -top-1 -right-1 h-1.5 w-1.5 rounded-full bg-blue-500" />}
            </span>
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-52 p-3 space-y-3" align="start" side="bottom">
          <div>
            <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1.5">Sort</p>
            <div className="flex flex-col gap-0.5">
              <button
                onClick={() => isActive && sortDir === "asc" ? onClearSort() : onSort(colKey, "asc")}
                className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded hover:bg-slate-100 ${isActive && sortDir === "asc" ? "bg-slate-100 font-semibold text-slate-800" : "text-slate-600"}`}
              >
                <ChevronUp size={12} /> {sortLabel("asc", filterType)}
              </button>
              <button
                onClick={() => isActive && sortDir === "desc" ? onClearSort() : onSort(colKey, "desc")}
                className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded hover:bg-slate-100 ${isActive && sortDir === "desc" ? "bg-slate-100 font-semibold text-slate-800" : "text-slate-600"}`}
              >
                <ChevronDown size={12} /> {sortLabel("desc", filterType)}
              </button>
            </div>
          </div>
          {filterType !== "none" && (
            <>
              <hr className="border-slate-100" />
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase">Filter</p>
                  {hasFilter && onClearFilter && (
                    <button onClick={onClearFilter} className="text-[10px] text-blue-500 hover:underline">Clear</button>
                  )}
                </div>
                {filterType === "text" && (
                  <Input className="h-7 text-xs" placeholder="Search…" value={filterValue || ""} onChange={e => onFilter && onFilter(e.target.value)} />
                )}
                {filterType === "status" && (
                  <div className="space-y-1">
                    {effectiveOptions.map(([val, lbl]) => (
                      <label key={val} className="flex items-center gap-2 cursor-pointer">
                        <input type="radio" className="h-3.5 w-3.5" checked={filterValue === val} onChange={() => onFilter && onFilter(val)} />
                        <span className="text-xs text-slate-700">{lbl}</span>
                      </label>
                    ))}
                  </div>
                )}
                {filterType === "number-range" && (
                  <div className="space-y-1.5">
                    <Input className="h-7 text-xs" type="number" placeholder="Min" value={filterValue?.min || ""} onChange={e => onFilter && onFilter({ ...filterValue, min: e.target.value })} />
                    <Input className="h-7 text-xs" type="number" placeholder="Max" value={filterValue?.max || ""} onChange={e => onFilter && onFilter({ ...filterValue, max: e.target.value })} />
                  </div>
                )}
                {filterType === "date-range" && (
                  <div className="space-y-1.5">
                    <div>
                      <p className="text-[10px] text-slate-400 mb-0.5">From</p>
                      <Input className="h-7 text-xs" type="date" value={filterValue?.from || ""} onChange={e => onFilter && onFilter({ ...filterValue, from: e.target.value })} />
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 mb-0.5">To</p>
                      <Input className="h-7 text-xs" type="date" value={filterValue?.to || ""} onChange={e => onFilter && onFilter({ ...filterValue, to: e.target.value })} />
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </PopoverContent>
      </Popover>
    </th>
  );
}
