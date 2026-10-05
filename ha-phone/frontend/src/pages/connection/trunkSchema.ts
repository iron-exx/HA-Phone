import { z } from "zod";

export const trunkSchema = z.object({
  registrar_host: z.string().min(1, "Pflichtfeld"),
  port: z.coerce.number().int().min(0, "Mindestens 0").max(65535, "Höchstens 65535"),
  transport: z.enum(["udp", "tcp", "tls"]),
  domain: z.string().default(""),
  auth_username: z.string().min(1, "Pflichtfeld"),
  password: z.string().min(1, "Pflichtfeld"),
  phone_number: z.string().min(1, "Pflichtfeld"),
  reg_refresh: z.coerce.number().int().min(30, "Mindestens 30").max(3600, "Höchstens 3600"),
  codecs: z.string().default("ulaw,alaw"),
  local_ringback: z.boolean().default(true),
});

export type TrunkFormValues = z.infer<typeof trunkSchema>;

// Codecs des freien Asterisk-Builds (G.729 braucht ein lizenziertes Modul).
export const CODEC_OPTIONS: { id: string; label: string }[] = [
  { id: "ulaw", label: "u-law (G.711µ)" },
  { id: "alaw", label: "a-law (G.711a)" },
  { id: "g722", label: "G.722 (HD)" },
  { id: "gsm", label: "GSM" },
  { id: "g726", label: "G.726" },
];

export const DEFAULT_VALUES: TrunkFormValues = {
  registrar_host: "",
  port: 0,
  transport: "udp",
  domain: "",
  auth_username: "",
  password: "",
  phone_number: "",
  reg_refresh: 60,
  codecs: "ulaw,alaw",
  local_ringback: true,
};
