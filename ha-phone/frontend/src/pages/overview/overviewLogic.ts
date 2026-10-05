import type { DoorbellEvent, Extension } from "@/types/api";

export interface UpdateInfo {
  version: string;
  version_latest: string;
  update_available: boolean;
}

export interface RegenerationStepStatus {
  name: string;
  label: string;
  ok: boolean;
  skipped: boolean;
  updated_at: string | null;
  message: string;
}

export interface ConfigRegenerationStatus {
  ok: boolean;
  source: string | null;
  last_run_at: string | null;
  last_failure_at: string | null;
  steps: RegenerationStepStatus[];
}

const TRUNK_LABELS: Record<string, string> = {
  Registered: "Verbunden",
  Unregistered: "Nicht angemeldet",
  Rejected: "Abgelehnt",
  Forbidden: "Zugang verweigert",
  Unreachable: "Nicht erreichbar",
  UNKNOWN: "Unbekannt",
};

export function trunkLabel(status: string): string {
  return TRUNK_LABELS[status] ?? status;
}

export function greeting(now: Date): string {
  const h = now.getHours();
  if (h >= 5 && h < 11) return "Guten Morgen";
  if (h >= 11 && h < 18) return "Guten Tag";
  return "Guten Abend";
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function countToday(events: DoorbellEvent[], now: Date): number {
  return events.filter((e) => isSameDay(new Date(e.started_at), now)).length;
}

export function formatDoorTime(iso: string, now: Date): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  if (isSameDay(d, now)) return `heute ${time}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (isSameDay(d, yesterday)) return `gestern ${time}`;
  return `${d.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })} ${time}`;
}

export type AttentionTone = "error" | "warn" | "info";

export interface AttentionItem {
  id: string;
  tone: AttentionTone;
  text: string;
  to?: string;
}

export interface AttentionInput {
  trunkStatus: string;
  extensions: Pick<Extension, "number" | "display_name" | "enabled">[];
  online: ReadonlySet<string>;
  statusKnown: boolean;
  regenFailures: Pick<RegenerationStepStatus, "name" | "label">[];
  updateLatest: string | null;
}

export const MAX_OFFLINE_LISTED = 3;

export function buildAttention(input: AttentionInput): AttentionItem[] {
  const items: AttentionItem[] = [];
  if (input.trunkStatus !== "Registered" && input.trunkStatus !== "UNKNOWN") {
    items.push({ id: "trunk", tone: "error", text: `Telefonanbieter: ${trunkLabel(input.trunkStatus)}.`, to: "/connection/provider" });
  }
  for (const step of input.regenFailures) {
    items.push({ id: `regen-${step.name}`, tone: "error", text: `„${step.label}“ konnte nicht angewendet werden.`, to: "/system/diagnostics" });
  }
  if (input.statusKnown) {
    const offline = input.extensions.filter((e) => e.enabled && !input.online.has(String(e.number)));
    for (const e of offline.slice(0, MAX_OFFLINE_LISTED)) {
      items.push({ id: `ext-${e.number}`, tone: "warn", text: `Nst. ${e.number} „${e.display_name}“ ist nicht angemeldet.`, to: "/extensions" });
    }
    const rest = offline.length - MAX_OFFLINE_LISTED;
    if (rest > 0) {
      items.push({
        id: "ext-more",
        tone: "warn",
        text: rest === 1 ? "1 weitere Nebenstelle ist nicht angemeldet." : `${rest} weitere Nebenstellen sind nicht angemeldet.`,
        to: "/extensions",
      });
    }
  }
  if (input.updateLatest) items.push({ id: "update", tone: "info", text: `Update auf Version ${input.updateLatest} verfügbar.` });
  return items;
}

export function summaryLine(online: number, total: number, attention: number): string {
  const devices = total === 1 ? `${online} von 1 Nebenstelle ist angemeldet.` : `${online} von ${total} Nebenstellen sind angemeldet.`;
  if (attention === 0) return `Alles läuft. ${devices}`;
  return `${attention === 1 ? "1 Punkt braucht" : `${attention} Punkte brauchen`} Aufmerksamkeit. ${devices}`;
}
