import { z } from "zod";
import type { Extension } from "@/types/api";

export const extensionSchema = z.object({
  number: z.coerce.number().int().min(10, "Mindestens 10").max(99, "Höchstens 99"),
  display_name: z.string().min(1, "Pflichtfeld").max(64, "Max. 64 Zeichen"),
  sip_password: z.string().min(8, "Mind. 8 Zeichen"),
  enabled: z.boolean(),
  video_capable: z.boolean().default(false),
  internal_only: z.boolean().default(false),
  numeric_callerid: z.boolean().default(false),
});

export type ExtensionFormValues = z.infer<typeof extensionSchema>;

export const PRESENCE_STATUSES: { value: string; label: string }[] = [
  { value: "available", label: "Verfügbar" },
  { value: "away", label: "Abwesend" },
  { value: "lunch", label: "Mittagspause" },
  { value: "do_not_disturb", label: "Nicht stören" },
  { value: "off_work", label: "Feierabend" },
];

export const editSchema = extensionSchema.extend({
  sip_password: z
    .string()
    .refine((v) => v === "" || v.length >= 8, "Mind. 8 Zeichen oder leer lassen"),
  presence_status: z.string().default("available"),
  recording_allowed: z.boolean().default(false),
  ha_person: z
    .string()
    .max(128, "Max 128 Zeichen")
    .regex(/^(person\.[a-z0-9_]+)?$/, "z. B. person.anna")
    .default(""),
  mobile_fallback: z
    .string()
    .max(32, "Max 32 Zeichen")
    .regex(/^(\+?[0-9][0-9 /()-]{4,22})?$/, "Telefonnummer, z. B. 0171 5551234")
    .default(""),
});

export type EditFormValues = z.infer<typeof editSchema>;

export function editDefaults(ext: Extension): EditFormValues {
  return {
    number: ext.number,
    display_name: ext.display_name,
    sip_password: "",
    enabled: ext.enabled,
    video_capable: ext.video_capable ?? false,
    internal_only: ext.internal_only ?? false,
    numeric_callerid: ext.numeric_callerid ?? false,
    presence_status: ext.presence_status || "available",
    recording_allowed: ext.recording_allowed ?? false,
    ha_person: ext.ha_person ?? "",
    mobile_fallback: ext.mobile_fallback ?? "",
  };
}

export interface ExtensionPatch {
  display_name: string;
  enabled: boolean;
  video_capable: boolean;
  internal_only: boolean;
  numeric_callerid: boolean;
  presence_status: string;
  recording_allowed: boolean;
  ha_person: string;
  mobile_fallback: string;
  sip_password?: string;
}

/** PATCH-Körper des Nebenstellen-Dialogs – keine Tür-Felder (siehe Türklingel-Seite). */
export function editPatchBody(values: EditFormValues): ExtensionPatch {
  const body: ExtensionPatch = {
    display_name: values.display_name,
    enabled: values.enabled,
    video_capable: values.video_capable,
    internal_only: values.internal_only,
    numeric_callerid: values.numeric_callerid,
    presence_status: values.presence_status,
    recording_allowed: values.recording_allowed,
    ha_person: (values.ha_person ?? "").trim(),
    mobile_fallback: (values.mobile_fallback ?? "").trim(),
  };
  return values.sip_password ? { ...body, sip_password: values.sip_password } : body;
}
