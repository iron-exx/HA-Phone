import { z } from "zod";
import type { DestinationType } from "@/types/api";

export const ivrSchema = z.object({
  number: z.coerce.number().int().min(10, "Mindestens 10").max(99, "Höchstens 99"),
  name: z.string().min(1, "Pflichtfeld").max(64, "Max. 64 Zeichen"),
  timeout: z.coerce.number().int().min(3, "Mindestens 3 s").max(60, "Höchstens 60 s"),
  max_invalid_tries: z.coerce.number().int().min(1, "Mindestens 1").max(10, "Höchstens 10"),
});

export type IVRFormValues = z.infer<typeof ivrSchema>;

export const IVR_OPTION_ALLOWED_DESTINATION_TYPES: DestinationType[] = [
  "extension",
  "ring_group",
  "ivr",
  "voicemail",
  "hangup",
];
