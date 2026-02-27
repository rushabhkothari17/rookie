// Shared types for product detail layouts
export interface IntakeQuestion {
  key: string;
  label: string;
  type: string;
  helper_text?: string;
  tooltip_text?: string;
  required?: boolean;
  enabled?: boolean;
  order?: number;
  step_group?: number;
  // Dropdown/Multiselect
  affects_price?: boolean;
  price_mode?: "add" | "multiply";
  options?: { label: string; value: string; price_value?: number }[];
  // Number
  price_per_unit?: number;
  pricing_mode?: "flat" | "tiered";
  tiers?: { from: number; to: number | null; price_per_unit: number }[];
  min?: number;
  max?: number;
  step?: number;
  default_value?: number;
  // Boolean
  price_for_yes?: number;
  price_for_no?: number;
  // Formula
  formula_expression?: string;
  // Date
  date_format?: "date" | "date_range";
  // File
  accept?: string;
  max_size_mb?: number;
  // HTML block
  content?: string;
  // Visibility
  visibility_rule?: {
    depends_on: string;
    operator: string;
    value: string;
  } | null;
}

export interface Product {
  id: string;
  name: string;
  tagline?: string;
  description_long?: string;
  bullets?: string[];
  card_tag?: string;
  card_description?: string;
  card_bullets?: string[];
  tag?: string;
  category?: string;
  base_price?: number;
  pricing_type?: string;
  external_url?: string;
  is_subscription?: boolean;
  stripe_price_id?: string;
  terms_id?: string;
  display_layout?: string;
  price_rounding?: string;
  intake_schema_json?: {
    version: number;
    questions: IntakeQuestion[];
    price_floor?: number | null;
    price_ceiling?: number | null;
  };
  custom_sections?: {
    id: string;
    name: string;
    content: string;
    icon?: string;
    icon_color?: string;
    tags?: string[];
  }[];
  faqs?: { question: string; answer: string }[];
  price_inputs?: any[];
}

export interface PricingResult {
  subtotal: number;
  fee: number;
  total: number;
  line_items?: { label: string; amount: number }[];
  requires_checkout?: boolean;
  is_subscription?: boolean;
  is_enquiry?: boolean;
  external_url?: string | null;
}

export interface LayoutProps {
  product: Product;
  pricing: PricingResult | null;
  intakeAnswers: Record<string, any>;
  setIntakeAnswers: (fn: (prev: Record<string, any>) => Record<string, any>) => void;
  visibleIntakeQuestions: IntakeQuestion[];
  handleAddToCart: () => void;
  isRFQ: boolean;
  isSubscription: boolean;
  termsUrl?: string;
  currency?: string;
  scopeUnlock?: any;
  scopeId: string;
  setScopeId: (v: string) => void;
  handleValidateScopeId: () => void;
  scopeValidating: boolean;
  scopeError: string;
}
