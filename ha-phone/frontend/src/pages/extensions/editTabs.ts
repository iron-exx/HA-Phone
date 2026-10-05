import type { FieldErrors } from "react-hook-form";
import type { EditFormValues } from "./schema";

export type ExtensionTab = "general" | "app" | "reach";

export const EXTENSION_TABS: { value: ExtensionTab; label: string }[] = [
  { value: "general", label: "Allgemein" },
  { value: "app", label: "Handy-App" },
  { value: "reach", label: "Erreichbarkeit" },
];

export const FIELD_TAB: Record<keyof EditFormValues, ExtensionTab> = {
  number: "general",
  display_name: "general",
  sip_password: "general",
  enabled: "general",
  internal_only: "general",
  numeric_callerid: "general",
  video_capable: "app",
  recording_allowed: "app",
  presence_status: "reach",
  ha_person: "reach",
  mobile_fallback: "reach",
};

export function isExtensionTab(value: string): value is ExtensionTab {
  return EXTENSION_TABS.some((t) => t.value === value);
}

export function firstTabWithError(errors: FieldErrors<EditFormValues>): ExtensionTab | null {
  const failing = new Set(Object.keys(errors).map((field) => FIELD_TAB[field as keyof EditFormValues]));
  return EXTENSION_TABS.find((t) => failing.has(t.value))?.value ?? null;
}
