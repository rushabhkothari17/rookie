import { useState } from "react";
import { ChevronDown, ChevronUp, ChevronsUpDown, Check } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

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
  compact?: boolean;
  /** For filterType="status": override the radio options. Defaults to [[all,All],[active,Active],[inactive,Inactive]] */
  statusOptions?: [string, string][];
  /** For filterType="number-range": show a currency selector above the min/max inputs */
  currencyOptions?: [string, string][];
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
  compact = false,
  statusOptions,
  currencyOptions,
}: ColHeaderProps) {
  const isActive = sortCol === colKey;
  const [dropdownSearch, setDropdownSearch] = useState("");
  const effectiveOptions: [string, string][] =
    statusOptions ?? [["all", "All"], ["active", "Active"], ["inactive", "Inactive"]];

  const filteredDropdownOptions = dropdownSearch
    ? effectiveOptions.filter(([, lbl]) => lbl.toLowerCase().includes(dropdownSearch.toLowerCase()))
    : effectiveOptions;

  const hasFilter =
    filterType === "none" ? false
    : filterType === "text" ? !!filterValue
    : filterType === "status" ? filterValue !== "all" && !!filterValue
    : filterType === "dropdown" ? Array.isArray(filterValue) && filterValue.length > 0
    : filterType === "number-range" ? !!(filterValue?.min || filterValue?.max || filterValue?.currency)
    : !!(filterValue?.from || filterValue?.to);

  const SortIcon = isActive ? (sortDir === "asc" ? ChevronUp : ChevronDown) : ChevronsUpDown;

  return (
    <th className={`${compact ? "px-3 py-2" : "px-4 py-3"} text-${align}`}>
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
        <PopoverContent className={`${filterType === "dropdown" ? "w-60" : filterType === "number-range" && currencyOptions ? "w-56" : "w-52"} p-3 space-y-3`} align="start" side="bottom">
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
                {filterType === "dropdown" && (
                  <div>
                    {(Array.isArray(filterValue) && filterValue.length > 0) && (
                      <p className="text-[10px] text-blue-500 font-medium mb-1">{filterValue.length} selected</p>
                    )}
                    <Input
                      className="h-6 text-xs mb-1.5"
                      placeholder="Search…"
                      value={dropdownSearch}
                      onChange={e => setDropdownSearch(e.target.value)}
                    />
                    <div className="max-h-44 overflow-y-auto space-y-0.5 pr-0.5">
                      {filteredDropdownOptions.map(([val, lbl]) => {
                        const selected = Array.isArray(filterValue) && filterValue.includes(val);
                        const toggle = () => {
                          const current: string[] = Array.isArray(filterValue) ? filterValue : [];
                          const next = selected ? current.filter(v => v !== val) : [...current, val];
                          onFilter && onFilter(next);
                        };
                        return (
                          <button
                            key={val}
                            onClick={toggle}
                            className={`w-full flex items-center gap-2 text-xs px-2 py-1.5 rounded text-left hover:bg-slate-100 ${selected ? "bg-slate-50 font-medium text-slate-800" : "text-slate-600"}`}
                          >
                            <span className={`h-3.5 w-3.5 shrink-0 rounded border flex items-center justify-center ${selected ? "bg-blue-500 border-blue-500" : "border-slate-300"}`}>
                              {selected && <Check size={9} className="text-white" strokeWidth={3} />}
                            </span>
                            <span className="truncate">{lbl}</span>
                          </button>
                        );
                      })}
                      {filteredDropdownOptions.length === 0 && (
                        <p className="text-xs text-slate-400 px-2 py-1.5">No results</p>
                      )}
                    </div>
                  </div>
                )}
                {filterType === "number-range" && (
                  <div className="space-y-1.5">
                    {currencyOptions && currencyOptions.length > 0 && (
                      <div>
                        <p className="text-[10px] text-slate-400 mb-0.5">Currency</p>
                        <Select
                          value={filterValue?.currency || "__any__"}
                          onValueChange={val => onFilter && onFilter({ ...filterValue, currency: val === "__any__" ? undefined : val })}
                        >
                          <SelectTrigger className="h-7 text-xs w-full">
                            <SelectValue placeholder="Any currency" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__any__">Any currency</SelectItem>
                            {currencyOptions.map(([val, lbl]) => (
                              <SelectItem key={val} value={val}>{lbl}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
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
