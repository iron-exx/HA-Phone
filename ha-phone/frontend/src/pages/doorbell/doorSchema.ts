import { z } from "zod";
import type { DoorAction, Extension } from "@/types/api";

export const doorSchema = z.object({
  is_door: z.boolean(),
  numeric_callerid: z.boolean(),
  door_open_code: z.string().trim().max(16, "Max. 16 Zeichen").regex(/^[0-9*#]*$/, "Nur 0-9, * und #"),
  door_open_webhook: z.string().trim().max(512, "Max. 512 Zeichen").regex(/^(https?:\/\/\S+)?$/, "http:// oder https:// Adresse"),
  doorbell_camera: z
    .string()
    .trim()
    .max(512, "Max. 512 Zeichen")
    .regex(/^(camera\.[a-z0-9_]+|https?:\/\/\S+)?$/, "camera.name oder http(s):// Adresse"),
});

export type DoorFormValues = z.infer<typeof doorSchema>;

export function doorDefaults(ext: Extension): DoorFormValues {
  return {
    is_door: ext.is_door ?? false,
    numeric_callerid: ext.numeric_callerid ?? false,
    door_open_code: ext.door_open_code ?? "",
    door_open_webhook: ext.door_open_webhook ?? "",
    doorbell_camera: ext.doorbell_camera ?? "",
  };
}

export interface DoorPatch extends DoorFormValues {
  door_actions: DoorAction[];
}

/** PATCH-Körper des Tür-Dialogs – bewusst ohne Felder des Nebenstellen-Dialogs (außer Altgeräte-Modus). */
export function doorPatchBody(values: DoorFormValues, actions: DoorAction[]): DoorPatch {
  return {
    is_door: values.is_door,
    numeric_callerid: values.numeric_callerid,
    door_open_code: values.door_open_code.trim(),
    door_open_webhook: values.door_open_webhook.trim(),
    doorbell_camera: values.doorbell_camera.trim(),
    door_actions: actions,
  };
}

export function doorSummary(
  ext: Partial<Pick<Extension, "door_open_code" | "door_open_webhook" | "doorbell_camera" | "door_actions">>,
): string {
  const parts: string[] = [];
  if (ext.door_open_webhook) parts.push("Öffnen per Schieberegler");
  else if (ext.door_open_code) parts.push(`Öffnen mit ${ext.door_open_code}`);
  else parts.push("kein Tür-Öffner");
  parts.push(ext.doorbell_camera ? "mit Klingelbild" : "ohne Klingelbild");
  const actions = ext.door_actions?.length ?? 0;
  if (actions > 0) parts.push(actions === 1 ? "1 Aktion" : `${actions} Aktionen`);
  return parts.join(" · ");
}
