/** Shared section types, icon registry, and colour palette used by
 *  admin SectionsEditor and customer ProductDetail. */
import {
  CheckCircle2, XCircle, Info, Star, Clock, Zap, Target, Users, Shield,
  Lightbulb, BookOpen, ListChecks, ArrowRight, AlertTriangle, Wrench,
  BarChart2, Gift, Heart, FileText, Rocket,
} from "lucide-react";
import { ComponentType } from "react";

export interface CustomSection {
  id: string;
  name: string;
  type: "bullets" | "paragraph" | "steps";
  content: string | string[];
  icon: string;
  icon_color: string;
  icon_style: "filled" | "outline" | "ghost";
  tags: string[];
  enabled: boolean;
  order: number;
}

export interface SectionIconDef {
  name: string;
  label: string;
  Icon: ComponentType<{ size?: number; className?: string }>;
}

export const SECTION_ICONS: SectionIconDef[] = [
  { name: "check",   label: "Checkmark",  Icon: CheckCircle2 },
  { name: "x-circle",label: "Exclude",    Icon: XCircle },
  { name: "info",    label: "Info",       Icon: Info },
  { name: "star",    label: "Star",       Icon: Star },
  { name: "clock",   label: "Clock",      Icon: Clock },
  { name: "zap",     label: "Lightning",  Icon: Zap },
  { name: "target",  label: "Target",     Icon: Target },
  { name: "users",   label: "Team",       Icon: Users },
  { name: "shield",  label: "Shield",     Icon: Shield },
  { name: "lightbulb",label:"Idea",       Icon: Lightbulb },
  { name: "book",    label: "Guide",      Icon: BookOpen },
  { name: "list",    label: "Checklist",  Icon: ListChecks },
  { name: "arrow",   label: "Next Steps", Icon: ArrowRight },
  { name: "alert",   label: "Warning",    Icon: AlertTriangle },
  { name: "wrench",  label: "Technical",  Icon: Wrench },
  { name: "chart",   label: "Metrics",    Icon: BarChart2 },
  { name: "gift",    label: "Bonus",      Icon: Gift },
  { name: "heart",   label: "Support",    Icon: Heart },
  { name: "file",    label: "Document",   Icon: FileText },
  { name: "rocket",  label: "Launch",     Icon: Rocket },
];

export const ICON_MAP: Record<string, ComponentType<{ size?: number; className?: string }>> =
  Object.fromEntries(SECTION_ICONS.map((i) => [i.name, i.Icon]));

export interface SectionColorDef {
  name: string;
  label: string;
  bg: string;
  text: string;
  ring: string;
  border: string;
}

export const SECTION_COLORS: SectionColorDef[] = [
  { name: "slate",  label: "Default", bg: "bg-slate-100",  text: "text-slate-600",  ring: "ring-slate-300",  border: "border-slate-200" },
  { name: "blue",   label: "Blue",    bg: "bg-blue-50",    text: "text-blue-600",   ring: "ring-blue-200",   border: "border-blue-100" },
  { name: "green",  label: "Green",   bg: "bg-green-50",   text: "text-green-700",  ring: "ring-green-200",  border: "border-green-100" },
  { name: "red",    label: "Red",     bg: "bg-red-50",     text: "text-red-600",    ring: "ring-red-200",    border: "border-red-100" },
  { name: "amber",  label: "Amber",   bg: "bg-amber-50",   text: "text-amber-700",  ring: "ring-amber-200",  border: "border-amber-100" },
  { name: "purple", label: "Purple",  bg: "bg-purple-50",  text: "text-purple-600", ring: "ring-purple-200", border: "border-purple-100" },
  { name: "pink",   label: "Pink",    bg: "bg-pink-50",    text: "text-pink-600",   ring: "ring-pink-200",   border: "border-pink-100" },
  { name: "cyan",   label: "Cyan",    bg: "bg-cyan-50",    text: "text-cyan-600",   ring: "ring-cyan-200",   border: "border-cyan-100" },
  { name: "orange", label: "Orange",  bg: "bg-orange-50",  text: "text-orange-600", ring: "ring-orange-200", border: "border-orange-100" },
  { name: "teal",   label: "Teal",    bg: "bg-teal-50",    text: "text-teal-600",   ring: "ring-teal-200",   border: "border-teal-100" },
];

export const COLOR_MAP: Record<string, SectionColorDef> =
  Object.fromEntries(SECTION_COLORS.map((c) => [c.name, c]));

const uid = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

export function makeDefaultSection(order = 0): CustomSection {
  return {
    id: uid(),
    name: "What's Included",
    type: "bullets",
    content: [],
    icon: "check",
    icon_color: "green",
    icon_style: "filled",
    tags: [],
    enabled: true,
    order,
  };
}
