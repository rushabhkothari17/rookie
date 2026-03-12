/**
 * CustomerSignupFields
 *
 * Thin wrapper around UniversalFormRenderer for customer signup / create-customer forms.
 * Injects the auth-only fields (email, password) into the schema at the right position
 * so they render alongside the admin-configured fields in the correct order.
 *
 * Used by:
 *   - public /signup page (compact=false)
 *   - admin "Add Customer" dialog (compact=true)
 */

import { UniversalFormRenderer } from "@/components/UniversalFormRenderer";
import { type FormField } from "@/components/FormSchemaBuilder";

interface Props {
  schema: FormField[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  showPassword?: boolean;
  compact?: boolean;
  partnerCode?: string;
  /** @deprecated countries/provinces are now fetched internally by AddressFieldRenderer */
  countries?: unknown;
  /** @deprecated countries/provinces are now fetched internally by AddressFieldRenderer */
  provinces?: unknown;
}

const EMAIL_FIELD: FormField = {
  id: "builtin_email", key: "email", label: "Email address", type: "email",
  required: true, placeholder: "", locked: true, enabled: true, options: [], order: -1,
};

const PASSWORD_FIELD: FormField = {
  id: "builtin_password", key: "password", label: "Password", type: "password",
  required: true, placeholder: "", locked: true, enabled: true, options: [], order: -1,
};

/** Inject email (and optionally password) just after full_name / company_name in the schema */
function buildFields(schema: FormField[], showPassword: boolean): FormField[] {
  const sorted = [...schema]
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    .filter(f => f.enabled !== false);

  const fnIdx = sorted.findIndex(f => f.key === "full_name");
  const cnIdx = sorted.findIndex(f => f.key === "company_name");
  const insertAfterIdx = (cnIdx >= 0 && fnIdx >= 0 && cnIdx === fnIdx + 1) ? cnIdx : fnIdx;
  const insertAt = insertAfterIdx >= 0 ? insertAfterIdx + 1 : 0;

  const injected: FormField[] = showPassword ? [EMAIL_FIELD, PASSWORD_FIELD] : [EMAIL_FIELD];
  return [...sorted.slice(0, insertAt), ...injected, ...sorted.slice(insertAt)];
}

export function CustomerSignupFields({
  schema, values, onChange, showPassword = true, compact = false, partnerCode,
}: Props) {
  const fields = buildFields(schema, showPassword);
  return (
    <UniversalFormRenderer
      fields={fields}
      values={values}
      onChange={onChange}
      compact={compact}
      partnerCode={partnerCode}
    />
  );
}
